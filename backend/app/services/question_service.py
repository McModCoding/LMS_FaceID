from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.models.class_ import Class, ClassStatus
from app.models.exam import ExamQuestion
from app.models.lecturer import Lecturer
from app.models.question import Question, QuestionOption
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.question import QuestionIn
from app.services.audit_service import log_action


def subject_access(db: Session, user: User, subject_id: int) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy môn học."})
    if user.role == UserRole.admin:
        return subject
    if user.role == UserRole.lecturer:
        assignment = (db.query(Class.id).join(Lecturer, Class.lecturer_id == Lecturer.id)
            .filter(Lecturer.user_id == user.id, Lecturer.is_deleted.is_(False), Class.subject_id == subject_id,
                Class.is_deleted.is_(False), Class.status.in_([ClassStatus.draft, ClassStatus.active]))
            .first())
        if assignment:
            return subject
    raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Bạn không có quyền truy cập ngân hàng câu hỏi môn này."})


def editable(user: User, question: Question) -> bool:
    return user.role == UserRole.admin or question.created_by == user.id


def question_out(user: User, question: Question) -> dict:
    return {"id": question.id, "subject_id": question.subject_id,
        "created_by": question.created_by, "type": question.type, "content": question.content,
        "difficulty": question.difficulty, "explanation": question.explanation,
        "options": question.options, "created_at": question.created_at,
        "can_edit": editable(user, question)}


def list_questions(db: Session, user: User, subject_id: int, page: int, page_size: int,
                   search: str | None, question_type, difficulty) -> dict:
    subject_access(db, user, subject_id)
    query = db.query(Question).filter(Question.subject_id == subject_id)
    if search:
        query = query.filter(Question.content.contains(search.strip(), autoescape=True))
    if question_type:
        query = query.filter(Question.type == question_type)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    total = query.count()
    rows = (query.options(selectinload(Question.options)).order_by(Question.id.desc())
        .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [question_out(user, row) for row in rows], "total": total,
        "page": page, "page_size": page_size}


def _new_question(subject_id: int, user_id: int, data: QuestionIn) -> Question:
    return Question(subject_id=subject_id, created_by=user_id, type=data.type, content=data.content,
        difficulty=data.difficulty, explanation=data.explanation,
        options=[QuestionOption(content=option.content, is_correct=option.is_correct, order_no=index)
                 for index, option in enumerate(data.options, 1)])


def create_questions(db: Session, user: User, subject_id: int, items: list[QuestionIn]) -> list[Question]:
    subject_access(db, user, subject_id)
    rows = [_new_question(subject_id, user.id, item) for item in items]
    db.add_all(rows)
    db.flush()
    for row in rows:
        log_action(db, user.id, "CREATE_QUESTION", "questions", str(row.id),
            {"subject_id": subject_id, "summary": "Tạo câu hỏi"})
    db.commit()
    return rows


def get_question(db: Session, user: User, question_id: int, *, require_edit: bool = False) -> Question:
    query = db.query(Question).options(selectinload(Question.options)).filter(Question.id == question_id)
    if require_edit:
        query = query.with_for_update()
    question = query.first()
    if question is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy câu hỏi."})
    subject_access(db, user, question.subject_id)
    if require_edit and not editable(user, question):
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Bạn chỉ được sửa hoặc xóa câu hỏi do mình tạo."})
    return question


def update_question(db: Session, user: User, question_id: int, data: QuestionIn) -> Question:
    row = get_question(db, user, question_id, require_edit=True)
    row.type, row.content, row.difficulty, row.explanation = data.type, data.content, data.difficulty, data.explanation
    # Flush deletions before reusing the unique (question_id, order_no) positions.
    row.options.clear()
    db.flush()
    row.options = [QuestionOption(content=option.content, is_correct=option.is_correct, order_no=index)
                   for index, option in enumerate(data.options, 1)]
    log_action(db, user.id, "UPDATE_QUESTION", "questions", str(row.id),
        {"subject_id": row.subject_id, "summary": "Cập nhật câu hỏi"})
    db.commit()
    db.refresh(row)
    return row


def delete_question(db: Session, user: User, question_id: int) -> None:
    row = get_question(db, user, question_id, require_edit=True)
    if db.query(ExamQuestion.id).filter(ExamQuestion.question_id == question_id).first():
        raise HTTPException(409, detail={"code": "QUESTION_IN_EXAM", "message": "Câu hỏi đang được dùng trong đề kiểm tra; hãy bỏ khỏi đề trước khi xóa."})
    log_action(db, user.id, "DELETE_QUESTION", "questions", str(row.id),
        {"subject_id": row.subject_id, "summary": "Xóa câu hỏi"})
    db.delete(row)
    db.commit()
