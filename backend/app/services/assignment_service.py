"""Assignment, submission, attachment, and grading rules for M5."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.class_ import ClassStatus
from app.models.learning import Assignment, AssignmentStatus, Submission
from app.models.user import User, UserRole
from app.services.audit_service import log_action
from app.services.learning_access import (
    ensure_class_manager,
    ensure_class_writable,
    get_class_or_404,
    get_enrolled_student,
)
from app.services.notification_service import add_notification, notify_enrolled_students
from app.utils.clock import now_local
from app.utils.uploads import remove_stored_file, store_upload, validate_upload


def _deadline_utc(value: datetime) -> datetime:
    """MySQL DATETIME stores UTC without an offset; restore it at the API boundary."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _assignment_values(data) -> dict:
    values = data.model_dump()
    values["due_at"] = data.due_at.astimezone(UTC).replace(tzinfo=None)
    return values


def assignment_out(assignment: Assignment, submission: Submission | None = None) -> dict:
    return {
        "id": assignment.id,
        "class_id": assignment.class_id,
        "title": assignment.title,
        "description": assignment.description,
        "due_at": _deadline_utc(assignment.due_at),
        "max_score": assignment.max_score,
        "allow_late": assignment.allow_late,
        "status": assignment.status,
        "created_at": assignment.created_at,
        "has_attachment": bool(assignment.attachment_path),
        "my_submission_id": submission.id if submission else None,
        "my_submitted_at": submission.submitted_at if submission else None,
        "my_is_late": submission.is_late if submission else None,
        "my_has_file": bool(submission.file_path) if submission else False,
        "my_score": submission.score if submission else None,
        "my_feedback": submission.feedback if submission else None,
    }


def submission_out(row: Submission) -> dict:
    return {
        "id": row.id,
        "assignment_id": row.assignment_id,
        "student_id": row.student_id,
        "student_code": row.student.student_code,
        "student_name": row.student.full_name,
        "text": row.text,
        "has_file": bool(row.file_path),
        "submitted_at": row.submitted_at,
        "is_late": row.is_late,
        "score": row.score,
        "feedback": row.feedback,
        "graded_at": row.graded_at,
    }


def list_assignments(db: Session, user: User, class_id: int, page: int, page_size: int, view: str = "all") -> dict:
    cls = get_class_or_404(db, class_id)
    is_student = user.role == UserRole.student
    student = get_enrolled_student(db, user, class_id) if is_student else None
    if not is_student:
        ensure_class_manager(db, user, class_id)
    query = db.query(Assignment).filter(Assignment.class_id == class_id)
    now_utc = now_local().astimezone(UTC)
    now_naive = now_utc.replace(tzinfo=None)
    if is_student:
        query = query.filter(Assignment.status == AssignmentStatus.published)
        submitted = db.query(Submission.id).filter(Submission.assignment_id == Assignment.id, Submission.student_id == student.id).exists()
        if view == "submitted":
            query = query.filter(submitted)
        elif view == "todo":
            query = query.filter(false()) if cls.status == ClassStatus.closed else query.filter(
                ~submitted, or_(Assignment.due_at >= now_naive, Assignment.allow_late.is_(True)))
        elif view == "finished":
            query = query.filter(~submitted) if cls.status == ClassStatus.closed else query.filter(
                ~submitted, Assignment.due_at < now_naive, Assignment.allow_late.is_(False))
        elif view != "all":
            raise HTTPException(422, detail="Bộ lọc không phù hợp với sinh viên.")
    elif view == "pending":
        ungraded = db.query(Submission.id).filter(Submission.assignment_id == Assignment.id, Submission.score.is_(None)).exists()
        query = query.filter(ungraded)
    elif view == "finished":
        if cls.status != ClassStatus.closed:
            query = query.filter(Assignment.due_at < now_naive, Assignment.allow_late.is_(False))
    elif view != "all":
        raise HTTPException(422, detail="Bộ lọc không phù hợp với giảng viên.")
    total = query.count()
    assignments = (
        query.order_by(Assignment.due_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    submissions = {}
    if student and assignments:
        submissions = {
            item.assignment_id: item
            for item in db.query(Submission)
            .filter(
                Submission.student_id == student.id,
                Submission.assignment_id.in_([assignment.id for assignment in assignments]),
            )
            .all()
        }
    pending = {}
    if not is_student and assignments:
        pending = dict(db.query(Submission.assignment_id, func.count(Submission.id)).filter(
            Submission.assignment_id.in_([assignment.id for assignment in assignments]),
            Submission.score.is_(None),
        ).group_by(Submission.assignment_id).all())
    output = []
    for assignment in assignments:
        submission = submissions.get(assignment.id)
        row = assignment_out(assignment, submission)
        row["availability"] = (
            "submitted" if submission else
            "closed" if cls.status == ClassStatus.closed else
            "open" if _deadline_utc(assignment.due_at) >= now_utc else
            "late_allowed" if assignment.allow_late else "closed"
        ) if is_student else None
        row["can_submit"] = (cls.status != ClassStatus.closed and (
            _deadline_utc(assignment.due_at) >= now_utc or assignment.allow_late
        )) if is_student else None
        row["pending_count"] = pending.get(assignment.id, 0) if not is_student else None
        output.append(row)
    return {
        "items": output,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def create_assignment(db: Session, user: User, class_id: int, data) -> Assignment:
    ensure_class_manager(db, user, class_id)
    ensure_class_writable(db, class_id)
    item = Assignment(class_id=class_id, **_assignment_values(data))
    db.add(item)
    db.commit()
    db.refresh(item)
    if item.status == AssignmentStatus.published:
        notify_enrolled_students(
            db,
            class_id,
            "assignment_published",
            "Bài tập mới",
            f"{item.title} đã được giao.",
            f"/student/classes/{class_id}",
        )
        db.commit()
    return item


def update_assignment(db: Session, user: User, assignment_id: int, data) -> Assignment:
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(
            404,
            detail={"code": "ASSIGNMENT_NOT_FOUND", "message": "Không tìm thấy bài tập."},
        )
    ensure_class_manager(db, user, item.class_id)
    ensure_class_writable(db, item.class_id)
    was_published = item.status == AssignmentStatus.published
    previous = {"max_score": item.max_score, "status": item.status.value}
    for field, value in _assignment_values(data).items():
        setattr(item, field, value)
    log_action(db, user.id, "UPDATE_ASSIGNMENT_GRADE_SOURCE", "assignments", str(item.id),
        {"old": previous, "new": {"max_score": item.max_score, "status": item.status.value}})
    db.commit()
    db.refresh(item)
    if not was_published and item.status == AssignmentStatus.published:
        notify_enrolled_students(
            db,
            item.class_id,
            "assignment_published",
            "Bài tập mới",
            f"{item.title} đã được giao.",
            f"/student/classes/{item.class_id}",
        )
        db.commit()
    return item


def delete_assignment(db: Session, user: User, assignment_id: int) -> None:
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(
            404,
            detail={"code": "ASSIGNMENT_NOT_FOUND", "message": "Không tìm thấy bài tập."},
        )
    ensure_class_manager(db, user, item.class_id)
    ensure_class_writable(db, item.class_id)
    if db.query(Submission.id).filter(Submission.assignment_id == item.id).first():
        raise HTTPException(
            409,
            detail={
                "code": "ASSIGNMENT_HAS_SUBMISSIONS",
                "message": "Không thể xóa bài tập đã có bài nộp.",
            },
        )
    attachment = item.attachment_path
    db.delete(item)
    db.commit()
    remove_stored_file(attachment)


def _get_published_assignment(db: Session, assignment_id: int) -> Assignment:
    item = db.get(Assignment, assignment_id)
    if not item or item.status != AssignmentStatus.published:
        raise HTTPException(
            404,
            detail={
                "code": "ASSIGNMENT_NOT_FOUND",
                "message": "Không tìm thấy bài tập đang được giao.",
            },
        )
    return item


def _submission_timing(item: Assignment) -> tuple[datetime, bool]:
    now = now_local()
    due_at = _deadline_utc(item.due_at)
    is_late = now > due_at
    if is_late and not item.allow_late:
        raise HTTPException(
            409,
            detail={"code": "ASSIGNMENT_CLOSED", "message": "Đã quá hạn nộp bài."},
        )
    return now, is_late


def _existing_submission(db: Session, assignment_id: int, student_id: int) -> Submission | None:
    return (
        db.query(Submission)
        .filter(
            Submission.assignment_id == assignment_id,
            Submission.student_id == student_id,
        )
        .first()
    )


def _reset_grading(db: Session, user: User, row: Submission) -> None:
    if row.score is not None:
        log_action(db, user.id, "RESET_ASSIGNMENT_GRADE", "submissions", str(row.id),
            {"old_score": row.score, "new_score": None, "assignment_id": row.assignment_id})
    row.score = None
    row.feedback = None
    row.graded_by = None
    row.graded_at = None


def submit_text(db: Session, user: User, assignment_id: int, text: str | None) -> Submission:
    item = _get_published_assignment(db, assignment_id)
    student = get_enrolled_student(db, user, item.class_id)
    ensure_class_writable(db, item.class_id)
    now, is_late = _submission_timing(item)
    if not text or not text.strip():
        raise HTTPException(
            422,
            detail={
                "code": "SUBMISSION_REQUIRED",
                "message": "Nhập nội dung bài nộp trước khi gửi.",
            },
        )
    result = _existing_submission(db, item.id, student.id)
    old_file = result.file_path if result else None
    if result:
        result.text = text.strip()
        result.file_path = None
        result.submitted_at = now
        result.is_late = is_late
        _reset_grading(db, user, result)
    else:
        result = Submission(
            assignment_id=item.id,
            student_id=student.id,
            text=text.strip(),
            submitted_at=now,
            is_late=is_late,
        )
        db.add(result)
    db.commit()
    db.refresh(result)
    remove_stored_file(old_file)
    return result


def submit_file(
    db: Session,
    user: User,
    assignment_id: int,
    filename: str | None,
    content_type: str | None,
    content: bytes,
    text: str | None = None,
) -> Submission:
    item = _get_published_assignment(db, assignment_id)
    student = get_enrolled_student(db, user, item.class_id)
    ensure_class_writable(db, item.class_id)
    now, is_late = _submission_timing(item)
    suffix = validate_upload(filename, content_type, content)
    result = _existing_submission(db, item.id, student.id)
    stored = store_upload("submissions", student.id, suffix, content)
    old_file = result.file_path if result else None
    try:
        if result:
            result.file_path = str(stored)
            result.text = text.strip() if text and text.strip() else None
            result.submitted_at = now
            result.is_late = is_late
            _reset_grading(db, user, result)
        else:
            result = Submission(
                assignment_id=item.id,
                student_id=student.id,
                file_path=str(stored),
                text=text.strip() if text and text.strip() else None,
                submitted_at=now,
                is_late=is_late,
            )
            db.add(result)
        db.commit()
        db.refresh(result)
    except Exception:
        db.rollback()
        remove_stored_file(str(stored))
        raise
    remove_stored_file(old_file)
    return result


def upload_assignment_attachment(
    db: Session,
    user: User,
    assignment_id: int,
    filename: str | None,
    content_type: str | None,
    content: bytes,
) -> Assignment:
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(
            404,
            detail={"code": "ASSIGNMENT_NOT_FOUND", "message": "Không tìm thấy bài tập."},
        )
    ensure_class_manager(db, user, item.class_id)
    ensure_class_writable(db, item.class_id)
    suffix = validate_upload(filename, content_type, content)
    stored = store_upload("assignments", item.id, suffix, content)
    old_file = item.attachment_path
    try:
        item.attachment_path = str(stored)
        db.commit()
        db.refresh(item)
    except Exception:
        db.rollback()
        remove_stored_file(str(stored))
        raise
    remove_stored_file(old_file)
    return item


def assignment_attachment_path(db: Session, user: User, assignment_id: int) -> Path:
    item = db.get(Assignment, assignment_id)
    if not item or not item.attachment_path:
        raise HTTPException(
            404,
            detail={"code": "FILE_NOT_FOUND", "message": "Bài tập không có tệp đính kèm."},
        )
    if user.role == UserRole.student:
        get_enrolled_student(db, user, item.class_id)
        if item.status != AssignmentStatus.published:
            raise HTTPException(
                404,
                detail={"code": "FILE_NOT_FOUND", "message": "Không tìm thấy tệp."},
            )
    else:
        ensure_class_manager(db, user, item.class_id)
    path = Path(item.attachment_path)
    if not path.is_file():
        raise HTTPException(
            404,
            detail={
                "code": "FILE_NOT_FOUND",
                "message": "Tệp không còn tồn tại trên hệ thống.",
            },
        )
    return path


def submission_file_path(db: Session, user: User, submission_id: int) -> Path:
    row = db.get(Submission, submission_id)
    if not row or not row.file_path:
        raise HTTPException(
            404,
            detail={"code": "FILE_NOT_FOUND", "message": "Bài nộp không có tệp."},
        )
    if user.role == UserRole.student:
        student = get_enrolled_student(db, user, row.assignment.class_id)
        if row.student_id != student.id:
            raise HTTPException(
                403,
                detail={"code": "FORBIDDEN", "message": "Bạn không được tải bài nộp này."},
            )
    else:
        ensure_class_manager(db, user, row.assignment.class_id)
    path = Path(row.file_path)
    if not path.is_file():
        raise HTTPException(
            404,
            detail={
                "code": "FILE_NOT_FOUND",
                "message": "Tệp không còn tồn tại trên hệ thống.",
            },
        )
    return path


def list_submissions(
    db: Session,
    user: User,
    assignment_id: int,
    page: int,
    page_size: int,
) -> dict:
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(
            404,
            detail={"code": "ASSIGNMENT_NOT_FOUND", "message": "Không tìm thấy bài tập."},
        )
    ensure_class_manager(db, user, item.class_id)
    query = (
        db.query(Submission)
        .options(joinedload(Submission.student))
        .filter(Submission.assignment_id == assignment_id)
    )
    total = query.count()
    records = (
        query.order_by(Submission.submitted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [submission_out(row) for row in records],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def grade_submission(
    db: Session,
    user: User,
    submission_id: int,
    score: float,
    feedback: str | None,
) -> Submission:
    row = db.get(Submission, submission_id)
    if not row:
        raise HTTPException(
            404,
            detail={"code": "SUBMISSION_NOT_FOUND", "message": "Không tìm thấy bài nộp."},
        )
    ensure_class_manager(db, user, row.assignment.class_id)
    ensure_class_writable(db, row.assignment.class_id)
    if score > row.assignment.max_score:
        raise HTTPException(
            422,
            detail={"code": "INVALID_SCORE", "message": "Điểm không được vượt quá điểm tối đa."},
        )
    log_action(db, user.id, "GRADE_ASSIGNMENT", "submissions", str(row.id),
        {"old_score": row.score, "new_score": score, "assignment_id": row.assignment_id})
    row.score = score
    row.feedback = feedback
    row.graded_by = user.id
    row.graded_at = now_local()
    db.commit()
    db.refresh(row)
    add_notification(
        db,
        row.student.user_id,
        "assignment_graded",
        "Bài tập đã được chấm",
        f"{row.assignment.title}: {score:g}/{row.assignment.max_score:g} điểm.",
        f"/student/classes/{row.assignment.class_id}",
    )
    db.commit()
    return row
