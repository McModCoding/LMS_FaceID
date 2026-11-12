"""Snapshot and grading primitives for M6; never expose the private snapshot to students."""

from decimal import Decimal
from random import Random

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.exam import Exam, ExamQuestion, ExamStatus
from app.models.question import Question, QuestionOption, QuestionType


def shuffled_ids(ids: list[int], seed: int) -> list[int]:
    """Fisher–Yates, with the attempt ID as a reproducible seed."""
    values = list(ids)
    rng = Random(seed)
    for i in range(len(values) - 1, 0, -1):
        j = rng.randrange(i + 1)
        values[i], values[j] = values[j], values[i]
    return values


def _snapshot(row: ExamQuestion, question: Question, question_options: list[QuestionOption]) -> dict:
    options = [{"id": opt.id, "content": opt.content, "is_correct": opt.is_correct}
               for opt in question_options]
    correct = sum(option["is_correct"] for option in options)
    valid = (question.type == QuestionType.essay and not options) or (
        question.type != QuestionType.essay and 2 <= len(options) <= 6 and
        ((question.type == QuestionType.multiple and correct >= 1) or
         (question.type == QuestionType.single and correct == 1) or
         (question.type == QuestionType.true_false and len(options) == 2 and correct == 1))
    )
    if not valid:
        raise HTTPException(409, detail={"code": "INVALID_EXAM_QUESTION",
            "message": "Câu hỏi trong đề không còn hợp lệ; hãy kiểm tra ngân hàng câu hỏi."})
    return {"question_id": question.id, "type": question.type.value, "content": question.content,
            "explanation": question.explanation, "points": str(row.points), "options": options}


def freeze_exam_content(db: Session, exam_id: int) -> list[dict]:
    """Freeze once within caller's transaction; caller must not commit before creating attempt.

    Locking the exam serializes starts and edits; question locks coordinate with bank edits.
    A rollback rolls back snapshots together with the attempt.
    """
    exam = db.query(Exam).filter(Exam.id == exam_id).populate_existing().with_for_update().first()
    if not exam or exam.status != ExamStatus.published:
        raise HTTPException(409, detail={"code": "EXAM_NOT_PUBLISHED", "message": "Bài kiểm tra chưa được công bố."})
    rows = (db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.order_no).with_for_update().all())
    if not rows:
        raise HTTPException(409, detail={"code": "EXAM_EMPTY", "message": "Bài kiểm tra chưa có câu hỏi."})
    frozen_count = sum(row.frozen_content is not None for row in rows)
    if frozen_count == len(rows):
        return [row.frozen_content for row in rows]
    if frozen_count:
        raise HTTPException(409, detail={"code": "EXAM_SNAPSHOT_INCOMPLETE", "message": "Dữ liệu đề không nhất quán."})
    ids = sorted(row.question_id for row in rows)
    questions = (db.query(Question).filter(Question.id.in_(ids))
                 .order_by(Question.id).populate_existing().with_for_update().all())
    by_id = {question.id: question for question in questions}
    if len(by_id) != len(ids):
        raise HTTPException(409, detail={"code": "INVALID_EXAM_QUESTION", "message": "Không tìm thấy câu hỏi của đề."})
    # Locking reads prevent an old REPEATABLE READ snapshot of options from being
    # combined with a newer question while another transaction edits the bank.
    options = (db.query(QuestionOption).filter(QuestionOption.question_id.in_(ids))
               .order_by(QuestionOption.question_id, QuestionOption.order_no)
               .populate_existing().with_for_update().all())
    by_question = {question_id: [] for question_id in ids}
    for option in options:
        by_question[option.question_id].append(option)
    snapshots = [_snapshot(row, by_id[row.question_id], by_question[row.question_id]) for row in rows]
    for row, content in zip(rows, snapshots, strict=True):
        row.frozen_content = content
    db.flush()
    return snapshots


def student_question(snapshot: dict) -> dict:
    """Explicit allowlist: no explanation, correct flags, or author-only metadata."""
    return {"question_id": snapshot["question_id"], "type": snapshot["type"],
            "content": snapshot["content"], "points": snapshot["points"],
            "options": [{"id": opt["id"], "content": opt["content"]} for opt in snapshot["options"]]}


def score_answer(snapshot: dict, selected_ids: list[int]) -> Decimal | None:
    """Return unrounded points; essays are graded manually and remain unscored."""
    options = snapshot["options"]
    selected = set(selected_ids)
    if len(selected) != len(selected_ids) or not selected.issubset({opt["id"] for opt in options}):
        raise ValueError("Đáp án không hợp lệ")
    kind = snapshot["type"]
    if kind == "essay":
        if selected:
            raise ValueError("Câu tự luận không có lựa chọn")
        return None
    if kind not in {"single", "multiple", "true_false"}:
        raise ValueError("Loại câu hỏi không hợp lệ")
    if kind != "multiple" and len(selected) > 1:
        raise ValueError("Chỉ được chọn một đáp án")
    correct = {opt["id"] for opt in options if opt["is_correct"]}
    if not correct:
        raise ValueError("Câu hỏi không có đáp án đúng")
    points = Decimal(snapshot["points"])
    if kind == "multiple":
        numerator = max(0, len(selected & correct) - len(selected - correct))
        return points * Decimal(numerator) / Decimal(len(correct))
    return points if selected == correct else Decimal(0)
