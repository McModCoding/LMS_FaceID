"""M4 FaceID: serialized consent and recoverable private-image cleanup."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from math import isfinite
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.face.base import Candidate
from app.face.factory import get_engine
from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.learning import (
    FaceConsent,
    FaceTemplate,
    FaceTemplateStatus,
    RecognitionFrame,
    RecognitionLog,
    RecognitionStatus,
)
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student
from app.models.user import User
from app.services import attendance_service
from app.utils.clock import now_local

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def _valid_image_signature(content_type: str | None, content: bytes) -> bool:
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    return False


def _student(db: Session, user: User) -> Student:
    # The student row is the shared mutex even before the first consent exists.
    student = (db.query(Student).filter(Student.user_id == user.id, Student.is_deleted == False)
               .populate_existing().with_for_update().first())
    if not student:
        raise HTTPException(404, detail={"code": "STUDENT_NOT_FOUND", "message": "Không tìm thấy hồ sơ sinh viên."})
    return student


def _consent(db: Session, student_id: int) -> FaceConsent | None:
    # Locking reads also refresh an old MySQL REPEATABLE READ snapshot.
    return (db.query(FaceConsent).filter(FaceConsent.student_id == student_id, FaceConsent.revoked_at.is_(None))
            .order_by(FaceConsent.id.desc()).populate_existing().with_for_update().first())


def _templates(db: Session, student_id: int) -> list[FaceTemplate]:
    return (db.query(FaceTemplate).filter(FaceTemplate.student_id == student_id)
            .order_by(FaceTemplate.id).populate_existing().with_for_update().all())


def _storage_folder(student_id: int) -> Path:
    root = Path(settings.FACE_STORAGE_DIR).resolve()
    folder = (root / str(student_id)).resolve()
    if folder.parent != root:
        raise HTTPException(500, detail={"code": "FACE_STORAGE_FAILED", "message": "Thư mục ảnh không hợp lệ. Hãy liên hệ quản trị viên."})
    return folder


def _stored_path(folder: Path, value: str) -> Path:
    target = Path(value).resolve()
    if target.parent != folder:
        raise HTTPException(500, detail={"code": "FACE_STORAGE_FAILED", "message": "Không thể xử lý tệp ảnh an toàn. Hãy liên hệ quản trị viên."})
    return target


def _pending_paths(db: Session, student_id: int) -> tuple[list[FaceTemplate], set[Path]]:
    folder = _storage_folder(student_id)
    rows = _templates(db, student_id)
    registered = {_stored_path(folder, row.image_path) for row in rows
                  if row.image_path and row.status != FaceTemplateStatus.revoked}
    pending = {_stored_path(folder, row.image_path) for row in rows
               if row.image_path and row.status == FaceTemplateStatus.revoked}
    # Orphan files left by a failed write/rollback or process interruption are
    # durable retry evidence in this student's private directory. Never recurse.
    if folder.exists():
        pending.update(_stored_path(folder, str(item)) for item in folder.iterdir()
                       if (item.is_file() or item.is_symlink()) and item.resolve() not in registered)
    return rows, pending


def _delete_pending(db: Session, student_id: int) -> int:
    rows, pending = _pending_paths(db, student_id)
    failed: set[Path] = set()
    for target in pending:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            failed.add(target)
    folder = _storage_folder(student_id)
    for row in rows:
        if row.status == FaceTemplateStatus.revoked and row.image_path and _stored_path(folder, row.image_path) not in failed:
            row.image_path = ""
    db.flush()
    return len(failed)


def _cleanup_error() -> HTTPException:
    return HTTPException(500, detail={
        "code": "FACE_DATA_DELETE_FAILED",
        "message": "Dữ liệu đã ngừng dùng để nhận diện nhưng chưa xóa hết ảnh. Hãy chọn Thử xóa dữ liệu còn lại hoặc liên hệ quản trị viên.",
        "details": {"cleanup_pending": True},
    })


def _profile(db: Session, student: Student) -> dict:
    consent = _consent(db, student.id)
    templates = [row for row in _templates(db, student.id)
                 if row.status != FaceTemplateStatus.revoked] if consent else []
    try:
        cleanup_pending = bool(_pending_paths(db, student.id)[1])
    except (OSError, HTTPException):
        cleanup_pending = True
    return {"consented": consent is not None, "text_version": consent.text_version if consent else None,
            "consented_at": consent.consented_at if consent else None, "image_count": len(templates),
            "status": "active" if any(row.status == FaceTemplateStatus.active for row in templates)
            else ("pending_embedding" if templates else None), "cleanup_pending": cleanup_pending}


def get_profile(db: Session, user: User) -> dict:
    return _profile(db, _student(db, user))


def grant_consent(db: Session, user: User, text_version: str) -> dict:
    try:
        student = _student(db, user)
        if _delete_pending(db, student.id):
            db.commit()
            raise _cleanup_error()
        if not _consent(db, student.id):
            db.add(FaceConsent(student_id=student.id, text_version=text_version, consented_at=now_local()))
            db.flush()
        profile = _profile(db, student)
        db.commit()
        return profile
    except Exception:
        db.rollback()
        raise


def revoke_consent(db: Session, user: User) -> dict:
    try:
        student = _student(db, user)
        consents = (db.query(FaceConsent).filter(FaceConsent.student_id == student.id, FaceConsent.revoked_at.is_(None))
                    .populate_existing().with_for_update().all())
        for consent in consents:
            consent.revoked_at = now_local()
        for template in _templates(db, student.id):
            template.embedding = None
            template.status = FaceTemplateStatus.revoked
        db.flush()
        try:
            failed = _delete_pending(db, student.id)
        except (OSError, HTTPException):
            failed = 1
        profile = _profile(db, student)
        # A failed unlink must not keep consent or embeddings usable. Revoked
        # rows retain failed paths for retry; success clears those paths.
        db.commit()
        if failed:
            raise _cleanup_error()
        return profile
    except Exception:
        db.rollback()
        raise


def enroll_images(db: Session, user: User, files: list[tuple[str | None, str | None, bytes]]) -> dict:
    student = _student(db, user)
    if not _consent(db, student.id):
        db.rollback()
        raise HTTPException(409, detail={"code": "FACE_CONSENT_REQUIRED", "message": "Bạn cần đồng ý xử lý dữ liệu khuôn mặt trước khi đăng ký ảnh."})
    if not 1 <= len(files) <= 5:
        db.rollback()
        raise HTTPException(422, detail={"code": "INVALID_IMAGE_COUNT", "message": "Chọn từ 1 đến 5 ảnh khuôn mặt."})
    try:
        if _delete_pending(db, student.id):
            db.commit()
            raise _cleanup_error()
    except Exception:
        db.rollback()
        raise
    accepted = rejected = 0
    items: list[dict] = []
    try:
        engine = get_engine()
        folder = _storage_folder(student.id)
        folder.mkdir(parents=True, exist_ok=True)
        for filename, content_type, content in files:
            suffix = ALLOWED_IMAGE_TYPES.get(content_type or "")
            reason = ("unsupported_type" if not suffix else "empty_file" if not content
                      else "file_too_large" if len(content) > MAX_IMAGE_BYTES
                      else "invalid_image" if not _valid_image_signature(content_type, content) else None)
            if reason:
                rejected += 1
                items.append({"filename": filename, "accepted": False, "reason": reason})
                continue
            result = engine.assess_enrollment(content)
            if not result.ok:
                rejected += 1
                items.append({"filename": filename, "accepted": False, "reason": result.reason or "rejected"})
                continue
            target = folder / f"{uuid4().hex}{suffix}"
            target.write_bytes(content)
            db.add(FaceTemplate(student_id=student.id, image_path=str(target), embedding=result.embedding,
                                quality_score=result.quality_score, engine_name=engine.name, engine_version=engine.version,
                                status=FaceTemplateStatus.active if result.embedding else FaceTemplateStatus.pending_embedding))
            accepted += 1
            items.append({"filename": filename, "accepted": True, "reason": None})
        db.commit()
    except Exception:
        db.rollback()
        cleanup_pending = True
        try:
            student = _student(db, user)
            cleanup_pending = bool(_delete_pending(db, student.id))
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(500, detail={
            "code": "FACE_ENROLL_FAILED", "message": "Không thể hoàn tất đăng ký ảnh. Hãy tải lại hồ sơ và thử lại; nếu còn dữ liệu chờ xóa, hãy xóa trước khi đăng ký tiếp.",
            "details": {"cleanup_pending": cleanup_pending},
        }) from None
    return {"accepted": accepted, "rejected": rejected,
            "status": "active" if engine.is_ready else "pending_embedding", "items": items}


def reindex(db: Session) -> dict:
    engine = get_engine()
    if not engine.is_ready:
        raise HTTPException(409, detail={"code": "ENGINE_NOT_READY", "message": "FaceID chưa được kích hoạt; không thể reindex."})
    processed = activated = 0
    try:
        ids = [row[0] for row in db.query(FaceTemplate.student_id)
               .filter(FaceTemplate.status == FaceTemplateStatus.pending_embedding).distinct().all()]
        students = (db.query(Student).filter(Student.id.in_(ids), Student.is_deleted == False)
                    .order_by(Student.id).populate_existing().with_for_update().all()) if ids else []
        for student in students:
            templates = [row for row in _templates(db, student.id) if row.status == FaceTemplateStatus.pending_embedding]
            processed += len(templates)
            if not _consent(db, student.id):
                continue
            for template in templates:
                try:
                    result = engine.embed_stored_image(_stored_path(_storage_folder(student.id), template.image_path).read_bytes())
                except OSError:
                    continue
                if result.ok and result.embedding:
                    template.embedding = result.embedding
                    template.quality_score = result.quality_score
                    template.engine_name = engine.name
                    template.engine_version = engine.version
                    template.status = FaceTemplateStatus.active
            # Flush before any later locking query refreshes ORM objects.
            db.flush()
            activated += sum(row.status == FaceTemplateStatus.active for row in templates)
        db.commit()
        return {"processed": processed, "activated": activated}
    except Exception:
        db.rollback()
        raise HTTPException(500, detail={"code": "FACE_REINDEX_FAILED", "message": "Không thể hoàn tất xử lý ảnh. Hãy thử lại hoặc liên hệ quản trị viên."}) from None


def recognize(db: Session, session_id: int, frame: bytes, frame_id: str | None = None) -> dict:
    engine = get_engine()
    if not engine.is_ready:
        # Mock không ghi log giả hay thay đổi chuyên cần.
        return {
            "engine": engine.name,
            "ready": False,
            "faces": [],
            "attendance_changes": [],
        }

    if frame_id is None:
        raise HTTPException(422, detail={
            "code": "FRAME_ID_REQUIRED", "message": "Cần mã khung hình để tránh tính lặp lượt nhận diện.",
        })
    try:
        frame_id = str(UUID(frame_id))
    except ValueError:
        raise HTTPException(422, detail={"code": "INVALID_FRAME_ID", "message": "Mã khung hình không hợp lệ."}) from None

    # Serialize all frame transactions for this session across workers/processes.
    session = (db.query(SessionModel).filter(SessionModel.id == session_id)
               .populate_existing().with_for_update().first())
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": "Không tìm thấy buổi học."},
        )
    if session.status != SessionStatus.open:
        raise HTTPException(
            status_code=409,
            detail={"code": "SESSION_NOT_OPEN", "message": "Buổi học chưa được mở."},
        )

    content_hash = sha256(frame).hexdigest()
    processed = (db.query(RecognitionFrame).filter(
        RecognitionFrame.session_id == session_id, RecognitionFrame.frame_id == frame_id,
    ).populate_existing().with_for_update().first())
    if processed:
        if processed.content_hash != content_hash:
            raise HTTPException(409, detail={
                "code": "FRAME_ID_REUSED", "message": "Mã khung hình đã được dùng cho nội dung khác.",
            })
        response = processed.response
        db.commit()
        return response

    enrollment_ids = {
        row.student_id
        for row in db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == session.class_id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
        .all()
    }
    # Same student locks as grant/enroll/revoke/reindex; sorted to avoid
    # conflicting multi-student lock orders. Never identify after revocation.
    students = (db.query(Student).filter(Student.id.in_(enrollment_ids), Student.is_deleted == False)
                .order_by(Student.id).populate_existing().with_for_update().all()) if enrollment_ids else []
    consented_ids = {row[0] for row in db.query(FaceConsent.student_id).filter(
        FaceConsent.student_id.in_([student.id for student in students]), FaceConsent.revoked_at.is_(None),
    ).with_for_update().all()} if students else set()
    template_rows = (
        db.query(FaceTemplate)
        .filter(
            FaceTemplate.student_id.in_(consented_ids),
            FaceTemplate.status == FaceTemplateStatus.active,
            FaceTemplate.embedding.is_not(None),
        )
        .populate_existing().with_for_update().all()
        if consented_ids
        else []
    )
    embeddings: dict[int, list[bytes]] = {}
    for template in template_rows:
        if template.embedding:
            embeddings.setdefault(template.student_id, []).append(template.embedding)
    candidates = [
        Candidate(student_id=student_id, embeddings=values)
        for student_id, values in embeddings.items()
    ]
    matches = engine.identify(frame, candidates)
    occurrences = Counter(match.student_id for match in matches if match.student_id is not None)
    matched_ids: set[int] = set()
    faces: list[dict] = []
    attendance_changes: list[dict] = []

    if not matches:
        db.add(
            RecognitionLog(
                session_id=session.id,
                student_id=None,
                status=RecognitionStatus.no_face,
                score=None,
                margin=None,
                engine_name=engine.name,
                frame_at=now_local(),
            )
        )

    for match in matches:
        log_status = RecognitionStatus(match.status)
        student_id = match.student_id if match.student_id in embeddings else None
        score = match.score if match.score is not None and isfinite(match.score) else None
        margin = match.margin if match.margin is not None and isfinite(match.margin) else None
        if student_id is None:
            log_status = RecognitionStatus.unknown
        elif occurrences[student_id] > 1:
            # Two boxes claiming the same identity are ambiguous, not two hits.
            log_status = RecognitionStatus.ambiguous
        elif match.status == "matched":
            if score is None or score < settings.FACE_MATCH_THRESHOLD:
                log_status = RecognitionStatus.low_quality
            elif margin is None or margin < settings.FACE_MARGIN_THRESHOLD:
                log_status = RecognitionStatus.ambiguous

        db.add(RecognitionLog(
            session_id=session.id, student_id=student_id, status=log_status,
            score=score, margin=margin, engine_name=engine.name, frame_at=now_local(),
        ))
        change = None
        if log_status == RecognitionStatus.matched and student_id is not None:
            matched_ids.add(student_id)
            record, result_code = attendance_service.apply_face_match(
                db, session, student_id, score, margin
            )
            if result_code in {"present", "late", "no_downgrade", "already_excused"}:
                change = {
                    "student_id": student_id, "status": record.status.value,
                    "result": result_code, "hit_count": record.hit_count,
                }
                attendance_changes.append(change)
        faces.append({
            "box": asdict(match.box), "student_id": student_id, "status": log_status.value,
            "score": score, "margin": margin, "attendance_change": change,
        })

    # This also resets absent students when there are zero faces, unknown faces,
    # or only other students in the frame. Never change the attendance status here.
    attendance_service.reset_missing_face_hits(db, session, matched_ids)
    response = {
        "engine": engine.name, "ready": True,
        "faces": faces, "attendance_changes": attendance_changes,
    }
    db.add(RecognitionFrame(
        session_id=session.id, frame_id=frame_id, content_hash=content_hash, response=response,
    ))
    db.commit()
    return response



def recognition_feed(db: Session, session_id: int) -> dict:
    logs = (
        db.query(RecognitionLog)
        .filter(RecognitionLog.session_id == session_id)
        .order_by(RecognitionLog.frame_at.desc())
        .limit(50)
        .all()
    )
    needs_confirmation = [
        row
        for row in logs
        if row.status
        in {RecognitionStatus.unknown, RecognitionStatus.ambiguous, RecognitionStatus.low_quality}
    ]
    return {"needs_confirmation": needs_confirmation, "logs": logs}
