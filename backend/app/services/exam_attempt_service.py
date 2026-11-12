"""Server-authoritative attempt lifecycle and student-safe payloads."""

from datetime import UTC, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.class_ import Class, ClassStudent, ClassStudentStatus
from app.models.exam import Exam, ExamQuestion, ExamStatus
from app.models.exam_attempt import AttemptAnswer, AttemptStatus, ExamAttempt
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.exam_content_service import (
    freeze_exam_content,
    score_answer,
    shuffled_ids,
    student_question,
)
from app.services.learning_access import ensure_class_writable
from app.utils.clock import now_local

GRACE = timedelta(seconds=settings.EXAM_GRACE_SECONDS)


def _now():
    return now_local().astimezone(UTC).replace(tzinfo=None)


def _error(code: str, message: str, status: int = 409):
    raise HTTPException(status, detail={"code": code, "message": message})


def list_student_exams(db: Session, user: User, class_id: int, page: int, page_size: int) -> dict:
    """Return only published exam metadata and the requesting student's own attempt state."""
    if user.role != UserRole.student:
        _error("FORBIDDEN", "Chỉ sinh viên mới được xem bài kiểm tra của mình.", 403)
    student = db.query(Student).filter(Student.user_id == user.id, Student.is_deleted.is_(False)).first()
    if not student:
        _error("FORBIDDEN", "Không tìm thấy hồ sơ sinh viên.", 403)
    cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted.is_(False)).first()
    if not cls:
        _error("CLASS_NOT_FOUND", "Không tìm thấy lớp học phần.", 404)
    enrolled = db.query(ClassStudent.id).filter(
        ClassStudent.class_id == class_id,
        ClassStudent.student_id == student.id,
        ClassStudent.status == ClassStudentStatus.enrolled,
    ).first()
    if not enrolled:
        _error("NOT_ENROLLED", "Bạn không còn thuộc lớp học phần này.", 403)

    query = db.query(Exam).filter(Exam.class_id == class_id, Exam.status.in_([ExamStatus.published, ExamStatus.closed]))
    total = query.count()
    exams = query.order_by(Exam.open_at, Exam.id).offset((page - 1) * page_size).limit(page_size).all()
    if not exams:
        return {"items": [], "total": total, "page": page, "page_size": page_size}

    exam_ids = [exam.id for exam in exams]
    attempts = (db.query(ExamAttempt).filter(
        ExamAttempt.student_id == student.id, ExamAttempt.exam_id.in_(exam_ids)
    ).order_by(ExamAttempt.exam_id, ExamAttempt.attempt_no).all())
    attempts_by_exam: dict[int, list[ExamAttempt]] = {exam_id: [] for exam_id in exam_ids}
    for attempt in attempts:
        attempts_by_exam[attempt.exam_id].append(attempt)
    question_counts = dict(db.query(ExamQuestion.exam_id, func.count(ExamQuestion.id))
        .filter(ExamQuestion.exam_id.in_(exam_ids)).group_by(ExamQuestion.exam_id).all())

    now = _now()
    items = []
    for exam in exams:
        own_attempts = attempts_by_exam[exam.id]
        active = next((item for item in reversed(own_attempts) if item.status == AttemptStatus.in_progress), None)
        if exam.status == ExamStatus.closed:
            state = "closed"
        elif active:
            state = "in_progress"
        elif now < exam.open_at:
            state = "upcoming"
        elif now >= exam.close_at:
            state = "closed"
        elif len(own_attempts) >= exam.max_attempts:
            state = "completed"
        else:
            state = "retry_available" if own_attempts else "available"
        items.append({
            "id": exam.id, "title": exam.title, "description": exam.description,
            "duration_min": exam.duration_min, "open_at": exam.open_at, "close_at": exam.close_at,
            "max_attempts": exam.max_attempts, "used_attempts": len(own_attempts),
            "question_count": question_counts.get(exam.id, 0), "require_fullscreen": exam.require_fullscreen,
            "record_events": exam.record_events, "violation_types": exam.violation_types,
            "max_violations": exam.max_violations, "auto_submit_on_violation": exam.auto_submit_on_violation,
            "active_attempt_id": active.id if active else None, "status": state,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _lock_class_and_student(db: Session, user: User, class_id: int) -> Student:
    # Class lock follows enrollment_service's lock order, including withdrawal.
    cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted.is_(False)).with_for_update().first()
    if not cls:
        _error("CLASS_NOT_FOUND", "Không tìm thấy lớp học phần.", 404)
    student = (db.query(Student).filter(Student.user_id == user.id, Student.is_deleted.is_(False)).first()
               if user.role == UserRole.student else None)
    enrolled = student and db.query(ClassStudent.id).filter(
        ClassStudent.class_id == class_id, ClassStudent.student_id == student.id,
        ClassStudent.status == ClassStudentStatus.enrolled).with_for_update().first()
    if not enrolled:
        _error("NOT_ENROLLED", "Bạn không còn thuộc lớp học phần này.", 403)
    return student


def _snapshots(db: Session, exam_id: int) -> dict[int, dict]:
    # Locking reads observe committed content even after a REPEATABLE READ view
    # was established before another transaction froze the exam.
    rows = (db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.order_no).populate_existing().with_for_update().all())
    if not rows or any(row.frozen_content is None for row in rows):
        _error("EXAM_SNAPSHOT_INCOMPLETE", "Dữ liệu đề chưa được cố định.")
    return {row.question_id: row.frozen_content for row in rows}


def begin_attempt(db: Session, user: User, exam_id: int) -> ExamAttempt:
    lookup = db.get(Exam, exam_id)
    if lookup is None:
        _error("EXAM_NOT_FOUND", "Không tìm thấy bài kiểm tra.", 404)
    student = _lock_class_and_student(db, user, lookup.class_id)
    ensure_class_writable(db, lookup.class_id)
    exam = db.query(Exam).filter(Exam.id == exam_id).populate_existing().with_for_update().first()
    if exam.status != ExamStatus.published:
        _error("EXAM_NOT_PUBLISHED", "Bài kiểm tra chưa được công bố.")
    attempts = (db.query(ExamAttempt).filter(ExamAttempt.exam_id == exam.id,
        ExamAttempt.student_id == student.id).order_by(ExamAttempt.attempt_no)
        .populate_existing().with_for_update().all())
    current = next((row for row in attempts if row.status == AttemptStatus.in_progress), None)
    if current:
        if _now() > current.deadline_at + GRACE:
            _finalize(db, current, automatic=True)
            db.commit()
            # Recheck the exam window and attempt limit under fresh locks. The
            # expired attempt is no longer resumable, but must stay persisted
            # even if a new attempt is forbidden.
            return begin_attempt(db, user, exam_id)
        return current
    now = _now()
    if not exam.open_at <= now < exam.close_at:
        _error("EXAM_CLOSED", "Bài kiểm tra chưa mở hoặc đã hết thời gian.")
    count = len(attempts)
    if count >= exam.max_attempts:
        _error("MAX_ATTEMPTS", "Bạn đã hết số lượt làm bài.")
    snapshots = freeze_exam_content(db, exam.id)
    attempt = ExamAttempt(exam_id=exam.id, student_id=student.id, attempt_no=count + 1,
        started_at=now, deadline_at=min(now + timedelta(minutes=exam.duration_min), exam.close_at),
        status=AttemptStatus.in_progress, question_order=[], option_order={}, violation_count=0,
        is_auto_submitted=False)
    db.add(attempt)
    db.flush()
    ids = [snapshot["question_id"] for snapshot in snapshots]
    attempt.question_order = shuffled_ids(ids, attempt.id) if exam.shuffle_questions else ids
    attempt.option_order = {str(row["question_id"]): (
        shuffled_ids([opt["id"] for opt in row["options"]], (attempt.id << 32) | row["question_id"])
        if exam.shuffle_options else [opt["id"] for opt in row["options"]]) for row in snapshots}
    db.commit()
    return attempt


def _owned_attempt(db: Session, user: User, attempt_id: int, *, writable: bool = False) -> ExamAttempt:
    lookup = db.get(ExamAttempt, attempt_id)
    if not lookup:
        _error("ATTEMPT_NOT_FOUND", "Không tìm thấy lượt làm bài.", 404)
    exam = db.get(Exam, lookup.exam_id)
    student = _lock_class_and_student(db, user, exam.class_id)
    if writable:
        ensure_class_writable(db, exam.class_id)
    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).populate_existing().with_for_update().first()
    if attempt.student_id != student.id:
        _error("FORBIDDEN", "Bạn không có quyền xem lượt làm bài này.", 403)
    return attempt


def _finalize(db: Session, attempt: ExamAttempt, automatic: bool) -> None:
    snapshots = _snapshots(db, attempt.exam_id)
    answers = {row.question_id: row for row in db.query(AttemptAnswer).filter_by(attempt_id=attempt.id)
               .populate_existing().with_for_update().all()}
    total = Decimal(0)
    needs_manual = False
    now = _now()
    for question_id, snapshot in snapshots.items():
        answer = answers.get(question_id)
        if answer is None:
            answer = AttemptAnswer(attempt_id=attempt.id, question_id=question_id,
                selected_option_ids=None, essay_text=None, saved_at=now)
            db.add(answer)
        answer.score = score_answer(snapshot, answer.selected_option_ids or [])
        if answer.score is None:
            needs_manual = True
        else:
            total += answer.score
    attempt.submitted_at = now
    attempt.is_auto_submitted = automatic
    attempt.status = (AttemptStatus.auto_submitted if automatic else AttemptStatus.submitted) if needs_manual else AttemptStatus.graded
    attempt.score = None if needs_manual else total


def _ensure_open(db: Session, attempt: ExamAttempt) -> None:
    if attempt.status != AttemptStatus.in_progress:
        _error("ATTEMPT_SUBMITTED", "Lượt làm bài đã được nộp.")
    if _now() > attempt.deadline_at + GRACE:
        _finalize(db, attempt, automatic=True)
        db.commit()  # Persist the automatic submission before returning an error.
        _error("ATTEMPT_EXPIRED", "Đã hết thời gian; bài đã được tự nộp.")


def save_answer(db: Session, user: User, attempt_id: int, question_id: int,
                selected_ids: list[int] | None, essay_text: str | None) -> None:
    attempt = _owned_attempt(db, user, attempt_id, writable=True)
    _ensure_open(db, attempt)
    snapshot = _snapshots(db, attempt.exam_id).get(question_id)
    if snapshot is None:
        _error("QUESTION_NOT_IN_EXAM", "Câu hỏi không thuộc bài kiểm tra.", 404)
    if (snapshot["type"] == "essay" and selected_ids) or (snapshot["type"] != "essay" and essay_text is not None):
        _error("INVALID_ANSWER", "Câu trả lời không phù hợp với loại câu hỏi.", 422)
    try:
        score_answer(snapshot, selected_ids or [])
    except ValueError:
        _error("INVALID_ANSWER", "Lựa chọn không hợp lệ.", 422)
    answer = (db.query(AttemptAnswer).filter_by(attempt_id=attempt.id, question_id=question_id)
              .populate_existing().with_for_update().first())
    if not answer:
        answer = AttemptAnswer(attempt_id=attempt.id, question_id=question_id, saved_at=_now())
        db.add(answer)
    answer.selected_option_ids = selected_ids if snapshot["type"] != "essay" else None
    answer.essay_text = essay_text if snapshot["type"] == "essay" else None
    answer.saved_at = _now()
    db.commit()


def submit_attempt(db: Session, user: User, attempt_id: int) -> ExamAttempt:
    attempt = _owned_attempt(db, user, attempt_id, writable=True)
    _ensure_open(db, attempt)
    _finalize(db, attempt, automatic=_now() >= attempt.deadline_at)
    db.commit()
    return attempt


def read_attempt(db: Session, user: User, attempt_id: int) -> dict:
    attempt = _owned_attempt(db, user, attempt_id)
    if attempt.status == AttemptStatus.in_progress and _now() > attempt.deadline_at + GRACE:
        _finalize(db, attempt, automatic=True)
        db.commit()
    snapshots = _snapshots(db, attempt.exam_id)
    answers = {row.question_id: row for row in db.query(AttemptAnswer).filter_by(attempt_id=attempt.id)
               .populate_existing().with_for_update().all()}
    questions = []
    for question_id in attempt.question_order:
        question = student_question(snapshots[question_id])
        by_id = {option["id"]: option for option in question["options"]}
        question["options"] = [by_id[oid] for oid in attempt.option_order[str(question_id)]]
        answer = answers.get(question_id)
        question["selected_option_ids"] = answer.selected_option_ids if answer else None
        question["essay_text"] = answer.essay_text if answer else None
        questions.append(question)
    exam = db.get(Exam, attempt.exam_id)
    return {"id": attempt.id, "exam_id": attempt.exam_id, "exam_title": exam.title,
            "class_id": exam.class_id, "record_events": exam.record_events,
            "violation_types": exam.violation_types, "max_violations": exam.max_violations,
            "auto_submit_on_violation": exam.auto_submit_on_violation,
            "violation_count": attempt.violation_count, "is_auto_submitted": attempt.is_auto_submitted,
            "require_fullscreen": exam.require_fullscreen, "attempt_no": attempt.attempt_no,
            "status": attempt.status.value, "started_at": attempt.started_at,
            "deadline_at": attempt.deadline_at, "server_now": _now(), "questions": questions}


def auto_submit_overdue(db: Session) -> int:
    """Idempotent periodic fallback; all times come from the shared business clock."""
    overdue = (db.query(ExamAttempt).filter(ExamAttempt.status == AttemptStatus.in_progress,
        ExamAttempt.deadline_at < _now() - GRACE).order_by(ExamAttempt.id).with_for_update().all())
    for attempt in overdue:
        _finalize(db, attempt, automatic=True)
    db.commit()
    return len(overdue)
