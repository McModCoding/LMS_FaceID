from datetime import UTC

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.models.exam import Exam, ExamQuestion, ExamStatus
from app.models.exam_attempt import ExamAttempt
from app.models.question import Question
from app.models.user import User
from app.schemas.exam import ExamDraftIn
from app.services.audit_service import log_action
from app.services.learning_access import (
    ensure_class_manager,
    ensure_class_writable,
    get_class_or_404,
)


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def exam_out(exam: Exam, has_attempts: bool = False) -> dict:
    return {"id": exam.id, "class_id": exam.class_id, "title": exam.title, "description": exam.description,
        "duration_min": exam.duration_min, "open_at": _utc(exam.open_at), "close_at": _utc(exam.close_at),
        "shuffle_questions": exam.shuffle_questions, "shuffle_options": exam.shuffle_options,
        "max_attempts": exam.max_attempts, "score_policy": exam.score_policy, "show_result": exam.show_result,
        "require_fullscreen": exam.require_fullscreen, "record_events": exam.record_events,
        "violation_types": exam.violation_types, "max_violations": exam.max_violations,
        "auto_submit_on_violation": exam.auto_submit_on_violation, "status": exam.status,
        "questions": [{"question_id": q.question_id, "points": q.points, "order_no": q.order_no,
                       "content": (q.frozen_content or {}).get("content", q.question.content),
                       "type": (q.frozen_content or {}).get("type", q.question.type.value)} for q in exam.questions],
        "created_at": _utc(exam.created_at), "has_attempts": has_attempts,
        "total_points": sum(q.points for q in exam.questions)}


def _query(db: Session):
    return db.query(Exam).options(selectinload(Exam.questions).joinedload(ExamQuestion.question))


def list_drafts(db: Session, user: User, class_id: int, page: int, page_size: int) -> dict:
    get_class_or_404(db, class_id)
    ensure_class_manager(db, user, class_id)
    query = _query(db).filter(Exam.class_id == class_id)
    total = query.count()
    rows = query.order_by(Exam.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    counts = dict(db.query(ExamAttempt.exam_id, func.count(ExamAttempt.id)).filter(
        ExamAttempt.exam_id.in_([row.id for row in rows])).group_by(ExamAttempt.exam_id).all())
    return {"items": [exam_out(row, bool(counts.get(row.id))) for row in rows], "total": total, "page": page, "page_size": page_size}


def _validate_questions(db: Session, subject_id: int, data: ExamDraftIn) -> None:
    ids = [item.question_id for item in data.questions]
    if not ids:
        return
    rows = (db.query(Question.id).filter(Question.id.in_(ids), Question.subject_id == subject_id)
        .order_by(Question.id).with_for_update().all())
    if len(rows) != len(ids):
        raise HTTPException(422, detail={"code": "INVALID_QUESTIONS", "message": "Câu hỏi không tồn tại hoặc không thuộc môn học của lớp."})


def _apply(exam: Exam, data: ExamDraftIn) -> None:
    for key, value in data.model_dump(exclude={"questions"}).items():
        if key in ("open_at", "close_at"):
            value = value.astimezone(UTC).replace(tzinfo=None)
        setattr(exam, key, value)


def _question_rows(exam: Exam, data: ExamDraftIn) -> None:
    exam.questions = [ExamQuestion(question_id=item.question_id, points=item.points, order_no=index)
                      for index, item in enumerate(data.questions, 1)]


def create_draft(db: Session, user: User, class_id: int, data: ExamDraftIn) -> Exam:
    ensure_class_manager(db, user, class_id)
    cls = ensure_class_writable(db, class_id)
    _validate_questions(db, cls.subject_id, data)
    exam = Exam(class_id=class_id, status=ExamStatus.draft)
    _apply(exam, data)
    _question_rows(exam, data)
    db.add(exam)
    db.flush()
    log_action(db, user.id, "CREATE_EXAM_DRAFT", "exams", str(exam.id), {"class_id": class_id, "summary": "Tạo đề nháp"})
    db.commit()
    return exam


def _get_editable(db: Session, user: User, exam_id: int, allow_published: bool = False) -> Exam:
    from app.models.class_ import Class

    lookup = db.get(Exam, exam_id)
    if lookup:
        db.query(Class).filter(Class.id == lookup.class_id).with_for_update().first()
    exam = _query(db).filter(Exam.id == exam_id).populate_existing().with_for_update().first()
    if not exam:
        raise HTTPException(404, detail={"code": "EXAM_NOT_FOUND", "message": "Không tìm thấy bài kiểm tra."})
    # Refresh the collection with a current read after waiting for the class lock.
    # selectinload alone can use an older MySQL REPEATABLE READ snapshot.
    rows = db.query(ExamQuestion).filter_by(exam_id=exam_id).order_by(ExamQuestion.order_no).populate_existing().with_for_update().all()
    set_committed_value(exam, "questions", rows)
    ensure_class_manager(db, user, exam.class_id)
    ensure_class_writable(db, exam.class_id)
    if allow_published and exam.status == ExamStatus.published:
        if db.query(ExamAttempt.id).filter(ExamAttempt.exam_id == exam_id).with_for_update().first():
            raise HTTPException(409, detail={"code": "EXAM_LOCKED", "message": "Đã có sinh viên bắt đầu. Chỉ được đổi giờ đóng hoặc đóng đề."})
    elif exam.status != ExamStatus.draft:
        raise HTTPException(409, detail={"code": "EXAM_NOT_DRAFT", "message": "Chỉ được sửa hoặc xóa đề nháp."})
    return exam


def update_draft(db: Session, user: User, exam_id: int, data: ExamDraftIn) -> Exam:
    exam = _get_editable(db, user, exam_id, allow_published=True)
    cls = get_class_or_404(db, exam.class_id)
    _validate_questions(db, cls.subject_id, data)
    _apply(exam, data)
    exam.questions.clear()
    db.flush()
    _question_rows(exam, data)
    if exam.status == ExamStatus.published:
        from app.services.exam_attempt_service import _now
        from app.services.exam_content_service import freeze_exam_content

        if not data.questions or _utc(exam.close_at).replace(tzinfo=None) <= _now():
            db.rollback()
            raise HTTPException(409, detail={"code": "INVALID_PUBLISHED_EXAM", "message": "Đề công bố cần câu hỏi và giờ đóng trong tương lai."})
        db.flush()
        freeze_exam_content(db, exam.id)
    log_action(db, user.id, "UPDATE_EXAM_DRAFT", "exams", str(exam.id), {"class_id": exam.class_id, "summary": "Sửa đề nháp"})
    db.commit()
    return exam


def delete_draft(db: Session, user: User, exam_id: int) -> None:
    exam = _get_editable(db, user, exam_id)
    log_action(db, user.id, "DELETE_EXAM_DRAFT", "exams", str(exam.id), {"class_id": exam.class_id, "summary": "Xóa đề nháp"})
    db.delete(exam)
    db.commit()
