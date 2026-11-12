from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from threading import Barrier

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord, AttendanceSource, AttendanceStatus
from app.models.audit import AuditLog
from app.models.class_ import ClassStatus, ClassStudent, ClassStudentStatus
from app.models.grade import Grade
from app.models.learning import Assignment, AssignmentStatus, Submission
from app.models.lecturer import Lecturer
from app.models.session import Session as Lesson
from app.models.session import SessionStatus
from app.models.student import Student
from app.models.user import User
from app.schemas.grade import ManualGradeIn
from app.services.grade_service import set_manual
from app.utils.clock import override_clock
from tests.test_m4_m5 import _admin, _learning_data, _token
from tests.test_phase2_exams import OPEN, answer_and_submit, begin, setup_exam


def test_manual_grade_publication_permissions_and_weight(test_client, db_session):
    cls, teacher, student = _learning_data(db_session)
    _, foreign, _ = _learning_data(db_session)
    url = f"/api/v1/classes/{cls.id}/gradebook"
    data = {"name": "Điểm nhập tay", "weight": "100", "type": "manual", "ref_id": None}
    assert test_client.post(url + "/components", headers=_token(student), json=data).status_code == 403
    assert test_client.get(url, headers=_token(foreign)).status_code == 403
    assert test_client.post(url + "/publish", headers=_token(teacher)).status_code == 409
    created = test_client.post(url + "/components", headers=_token(teacher), json=data)
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    rows = test_client.get(url, headers=_token(teacher)).json()
    sid = rows["items"][0]["student_id"]
    mark_url = f"{url}/components/{cid}/students/{sid}"
    assert test_client.put(mark_url, headers=_token(teacher), json={"score": 11}).status_code == 422
    assert test_client.put(mark_url, headers=_token(teacher), json={"score": "8.25"}).status_code == 204
    hidden = test_client.get(url, headers=_token(student)).json()
    assert not hidden["published"] and not hidden["items"] and not hidden["components"]
    assert test_client.post(url + "/publish", headers=_token(teacher)).status_code == 204
    visible = test_client.get(url, headers=_token(student)).json()
    assert visible["total"] == 1 and visible["items"][0]["total_score"] == "8.3"
    assert test_client.get(url + "/export", headers=_token(student)).status_code == 403
    assert test_client.get(url + "/export", headers=_token(teacher)).status_code == 200
    assert test_client.put(mark_url, headers=_token(teacher), json={"score": "9"}).status_code == 204
    assert test_client.get(url, headers=_token(student)).json()["items"][0]["total_score"] == "9.0"
    assert db_session.query(AuditLog).filter_by(action="UPDATE_MANUAL_GRADE", entity_id=str(cid)).count() == 2
    person = db_session.get(Student, sid)
    person.full_name = "=HYPERLINK(\"bad\")"
    db_session.commit()
    wb = load_workbook(BytesIO(test_client.get(url + "/export", headers=_token(teacher)).content))
    assert wb["Bảng điểm"].cell(2, 2).value.startswith("'=")
    db_session.refresh(cls)
    cls.status = ClassStatus.closed
    db_session.commit()
    assert test_client.put(mark_url, headers=_token(teacher), json={"score": "7"}).status_code == 409
    assert test_client.post(url + "/components", headers=_token(teacher), json=data).status_code == 409
    assert test_client.get(url, headers=_token(teacher)).status_code == 200


def test_real_sources_acceptance_83_excel_and_foreign_reference(test_client, db_session):
    cls, teacher, student, eid, questions, _ = setup_exam(test_client, db_session)
    sid = db_session.query(Student).filter_by(user_id=student.id).one().id
    with override_clock(OPEN):
        attempt = begin(test_client, student, eid)
        answer_and_submit(test_client, student, attempt, questions)
        graded = test_client.post(f"/api/v1/attempts/{attempt['id']}/questions/{questions[-1]['id']}/grade", headers=_token(teacher), json={"score": "1.5"})
        assert graded.status_code == 200, graded.text
        for i in range(5):
            lesson = Lesson(class_id=cls.id, session_no=i + 1, date=OPEN.date() - timedelta(days=i), start_time=OPEN.time().replace(tzinfo=None), end_time=(OPEN + timedelta(hours=1)).time().replace(tzinfo=None), room="M7", status=SessionStatus.closed)
            db_session.add(lesson)
            db_session.flush()
            db_session.add(AttendanceRecord(session_id=lesson.id, student_id=sid, status=AttendanceStatus.present if i < 4 else AttendanceStatus.absent, source=AttendanceSource.manual))
        assignment = Assignment(class_id=cls.id, title="Bài 20 điểm", max_score=20, status=AssignmentStatus.published, due_at=OPEN.replace(tzinfo=None))
        db_session.add(assignment)
        db_session.flush()
        db_session.add(Submission(assignment_id=assignment.id, student_id=sid, score=14, is_late=False, submitted_at=OPEN.replace(tzinfo=None)))
        db_session.commit()
        base = f"/api/v1/classes/{cls.id}/gradebook"
        for kind, weight, ref in [("attendance", 10, None), ("assignment", 30, assignment.id), ("exam", 60, eid)]:
            res = test_client.post(base + "/components", headers=_token(teacher), json={"name": kind, "weight": weight, "type": kind, "ref_id": ref})
            assert res.status_code == 201, res.text
        foreign, other, _ = _learning_data(db_session)
        bad = test_client.post(f"/api/v1/classes/{foreign.id}/gradebook/components", headers=_token(other), json={"name": "Sai lớp", "weight": 100, "type": "assignment", "ref_id": assignment.id})
        assert bad.status_code == 422
        data = test_client.get(base, headers=_token(teacher)).json()
        assert data["items"][0]["total_score"] == "8.3"
        assert [Decimal(v["score"]) for v in data["items"][0]["values"]] == [Decimal(8), Decimal(7), Decimal(9)]
        wb = load_workbook(BytesIO(test_client.get(base + "/export", headers=_token(teacher)).content))
        assert wb["Bảng điểm"].cell(2, 6).value == 8.3
        assert test_client.post(base + "/publish", headers=_token(teacher)).status_code == 204
        submission = db_session.query(Submission).filter_by(assignment_id=assignment.id, student_id=sid).one()
        changed = test_client.post(f"/api/v1/submissions/{submission.id}/grade", headers=_token(teacher), json={"score": 13, "feedback": "Chấm lại"})
        assert changed.status_code == 200, changed.text
        assert db_session.query(AuditLog).filter_by(action="GRADE_ASSIGNMENT", entity_id=str(submission.id)).count() == 1
        db_session.refresh(assignment)
        assignment.max_score = 10
        db_session.commit()
        invalid = test_client.get(base, headers=_token(teacher))
        assert invalid.status_code == 422 and invalid.json()["detail"]["code"] == "INVALID_SOURCE_SCORE"
        assignment.max_score = 20
        db_session.commit()
        resubmit = test_client.post(f"/api/v1/assignments/{assignment.id}/submissions", headers=_token(student), json={"text": "Nộp lại bài sau công bố"})
        assert resubmit.status_code == 200, resubmit.text
        assert db_session.query(AuditLog).filter_by(action="RESET_ASSIGNMENT_GRADE", entity_id=str(submission.id)).count() == 1
        component = data["components"][0]
        assert test_client.put(base + f"/components/{component['id']}", headers=_token(teacher), json={"name": "Chuyên cần sửa", "type": "attendance", "weight": 9, "ref_id": None}).status_code == 200
        assert not test_client.get(base, headers=_token(student)).json()["published"]
        assert db_session.query(AuditLog).filter_by(action="SAVE_GRADE_COMPONENT", entity_id=str(component["id"])).count() == 2
        enrollment = db_session.query(ClassStudent).filter_by(class_id=cls.id, student_id=sid).one()
        enrollment.status = ClassStudentStatus.dropped
        db_session.commit()
        assert test_client.get(base, headers=_token(student)).status_code == 403


def test_dashboard_scoped_counts_and_tasks_without_today_schedule(test_client, db_session):
    cls, teacher, student = _learning_data(db_session)
    foreign, _, _ = _learning_data(db_session)
    with override_clock(OPEN):
        db_session.add(Assignment(class_id=cls.id, title="Cần nộp dù không có lịch", due_at=(OPEN + timedelta(days=1)).replace(tzinfo=None), max_score=10, status=AssignmentStatus.published))
        db_session.add(Assignment(class_id=foreign.id, title="Không được thấy", due_at=(OPEN + timedelta(days=1)).replace(tzinfo=None), max_score=10, status=AssignmentStatus.published))
        db_session.commit()
        assert test_client.get("/api/v1/me/dashboard").status_code == 401
        for user in (student, teacher):
            res = test_client.get("/api/v1/me/dashboard", headers=_token(user))
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["class_count"] == 1
            assert all(g["count"] == len(g["items"]) for g in data["groups"])
            assert "Không được thấy" not in res.text
        student_data = test_client.get("/api/v1/me/dashboard", headers=_token(student)).json()
        assert student_data["groups"][0]["count"] == 0
        assert any(g["title"] == "Bài tập cần nộp" and g["count"] == 1 for g in student_data["groups"])
        from uuid import uuid4
        admin = _admin(db_session, uuid4().hex[:8])
        admin_data = test_client.get("/api/v1/me/dashboard", headers=_token(admin)).json()
        assert admin_data["administrative"]["Sinh viên"] == db_session.query(Student).filter_by(is_deleted=False).count()
        assert admin_data["administrative"]["Giảng viên"] == db_session.query(Lecturer).filter_by(is_deleted=False).count()
        db_session.refresh(cls)
        cls.status = ClassStatus.closed
        db_session.commit()
        closed = test_client.get("/api/v1/me/dashboard", headers=_token(student)).json()
        assert all(g["count"] == 0 for g in closed["groups"] if g["title"] in ("Bài tập cần nộp", "Kiểm tra cần theo dõi"))


def test_concurrent_manual_grades_use_current_reads(test_client, db_session, test_engine):
    cls, teacher, student = _learning_data(db_session)
    base = f"/api/v1/classes/{cls.id}/gradebook"
    result = test_client.post(base + "/components", headers=_token(teacher), json={"name": "Đồng thời", "weight": 100, "type": "manual", "ref_id": None})
    assert result.status_code == 201
    component_id, class_id, user_id = result.json()["id"], cls.id, teacher.id
    student_id = db_session.query(Student).filter_by(user_id=student.id).one().id
    barrier = Barrier(4)
    def worker(score):
        with Session(test_engine) as db:
            user = db.get(User, user_id)
            assert db.query(Grade).filter_by(component_id=component_id).count() == 0
            barrier.wait(timeout=10)
            set_manual(db, user, class_id, component_id, student_id, ManualGradeIn(score=score))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(worker, [1, 2, 3, 4]))
    with Session(test_engine) as db:
        assert db.query(Grade).filter_by(component_id=component_id, student_id=student_id).count() == 1
        audit = db.query(AuditLog).filter_by(action="UPDATE_MANUAL_GRADE", entity_id=str(component_id)).order_by(AuditLog.id).all()
        assert len(audit) == 4 and audit[0].detail["old"] == "None"
        for previous, current in zip(audit, audit[1:], strict=False):
            assert Decimal(previous.detail["new"]) == Decimal(current.detail["old"])

def test_dashboard_next_session_and_class_ids_are_scoped(test_client, db_session):
    from datetime import time

    from app.models.session import Session as Lesson
    from app.models.session import SessionStatus
    cls, _, student = _learning_data(db_session)
    foreign, _, _ = _learning_data(db_session)
    with override_clock(OPEN):
        db_session.add_all([
            Lesson(class_id=cls.id, session_no=1, date=(OPEN + timedelta(days=1)).date(), start_time=time(8), end_time=time(10), room="A1", status=SessionStatus.scheduled),
            Lesson(class_id=foreign.id, session_no=1, date=OPEN.date(), start_time=time(8), end_time=time(10), room="B1", status=SessionStatus.scheduled),
            Assignment(class_id=cls.id, title="Hạn sắp tới", due_at=(OPEN + timedelta(days=1)).replace(tzinfo=None), max_score=10, status=AssignmentStatus.published),
        ])
        db_session.commit()
        data = test_client.get('/api/v1/me/dashboard', headers=_token(student)).json()
        assert data['next_session']['class_id'] == cls.id
        assert data['next_session']['room'] == 'A1'
        assert [entry['id'] for entry in data['classes']] == [cls.id]
        item = next(group for group in data['groups'] if group['title'] == 'Bài tập cần nộp')['items'][0]
        assert item['class_id'] == cls.id
