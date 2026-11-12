"""Exam review, result visibility, manual grading and aggregate statistics."""

from datetime import UTC
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.exam import Exam, ExamStatus, ScorePolicy, ShowResult
from app.models.exam_attempt import AttemptAnswer, AttemptStatus, ExamAttempt
from app.models.exam_event import ExamEvent
from app.models.student import Student
from app.models.user import User
from app.schemas.exam_management import EssayGradeIn
from app.services.audit_service import log_action
from app.services.exam_attempt_service import (
    GRACE,
    _finalize,
    _lock_class_and_student,
    _now,
    _owned_attempt,
    _snapshots,
)
from app.services.exam_lifecycle_service import managed_exam

TWO = Decimal("0.01")


def _utc(value):
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _total(db: Session, exam: Exam) -> Decimal:
    # Published exams use frozen points, never the mutable question bank.
    return sum((Decimal(row["points"]) for row in _snapshots(db, exam.id).values()), Decimal(0))


def _score10(score, total):
    return (score * 10 / total).quantize(TWO, rounding=ROUND_HALF_UP) if score is not None and total else None


def _summary(attempt: ExamAttempt, student: Student, total: Decimal) -> dict:
    return {"id": attempt.id, "student_id": student.id, "student_code": student.student_code,
            "student_name": student.full_name, "attempt_no": attempt.attempt_no,
            "status": attempt.status.value, "score": attempt.score, "score10": _score10(attempt.score, total),
            "submitted_at": _utc(attempt.submitted_at), "violation_count": attempt.violation_count,
            "is_auto_submitted": attempt.is_auto_submitted}


def _managed_attempt(db: Session, user: User, attempt_id: int, writable=False):
    lookup = db.get(ExamAttempt, attempt_id)
    if not lookup:
        raise HTTPException(404, detail={"code": "ATTEMPT_NOT_FOUND", "message": "Không tìm thấy lượt làm bài."})
    exam = managed_exam(db, user, lookup.exam_id, writable=writable)
    attempt = db.query(ExamAttempt).filter_by(id=attempt_id).populate_existing().with_for_update().one()
    if attempt.status == AttemptStatus.in_progress and _now() > attempt.deadline_at + GRACE:
        _finalize(db, attempt, automatic=True)
        db.flush()
    return exam, attempt


def _detail(db: Session, exam: Exam, attempt: ExamAttempt) -> dict:
    db.flush()
    snapshots = _snapshots(db, exam.id)
    answers = {row.question_id: row for row in db.query(AttemptAnswer).filter_by(attempt_id=attempt.id)
               .populate_existing().with_for_update().all()}
    total = sum((Decimal(row["points"]) for row in snapshots.values()), Decimal(0))
    result = _summary(attempt, db.get(Student, attempt.student_id), total)
    result.update(exam_id=exam.id, class_id=exam.class_id, exam_title=exam.title, total_points=total)
    questions = []
    for qid in attempt.question_order:
        snapshot = snapshots[qid]
        answer = answers.get(qid)
        by_id = {row["id"]: row for row in snapshot["options"]}
        questions.append({"question_id": qid, "content": snapshot["content"], "type": snapshot["type"],
            "points": snapshot["points"], "explanation": snapshot["explanation"],
            "options": [by_id[oid] for oid in attempt.option_order[str(qid)]],
            "selected_option_ids": answer.selected_option_ids if answer else None,
            "essay_text": answer.essay_text if answer else None,
            "score": answer.score if answer else None, "feedback": answer.feedback if answer else None})
    result["questions"] = questions
    return result


def review_attempt(db: Session, user: User, attempt_id: int) -> dict:
    exam, attempt = _managed_attempt(db, user, attempt_id)
    result = _detail(db, exam, attempt)
    db.commit()  # Preserve a lazy automatic submission if the review finalized it.
    return result


def grade_essay(db: Session, user: User, attempt_id: int, question_id: int, data: EssayGradeIn) -> dict:
    exam, attempt = _managed_attempt(db, user, attempt_id, writable=True)
    if attempt.status == AttemptStatus.in_progress:
        raise HTTPException(409, detail={"code": "ATTEMPT_IN_PROGRESS", "message": "Chỉ chấm được bài đã nộp."})
    snapshot = _snapshots(db, exam.id).get(question_id)
    if not snapshot or snapshot["type"] != "essay":
        raise HTTPException(422, detail={"code": "NOT_ESSAY", "message": "Chỉ chấm tay câu tự luận thuộc đề."})
    if data.score > Decimal(snapshot["points"]):
        raise HTTPException(422, detail={"code": "INVALID_SCORE", "message": "Điểm vượt quá điểm tối đa của câu."})
    answers = db.query(AttemptAnswer).filter_by(attempt_id=attempt.id).populate_existing().with_for_update().all()
    answer = next(row for row in answers if row.question_id == question_id)
    previous = answer.score
    answer.score, answer.feedback = data.score, data.feedback.strip() if data.feedback else None
    if all(row.score is not None for row in answers):
        attempt.score = sum((row.score for row in answers), Decimal(0))
        attempt.status = AttemptStatus.graded
    log_action(db, user.id, "GRADE_EXAM_ESSAY", "exam_attempts", str(attempt.id),
               {"question_id": question_id, "old_score": str(previous), "score": str(data.score)})
    db.flush()
    result = _detail(db, exam, attempt)
    db.commit()
    return result


def list_attempts(db: Session, user: User, exam_id: int, page: int, page_size: int,
                  state: str | None = None, student_id: int | None = None) -> dict:
    exam = managed_exam(db, user, exam_id)
    query = db.query(ExamAttempt).filter_by(exam_id=exam_id)
    if student_id:
        query = query.filter(ExamAttempt.student_id == student_id)
    if state == "in_progress":
        query = query.filter(ExamAttempt.status == AttemptStatus.in_progress)
    elif state == "pending_grading":
        query = query.filter(ExamAttempt.status.in_([AttemptStatus.submitted, AttemptStatus.auto_submitted]))
    elif state == "graded":
        query = query.filter(ExamAttempt.status == AttemptStatus.graded)
    total = query.count()
    attempts = query.order_by(ExamAttempt.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    students = {row.id: row for row in db.query(Student).filter(Student.id.in_([a.student_id for a in attempts])).all()}
    points = _total(db, exam) if exam.status != ExamStatus.draft else Decimal(0)
    return {"items": [_summary(a, students[a.student_id], points) for a in attempts],
            "total": total, "page": page, "page_size": page_size}


def _visible(exam: Exam) -> bool:
    return exam.show_result != ShowResult.never and (exam.show_result == ShowResult.after_submit
        or exam.status == ExamStatus.closed or _now() >= exam.close_at)


def _selected(exam: Exam, attempts: list[ExamAttempt]):
    if not attempts or any(a.status != AttemptStatus.graded or a.score is None for a in attempts):
        return None
    return max(attempts, key=lambda a: (a.score, a.attempt_no)) if exam.score_policy == ScorePolicy.highest else max(attempts, key=lambda a: a.attempt_no)


def student_results(db: Session, user: User, exam_id: int) -> dict:
    exam = db.get(Exam, exam_id)
    if not exam or exam.status == ExamStatus.draft:
        raise HTTPException(404, detail={"code": "EXAM_NOT_FOUND", "message": "Không tìm thấy bài kiểm tra."})
    student = _lock_class_and_student(db, user, exam.class_id)
    exam = db.query(Exam).filter_by(id=exam_id).populate_existing().with_for_update().one()
    attempts = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student.id).order_by(ExamAttempt.attempt_no).populate_existing().with_for_update().all()
    for attempt in attempts:
        if attempt.status == AttemptStatus.in_progress and _now() > attempt.deadline_at + GRACE:
            _finalize(db, attempt, automatic=True)
    visible = _visible(exam)
    chosen = _selected(exam, attempts) if visible else None
    total = _total(db, exam)
    result = {"exam_id": exam.id, "class_id": exam.class_id, "title": exam.title, "available": visible,
              "reason": "Kết quả theo quy định của bài kiểm tra." if visible else (
                  "Giảng viên không cho hiển thị kết quả." if exam.show_result == ShowResult.never else "Kết quả được hiển thị sau khi đề đóng."),
              "score_policy": exam.score_policy.value, "selected_attempt_id": chosen.id if chosen else None,
              "score10": _score10(chosen.score, total) if chosen else None,
              "attempts": [{"id": a.id, "attempt_no": a.attempt_no, "status": a.status.value,
                            "score10": _score10(a.score, total) if visible and a.status == AttemptStatus.graded else None,
                            "is_auto_submitted": a.is_auto_submitted} for a in attempts]}
    db.commit()
    return result


def student_attempt_result(db: Session, user: User, attempt_id: int) -> dict:
    attempt = _owned_attempt(db, user, attempt_id)
    exam = db.get(Exam, attempt.exam_id)
    if not _visible(exam):
        raise HTTPException(403, detail={"code": "RESULT_NOT_AVAILABLE", "message": "Chưa được phép xem điểm và đáp án của bài kiểm tra này."})
    if attempt.status == AttemptStatus.in_progress:
        if _now() > attempt.deadline_at + GRACE:
            _finalize(db, attempt, automatic=True)
        else:
            raise HTTPException(409, detail={"code": "ATTEMPT_IN_PROGRESS", "message": "Cần nộp bài trước khi xem kết quả."})
    result = _detail(db, exam, attempt)
    db.commit()
    return result


def event_list(db: Session, user: User, attempt_id: int, page: int, page_size: int):
    _managed_attempt(db, user, attempt_id)
    query = db.query(ExamEvent).filter_by(attempt_id=attempt_id)
    result = {"items": [{"id": row.id, "type": row.type, "occurred_at": _utc(row.occurred_at), "counted": row.counted}
                        for row in query.order_by(ExamEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)],
              "total": query.count(), "page": page, "page_size": page_size}
    db.commit()
    return result


def statistics(db: Session, user: User, exam_id: int, *, commit: bool = True) -> dict:
    exam = managed_exam(db, user, exam_id)
    if exam.status == ExamStatus.draft:
        raise HTTPException(409, detail={"code": "EXAM_NOT_PUBLISHED", "message": "Công bố đề trước khi xem thống kê."})
    attempts = db.query(ExamAttempt).filter_by(exam_id=exam_id).order_by(ExamAttempt.id).populate_existing().with_for_update().all()
    for attempt in attempts:
        if attempt.status == AttemptStatus.in_progress and _now() > attempt.deadline_at + GRACE:
            _finalize(db, attempt, automatic=True)
    snapshots = _snapshots(db, exam_id)
    db.flush()
    total = sum((Decimal(q["points"]) for q in snapshots.values()), Decimal(0))
    by_student = {}
    for a in attempts:
        by_student.setdefault(a.student_id, []).append(a)
    scores = [_score10(chosen.score, total) for own in by_student.values() if (chosen := _selected(exam, own))]
    finished_ids = [a.id for a in attempts if a.status != AttemptStatus.in_progress]
    answers = db.query(AttemptAnswer).filter(AttemptAnswer.attempt_id.in_(finished_ids)).all()
    question_stats = []
    for qid, q in snapshots.items():
        relevant = [a for a in answers if a.question_id == qid]
        objective = q["type"] != "essay"
        correct = sum(a.score == Decimal(q["points"]) for a in relevant) if objective else None
        question_stats.append({"question_id": qid, "content": q["content"], "type": q["type"],
            "total": len(relevant), "correct": correct,
            "correct_rate": Decimal(correct) / len(relevant) if objective and relevant else None})
    enrolled = db.query(Student).join(ClassStudent, ClassStudent.student_id == Student.id).filter(
        ClassStudent.class_id == exam.class_id, ClassStudent.status == ClassStudentStatus.enrolled,
        Student.is_deleted.is_(False)).order_by(Student.student_code).all()
    histogram = [{"label": f"{i}–{i + 1}" if i < 9 else "9–10", "count": sum(i <= score < i + 1 or (i == 9 and score == 10) for score in scores)} for i in range(10)]
    result = {"exam_id": exam.id, "score_policy": exam.score_policy.value,
        "in_progress": sum(a.status == AttemptStatus.in_progress for a in attempts),
        "submitted": len(finished_ids), "pending_grading": sum(a.status in (AttemptStatus.submitted, AttemptStatus.auto_submitted) for a in attempts),
        "graded_students": len(scores), "average": (sum(scores) / len(scores)).quantize(TWO, rounding=ROUND_HALF_UP) if scores else None,
        "highest": max(scores) if scores else None, "lowest": min(scores) if scores else None,
        "histogram": histogram, "questions": question_stats,
        "not_started": [{"student_id": s.id, "student_code": s.student_code, "student_name": s.full_name} for s in enrolled if s.id not in by_student]}
    if commit:
        db.commit()
    return result


def export_results(db: Session, user: User, exam_id: int) -> BytesIO:
    exam = managed_exam(db, user, exam_id)
    stats = statistics(db, user, exam_id, commit=False)
    rows = list_attempts(db, user, exam_id, 1, 2147483647)["items"]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lượt làm"
    sheet.append(["MSSV", "Họ tên", "Lượt", "Trạng thái", "Điểm gốc", "Điểm thang 10", "Sự kiện tính ngưỡng", "Tự nộp"])
    labels = {"in_progress": "Đang làm", "submitted": "Chờ chấm", "auto_submitted": "Tự nộp, chờ chấm", "graded": "Đã chấm"}
    def safe(value):
        return "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
    for row in rows:
        sheet.append([safe(row["student_code"]), safe(row["student_name"]), row["attempt_no"], labels[row["status"]],
                      float(row["score"]) if row["score"] is not None else None,
                      float(row["score10"]) if row["score10"] is not None else None,
                      row["violation_count"], "Có" if row["is_auto_submitted"] else "Không"])
    missing = workbook.create_sheet("Chưa làm")
    missing.append(["MSSV", "Họ tên"])
    for student in stats["not_started"]:
        missing.append([safe(student["student_code"]), safe(student["student_name"])])
    summary = workbook.create_sheet("Thống kê")
    for key, label in [("graded_students", "Sinh viên có điểm hoàn tất"), ("average", "Trung bình"), ("highest", "Cao nhất"), ("lowest", "Thấp nhất")]:
        summary.append([label, float(stats[key]) if stats[key] is not None else None])
    for item in stats["histogram"]:
        summary.append([item["label"], item["count"]])
    questions = workbook.create_sheet("Câu hỏi")
    questions.append(["Câu hỏi", "Loại", "Số bài nộp", "Đúng hoàn toàn", "Tỷ lệ đúng hoàn toàn"])
    for row in stats["questions"]:
        questions.append([safe(row["content"]), row["type"], row["total"], row["correct"], float(row["correct_rate"]) if row["correct_rate"] is not None else None])
    log_action(db, user.id, "EXPORT_EXAM_RESULTS", "exams", str(exam.id))
    db.commit()
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
