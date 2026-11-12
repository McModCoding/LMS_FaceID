"""M7 gradebook: authorization, sources and one shared calculation."""
from datetime import UTC
from decimal import Decimal
from io import BytesIO

from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.class_ import Class, ClassStudent, ClassStudentStatus
from app.models.exam import Exam, ExamQuestion
from app.models.exam_attempt import ExamAttempt
from app.models.grade import Grade, GradeComponent, GradePublication
from app.models.learning import Assignment, Submission
from app.models.session import Session as Lesson
from app.models.session import SessionStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.grade import GradeComponentIn, ManualGradeIn
from app.services.attendance_score import calculate_attendance_score
from app.services.audit_service import log_action
from app.services.exam_review_service import _selected
from app.services.grade_calculation import normalize_score, weighted_total
from app.services.learning_access import (
    ensure_class_manager,
    ensure_class_writable,
    get_class_or_404,
    get_enrolled_student,
)
from app.utils.clock import now_local


def fail(code, message, status=422):
    raise HTTPException(status, detail={"code": code, "message": message})


def managed(db: Session, user: User, class_id: int, writable=False):
    cls = db.query(Class).filter_by(id=class_id).populate_existing().with_for_update().first()
    get_class_or_404(db, class_id)
    ensure_class_manager(db, user, class_id)
    if writable:
        ensure_class_writable(db, class_id)
    return cls


def components(db, class_id, *, locking=False):
    query = db.query(GradeComponent).filter_by(class_id=class_id).order_by(GradeComponent.id)
    return query.populate_existing().with_for_update().all() if locking else query.all()


def source(db, component):
    if component.type == "assignment":
        return db.get(Assignment, component.ref_id)
    if component.type == "exam":
        return db.get(Exam, component.ref_id)
    return None


def component_out(db, component):
    original = source(db, component)
    return {"id": component.id, "name": component.name, "type": component.type,
        "weight": component.weight, "ref_id": component.ref_id,
        "source_name": original.title if original else {"attendance": "Các buổi đã đóng", "manual": "Giảng viên nhập tay"}.get(component.type, "Nguồn không còn tồn tại")}


def save_component(db, user, class_id, data: GradeComponentIn, component_id=None):
    managed(db, user, class_id, writable=True)
    original = None
    if data.type in ("assignment", "exam"):
        original = db.get(Assignment if data.type == "assignment" else Exam, data.ref_id)
        if not original or original.class_id != class_id or original.status.value == "draft":
            fail("INVALID_GRADE_SOURCE", "Chọn bài tập hoặc đề kiểm tra đã công bố thuộc đúng lớp.")
    row = db.query(GradeComponent).filter_by(id=component_id, class_id=class_id).populate_existing().with_for_update().first() if component_id else None
    if component_id and not row:
        fail("COMPONENT_NOT_FOUND", "Không tìm thấy thành phần điểm.", 404)
    if row and (row.type != data.type or row.ref_id != data.ref_id):
        fail("GRADE_SOURCE_LOCKED", "Muốn đổi loại hoặc nguồn, hãy xóa thành phần và tạo lại.", 409)
    old = {"name": row.name, "weight": str(row.weight)} if row else None
    if not row:
        row = GradeComponent(class_id=class_id)
        db.add(row)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.flush()
    log_action(db, user.id, "SAVE_GRADE_COMPONENT", "grade_components", str(row.id),
        {"old": old, "new": data.model_dump(mode="json")})
    db.commit()
    return component_out(db, row)


def delete_component(db, user, class_id, component_id):
    managed(db, user, class_id, writable=True)
    row = db.query(GradeComponent).filter_by(id=component_id, class_id=class_id).populate_existing().with_for_update().first()
    if not row:
        fail("COMPONENT_NOT_FOUND", "Không tìm thấy thành phần điểm.", 404)
    log_action(db, user.id, "DELETE_GRADE_COMPONENT", "grade_components", str(row.id), {"class_id": class_id, "name": row.name, "weight": str(row.weight)})
    db.delete(row)
    db.commit()


def set_manual(db, user, class_id, component_id, student_id, data: ManualGradeIn):
    managed(db, user, class_id, writable=True)
    component = db.query(GradeComponent).filter_by(id=component_id, class_id=class_id).populate_existing().with_for_update().first()
    if not component or component.type != "manual":
        fail("NOT_MANUAL_COMPONENT", "Chỉ nhập điểm cho thành phần nhập tay.")
    enrollment = db.query(ClassStudent).filter_by(class_id=class_id, student_id=student_id).first()
    if not enrollment:
        fail("NOT_CLASS_STUDENT", "Sinh viên không thuộc lớp học phần.")
    row = db.query(Grade).filter_by(component_id=component_id, student_id=student_id).populate_existing().with_for_update().first()
    old = row.score if row else None
    if not row:
        row = Grade(component_id=component_id, student_id=student_id)
        db.add(row)
    row.score, row.updated_by = data.score, user.id
    log_action(db, user.id, "UPDATE_MANUAL_GRADE", "grade_components", str(component_id),
        {"student_id": student_id, "old": str(old), "new": str(data.score)})
    db.commit()


def score_reader(db, cls, rows, student_ids):
    """Batch source reads once per page/export, independent of row count."""
    manual_ids = [r.id for r in rows if r.type == 'manual']
    assignment_ids = [r.ref_id for r in rows if r.type == 'assignment']
    exam_ids = [r.ref_id for r in rows if r.type == 'exam']
    manual = {(r.component_id, r.student_id): r.score for r in db.query(Grade).filter(
        Grade.component_id.in_(manual_ids), Grade.student_id.in_(student_ids)).all()} if manual_ids else {}
    attendance = {}
    if any(r.type == 'attendance' for r in rows):
        records = db.query(AttendanceRecord).join(Lesson, Lesson.id == AttendanceRecord.session_id).filter(
            Lesson.class_id == cls.id, Lesson.status == SessionStatus.closed, AttendanceRecord.student_id.in_(student_ids)).all()
        counts = {}
        for record in records:
            own = counts.setdefault(record.student_id, {'present': 0, 'late': 0, 'excused': 0, 'total': 0})
            own['total'] += 1
            if record.status.value in ('present', 'late', 'excused'):
                own[record.status.value] += 1
        for sid, own in counts.items():
            attendance[sid] = calculate_attendance_score(present_count=own['present'], late_count=own['late'],
                excused_count=own['excused'], total_count=own['total'], weight_present=cls.weight_present,
                weight_late=cls.weight_late, weight_excused=cls.weight_excused)
    assignments = {r.id: r for r in db.query(Assignment).filter(Assignment.id.in_(assignment_ids)).all()} if assignment_ids else {}
    submissions = {(r.assignment_id, r.student_id): r for r in db.query(Submission).filter(
        Submission.assignment_id.in_(assignment_ids), Submission.student_id.in_(student_ids)).all()} if assignment_ids else {}
    exams = {r.id: r for r in db.query(Exam).filter(Exam.id.in_(exam_ids)).all()} if exam_ids else {}
    attempts = {}
    points = {}
    if exam_ids:
        for attempt in db.query(ExamAttempt).filter(ExamAttempt.exam_id.in_(exam_ids), ExamAttempt.student_id.in_(student_ids)).all():
            attempts.setdefault((attempt.exam_id, attempt.student_id), []).append(attempt)
        for question in db.query(ExamQuestion).filter(ExamQuestion.exam_id.in_(exam_ids)).all():
            if question.frozen_content:
                points[question.exam_id] = points.get(question.exam_id, Decimal(0)) + Decimal(question.frozen_content['points'])
    def score(component, student_id):
        if component.type == 'manual':
            return manual.get((component.id, student_id))
        if component.type == 'attendance':
            return attendance.get(student_id)
        original = (assignments if component.type == 'assignment' else exams).get(component.ref_id)
        if not original or original.class_id != cls.id or original.status.value == 'draft':
            return None
        if component.type == 'assignment':
            row = submissions.get((original.id, student_id))
            try:
                return normalize_score(Decimal(str(row.score)) if row and row.score is not None else None, Decimal(str(original.max_score)))
            except ValueError:
                fail('INVALID_SOURCE_SCORE', f'Điểm bài tập “{original.title}” không phù hợp điểm tối đa. Giảng viên cần kiểm tra lại nguồn điểm.')
        chosen = _selected(original, attempts.get((original.id, student_id), []))
        maximum = points.get(original.id)
        return normalize_score(chosen.score, maximum) if chosen and maximum else None
    return score


def gradebook(db, user, class_id, page=1, page_size=20):
    cls = get_class_or_404(db, class_id)
    student = get_enrolled_student(db, user, class_id) if user.role == UserRole.student else None
    if not student:
        ensure_class_manager(db, user, class_id)
    rows = components(db, class_id)
    weight = sum((r.weight for r in rows), Decimal(0))
    publication = db.query(GradePublication).filter_by(class_id=class_id).first()
    published = bool(publication) and weight == 100
    if student and not published:
        return {"published": False, "weight_total": None, "components": [], "items": [], "total": 0,
            "page": page, "page_size": page_size, "message": "Bảng điểm tổng hợp chưa được công bố. Điểm riêng từng bài xem tại Bài tập/Bài kiểm tra."}
    query = db.query(Student, ClassStudent.status).join(ClassStudent, ClassStudent.student_id == Student.id).filter(
        ClassStudent.class_id == class_id, Student.is_deleted.is_(False))
    if student:
        query = query.filter(Student.id == student.id)
    total = query.count()
    items = []
    people = query.order_by(Student.student_code).offset((page - 1) * page_size).limit(page_size).all()
    score = score_reader(db, cls, rows, [person.id for person, _ in people])
    for person, status in people:
        values = [{"component_id": r.id, "score": score(r, person.id)} for r in rows]
        items.append({"student_id": person.id, "student_code": person.student_code, "student_name": person.full_name,
            "is_dropped": status == ClassStudentStatus.dropped, "values": values,
            "missing_count": sum(v["score"] is None for v in values),
            "total_score": weighted_total([(v["score"], r.weight) for v, r in zip(values, rows, strict=True)])})
    return {"published": published, "weight_total": weight, "components": [component_out(db, r) for r in rows], "items": items,
        "total": total, "page": page, "page_size": page_size, "message": "Điểm chưa có được tính 0 theo trọng số. Điểm tổng hợp độc lập với quyền xem kết quả chi tiết từng bài."}


def publish(db, user, class_id):
    managed(db, user, class_id, writable=True)
    rows = components(db, class_id, locking=True)
    if not rows or sum((r.weight for r in rows), Decimal(0)) != 100:
        fail("INVALID_TOTAL_WEIGHT", "Tổng trọng số phải đúng 100% để công bố.", 409)
    row = db.query(GradePublication).filter_by(class_id=class_id).populate_existing().with_for_update().first()
    if not row:
        row = GradePublication(class_id=class_id)
        db.add(row)
    row.published_at = now_local().astimezone(UTC).replace(tzinfo=None)
    row.published_by = user.id
    log_action(db, user.id, "PUBLISH_GRADEBOOK", "classes", str(class_id))
    db.commit()


def export(db, user, class_id):
    ensure_class_manager(db, user, class_id)
    data = gradebook(db, user, class_id, page_size=2147483647)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bảng điểm"
    def safe(value):
        return "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
    sheet.append(["MSSV", "Họ tên", *[safe(f"{r['name']} ({r['weight']}%)") for r in data["components"]], "Tổng kết", "Số điểm chưa có"])
    for row in data["items"]:
        sheet.append([safe(row["student_code"]), safe(row["student_name"]),
            *[float(v["score"]) if v["score"] is not None else "Chưa có" for v in row["values"]], float(row["total_score"]), row["missing_count"]])
    sources = workbook.create_sheet("Nguồn và cách tính")
    sources.append(["Thành phần", "Trọng số", "Nguồn"])
    for component in data["components"]:
        sources.append([safe(component["name"]), float(component["weight"]), safe(component["source_name"])])
    sources.append(["Chưa có tính 0; tổng kết HALF_UP một chữ số. Tổng trọng số", float(data["weight_total"])])
    log_action(db, user.id, "EXPORT_GRADEBOOK", "classes", str(class_id))
    db.commit()
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
