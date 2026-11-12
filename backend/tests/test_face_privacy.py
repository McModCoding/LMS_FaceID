"""F07: consent, image storage and concurrent revocation on MySQL."""


from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.face.base import EnrollResult, FaceBox, MatchResult
from app.models.learning import FaceConsent, FaceTemplate, FaceTemplateStatus
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student
from app.models.user import User
from app.services import face_service
from app.utils.clock import VN_TZ, now_local, override_clock
from tests.test_m4_m5 import _learning_data, _token

IMAGE = b"\xff\xd8\xfff07-test-only"
FILES = [("face.jpg", "image/jpeg", IMAGE)]


class PrivacyEngine:
    name = "f07-test-only"
    version = "1"
    is_ready = True

    def assess_enrollment(self, image):
        return EnrollResult(True, 0.9, b"test-embedding", None)

    def embed_stored_image(self, image):
        return self.assess_enrollment(image)

    def identify(self, image, candidates):
        self.candidate_ids = {row.student_id for row in candidates}
        return self.matches


@pytest.fixture
def privacy_scene(db_session, tmp_path, monkeypatch):
    cls, lecturer, user = _learning_data(db_session)
    student = db_session.query(Student).filter_by(user_id=user.id).one()
    monkeypatch.setattr(settings, "FACE_STORAGE_DIR", str(tmp_path / "face"))
    engine = PrivacyEngine()
    monkeypatch.setattr(face_service, "get_engine", lambda: engine)
    return {"user": user, "student": student, "class": cls, "lecturer": lecturer,
            "engine": engine, "folder": tmp_path / "face" / str(student.id)}


def _call(factory, user_id, operation):
    with factory() as db:
        try:
            return operation(db, db.get(User, user_id))
        except HTTPException as error:
            db.rollback()
            return error.status_code, error.detail["code"]


def _serialized_pair(factory, user_id, entered, release, first, second):
    second_started, second_done = Event(), Event()

    def run_second():
        second_started.set()
        try:
            return _call(factory, user_id, second)
        finally:
            second_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(_call, factory, user_id, first)
        try:
            assert entered.wait(15), "First operation did not enter its critical section"
            b = pool.submit(run_second)
            assert second_started.wait(15)
            assert not second_done.wait(0.3), "Second operation escaped the student lock"
        finally:
            release.set()
        return a.result(timeout=20), b.result(timeout=20)


def _assert_revoked(db, scene):
    db.expire_all()
    assert db.query(FaceConsent).filter_by(student_id=scene["student"].id, revoked_at=None).count() == 0
    rows = db.query(FaceTemplate).filter_by(student_id=scene["student"].id).all()
    assert all(row.status == FaceTemplateStatus.revoked and row.embedding is None for row in rows)
    assert not list(scene["folder"].glob("*.jpg"))


def test_revoke_clears_all_legacy_active_consents(db_session, privacy_scene):
    scene = privacy_scene
    for version in ("old-1", "old-2"):
        db_session.add(FaceConsent(student_id=scene["student"].id, text_version=version, consented_at=now_local()))
    db_session.commit()
    profile = face_service.revoke_consent(db_session, scene["user"])
    assert profile["consented"] is False
    assert db_session.query(FaceConsent).filter_by(student_id=scene["student"].id, revoked_at=None).count() == 0


def test_engine_error_on_second_image_does_not_leave_first_file(db_session, privacy_scene, monkeypatch):
    face_service.grant_consent(db_session, privacy_scene["user"], "v1")
    calls = 0

    def assess(image):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("F07_PRIVATE_ENGINE_DETAILS")
        return EnrollResult(True, 0.9, b"test-embedding", None)

    monkeypatch.setattr(privacy_scene["engine"], "assess_enrollment", assess)
    with pytest.raises(HTTPException) as error:
        face_service.enroll_images(db_session, privacy_scene["user"], FILES * 2)
    assert error.value.detail["code"] == "FACE_ENROLL_FAILED"
    assert "F07_PRIVATE_ENGINE_DETAILS" not in str(error.value.detail)
    db_session.rollback()
    assert not list(privacy_scene["folder"].glob("*.jpg"))
    assert db_session.query(FaceTemplate).filter_by(student_id=privacy_scene["student"].id).count() == 0


def test_concurrent_grants_create_only_one_active_consent(db_session, privacy_scene, TestingSessionLocal, monkeypatch, test_engine):
    assert test_engine.dialect.name == 'mysql'
    entered, release = Event(), Event()
    original = face_service._consent
    def pause_first(db, student_id):
        result = original(db, student_id)
        if not entered.is_set():
            entered.set()
            assert release.wait(15)
        return result
    monkeypatch.setattr(face_service, '_consent', pause_first)
    user_id = privacy_scene['user'].id
    a, b = _serialized_pair(TestingSessionLocal, user_id, entered, release,
        lambda db, user: face_service.grant_consent(db, user, 'first'),
        lambda db, user: face_service.grant_consent(db, user, 'second'))
    assert a['consented'] and b['consented']
    db_session.expire_all()
    assert db_session.query(FaceConsent).filter_by(student_id=privacy_scene['student'].id, revoked_at=None).count() == 1


@pytest.mark.parametrize('first_operation', ['enroll', 'reindex', 'recognize'])
def test_revocation_waits_for_inflight_operation_then_removes_data(
    db_session, privacy_scene, TestingSessionLocal, monkeypatch, test_engine, first_operation
):
    assert test_engine.dialect.name == 'mysql'
    scene = privacy_scene
    face_service.grant_consent(db_session, scene['user'], 'v1')
    entered, release = Event(), Event()
    if first_operation != 'enroll':
        face_service.enroll_images(db_session, scene['user'], FILES)
    if first_operation == 'reindex':
        row = db_session.query(FaceTemplate).filter_by(student_id=scene['student'].id).one()
        row.status, row.embedding = FaceTemplateStatus.pending_embedding, None
        db_session.commit()
    if first_operation == 'recognize':
        sess = SessionModel(class_id=scene['class'].id, session_no=1, date=date(2026, 10, 18),
                            start_time=time(8), end_time=time(10), room='F07', status=SessionStatus.open)
        db_session.add(sess)
        db_session.commit()
        session_id = sess.id
        student_id = scene['student'].id
        scene['engine'].matches = [MatchResult(FaceBox(0, 0, 1, 1, 1), student_id, 'matched', .99, .9)]
    method_name = {'enroll': 'assess_enrollment', 'reindex': 'embed_stored_image', 'recognize': 'identify'}[first_operation]
    original = getattr(scene['engine'], method_name)
    def pause(*args):
        entered.set()
        assert release.wait(15)
        return original(*args)
    monkeypatch.setattr(scene['engine'], method_name, pause)
    operations = {'enroll': lambda db, user: face_service.enroll_images(db, user, FILES),
                  'reindex': lambda db, user: face_service.reindex(db)}
    if first_operation == 'recognize':
        operations['recognize'] = lambda db, user: face_service.recognize(db, session_id, IMAGE, str(uuid4()))
    user_id = scene['user'].id
    with override_clock(datetime(2026, 10, 18, 8, 5, tzinfo=VN_TZ)):
        _, revoked = _serialized_pair(TestingSessionLocal, user_id, entered, release,
            operations[first_operation], lambda db, user: face_service.revoke_consent(db, user))
    assert revoked['consented'] is False
    _assert_revoked(db_session, scene)
    db_session.commit()
    if first_operation == 'recognize':
        response = face_service.recognize(db_session, session_id, IMAGE, str(uuid4()))
        assert scene['engine'].candidate_ids == set()
        assert response['faces'][0]['status'] == 'unknown'
        assert response['attendance_changes'] == []


def test_enrollment_waits_for_revoke_and_cannot_restore_templates(db_session, privacy_scene, TestingSessionLocal, monkeypatch):
    scene = privacy_scene
    face_service.grant_consent(db_session, scene['user'], 'v1')
    face_service.enroll_images(db_session, scene['user'], FILES)
    entered, release = Event(), Event()
    original = Path.unlink
    def pause(path, *args, **kwargs):
        if path.parent == scene['folder']:
            entered.set()
            assert release.wait(15)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', pause)
    _, enrolled = _serialized_pair(TestingSessionLocal, scene['user'].id, entered, release,
        lambda db, user: face_service.revoke_consent(db, user),
        lambda db, user: face_service.enroll_images(db, user, FILES))
    assert enrolled == (409, 'FACE_CONSENT_REQUIRED')
    _assert_revoked(db_session, scene)


@pytest.mark.parametrize('failure', ['write', 'commit'])
def test_enrollment_storage_or_commit_error_cleans_partial_files(db_session, privacy_scene, monkeypatch, failure):
    scene = privacy_scene
    face_service.grant_consent(db_session, scene['user'], 'v1')
    if failure == 'write':
        original = Path.write_bytes
        calls = 0
        def partial_write(path, content):
            nonlocal calls
            calls += 1
            if calls == 2:
                original(path, content[:3])
                raise OSError('F07_PRIVATE_STORAGE_DETAILS')
            return original(path, content)
        monkeypatch.setattr(Path, 'write_bytes', partial_write)
    else:
        original = db_session.commit
        first = True
        def failed_commit():
            nonlocal first
            if first:
                first = False
                db_session.flush()
                raise RuntimeError('F07_PRIVATE_SQL_DETAILS')
            return original()
        monkeypatch.setattr(db_session, 'commit', failed_commit)
    with pytest.raises(HTTPException) as error:
        face_service.enroll_images(db_session, scene['user'], FILES * 2)
    assert error.value.detail['code'] == 'FACE_ENROLL_FAILED'
    assert 'F07_PRIVATE' not in str(error.value.detail)
    assert not list(scene['folder'].glob('*.jpg'))
    assert db_session.query(FaceTemplate).filter_by(student_id=scene['student'].id).count() == 0


def test_orphan_cleanup_failure_survives_session_and_can_be_retried(db_session, privacy_scene, monkeypatch, TestingSessionLocal):
    scene = privacy_scene
    face_service.grant_consent(db_session, scene['user'], 'v1')
    original_assess = scene['engine'].assess_enrollment
    calls = 0
    def failed_assess(image):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('engine failed')
        return original_assess(image)
    monkeypatch.setattr(scene['engine'], 'assess_enrollment', failed_assess)
    original_unlink = Path.unlink
    def locked(path, *args, **kwargs):
        if path.parent == scene['folder']:
            raise PermissionError('file busy')
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', locked)
    with pytest.raises(HTTPException) as error:
        face_service.enroll_images(db_session, scene['user'], FILES * 2)
    assert error.value.detail['details']['cleanup_pending'] is True
    user_id = scene['user'].id
    with TestingSessionLocal() as fresh:
        assert face_service.get_profile(fresh, fresh.get(User, user_id))['cleanup_pending'] is True
    monkeypatch.setattr(Path, 'unlink', original_unlink)
    response = face_service.revoke_consent(db_session, scene['user'])
    assert response['cleanup_pending'] is False
    assert response['consented'] is False
    assert not list(scene['folder'].glob('*.jpg'))


def test_partial_revoke_disables_embeddings_and_exposes_retry(test_client, db_session, privacy_scene, monkeypatch):
    scene = privacy_scene
    face_service.grant_consent(db_session, scene['user'], 'v1')
    face_service.enroll_images(db_session, scene['user'], FILES * 2)
    rows = db_session.query(FaceTemplate).filter_by(student_id=scene['student'].id).all()
    locked_file = Path(rows[0].image_path)
    original = Path.unlink
    def fail_one(path, *args, **kwargs):
        if path == locked_file:
            raise PermissionError('F07_PRIVATE_PATH')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', fail_one)
    headers = _token(scene['user'])
    response = test_client.delete('/api/v1/students/me/face/consent', headers=headers)
    assert response.status_code == 500
    assert 'F07_PRIVATE_PATH' not in response.text
    assert str(scene['folder']) not in response.text
    profile = test_client.get('/api/v1/students/me/face', headers=headers).json()
    assert profile['consented'] is False and profile['cleanup_pending'] is True
    assert profile['image_count'] == 0
    db_session.expire_all()
    assert all(row.embedding is None and row.status == FaceTemplateStatus.revoked for row in rows)
    assert test_client.post('/api/v1/students/me/face/consent', headers=headers, json={'text_version': 'new'}).status_code == 500
    assert test_client.post('/api/v1/students/me/face/enroll', headers=headers,
                           files={'images': ('face.jpg', IMAGE, 'image/jpeg')}).status_code == 409
    monkeypatch.setattr(Path, 'unlink', original)
    retry = test_client.delete('/api/v1/students/me/face/consent', headers=headers)
    assert retry.status_code == 200 and retry.json()['cleanup_pending'] is False
    assert test_client.delete('/api/v1/students/me/face/consent', headers=headers).status_code == 200
    _assert_revoked(db_session, scene)


def test_old_repeatable_read_snapshot_cannot_bypass_revocation(db_session, privacy_scene, test_engine, TestingSessionLocal):
    assert test_engine.dialect.name == 'mysql'
    scene = privacy_scene
    face_service.grant_consent(db_session, scene['user'], 'v1')
    face_service.enroll_images(db_session, scene['user'], FILES)
    student_id, user_id = scene['student'].id, scene['user'].id
    with Session(test_engine.execution_options(isolation_level='REPEATABLE READ')) as stale:
        user = stale.get(User, user_id)
        assert stale.query(FaceConsent).filter_by(student_id=student_id, revoked_at=None).first() is not None
        result = _call(TestingSessionLocal, user_id, face_service.revoke_consent)
        assert result['consented'] is False
        with pytest.raises(HTTPException) as error:
            face_service.enroll_images(stale, user, FILES)
        assert error.value.detail['code'] == 'FACE_CONSENT_REQUIRED'
    _assert_revoked(db_session, scene)


def test_reindex_requires_live_consent_and_rolls_back_engine_failure(db_session, privacy_scene, monkeypatch):
    scene = privacy_scene
    scene['folder'].mkdir(parents=True)
    for n in range(2):
        path = scene['folder'] / f'pending-{n}.jpg'
        path.write_bytes(IMAGE)
        db_session.add(FaceTemplate(student_id=scene['student'].id, image_path=str(path),
                                   status=FaceTemplateStatus.pending_embedding))
    db_session.commit()
    assert face_service.reindex(db_session)['activated'] == 0
    face_service.grant_consent(db_session, scene['user'], 'v1')
    original = scene['engine'].embed_stored_image
    calls = 0
    def fail_second(image):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('F07_PRIVATE_ENGINE_DETAILS')
        return original(image)
    monkeypatch.setattr(scene['engine'], 'embed_stored_image', fail_second)
    with pytest.raises(HTTPException) as error:
        face_service.reindex(db_session)
    assert error.value.detail['code'] == 'FACE_REINDEX_FAILED'
    assert 'F07_PRIVATE_ENGINE_DETAILS' not in str(error.value.detail)
    db_session.expire_all()
    assert all(row.embedding is None and row.status == FaceTemplateStatus.pending_embedding
               for row in db_session.query(FaceTemplate).filter_by(student_id=scene['student'].id))
    monkeypatch.setattr(scene['engine'], 'embed_stored_image', original)
    assert face_service.reindex(db_session)['activated'] == 2


def test_revoke_never_deletes_a_path_outside_student_storage(db_session, privacy_scene, tmp_path):
    scene = privacy_scene
    face_service.grant_consent(db_session, scene['user'], 'v1')
    outside = tmp_path / 'unrelated.jpg'
    outside.write_bytes(IMAGE)
    db_session.add(FaceTemplate(student_id=scene['student'].id, image_path=str(outside),
                               status=FaceTemplateStatus.active, embedding=b'test-embedding'))
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        face_service.revoke_consent(db_session, scene['user'])
    assert error.value.detail['code'] == 'FACE_DATA_DELETE_FAILED'
    assert outside.read_bytes() == IMAGE
    db_session.expire_all()
    assert db_session.query(FaceTemplate).filter_by(student_id=scene['student'].id).one().embedding is None
