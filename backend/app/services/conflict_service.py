"""
conflict_service.py
Phát hiện xung đột lịch học theo 3 loại:
  a) Cùng phòng, cùng ngày, giờ giao nhau.
  b) Cùng giảng viên, cùng ngày, giờ giao nhau.
  c) Sinh viên enrolled ở lớp này có buổi khác trùng giờ cùng ngày.

Định nghĩa "giao nhau":  start_a < end_b AND start_b < end_a
Buổi cancelled bị bỏ qua.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

from sqlalchemy import and_, func, not_
from sqlalchemy.orm import Session

from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus


@dataclass
class ConflictItem:
    conflict_type: str          # "room" | "lecturer" | "student"
    class_id: int
    class_code: str
    session_id: int
    date: date
    start_time: time
    end_time: time
    room: str
    conflicting_entity: str     # phòng / mã GV / mã SV
    message: str


@dataclass
class ConflictResult:
    has_conflict: bool = False
    conflicts: list[ConflictItem] = field(default_factory=list)


def _times_overlap(s1: time, e1: time, s2: time, e2: time) -> bool:
    """Trả True nếu [s1, e1) và [s2, e2) giao nhau (biên bằng nhau KHÔNG xung đột)."""
    return s1 < e2 and s2 < e1


def check_conflicts_for_sessions(
    db: Session,
    *,
    proposed: list[tuple[date, time, time, str]],   # (date, start_time, end_time, room)
    class_id: int,
    lecturer_id: int | None,
    exclude_session_ids: list[int] | None = None,
) -> ConflictResult:
    """
    Kiểm tra xung đột cho danh sách buổi đề xuất (date, start, end, room).
    Dùng khi tạo/sửa lịch hoặc đổi giảng viên.

    exclude_session_ids: danh sách session id không cần kiểm tra (dùng khi sửa lịch
    để loại trừ chính các buổi scheduled cũ sắp bị xoá/tái tạo).
    """
    result = ConflictResult()
    if not proposed:
        return result

    # Lấy mã lớp hiện tại
    from app.models.class_ import Class
    cls = db.query(Class).filter(Class.id == class_id).first()
    cls_code = cls.code if cls else str(class_id)

    exclude_ids = set(exclude_session_ids or [])

    for prop_date, prop_start, prop_end, prop_room in proposed:
        # Lấy tất cả buổi cùng ngày, không cancelled, không trong exclude_ids
        base_q = (
            db.query(SessionModel)
            .filter(
                SessionModel.date == prop_date,
                SessionModel.status != SessionStatus.cancelled,
            )
        )
        if exclude_ids:
            base_q = base_q.filter(not_(SessionModel.id.in_(exclude_ids)))

        # a) Xung đột phòng: cùng phòng, cùng ngày
        room_conflicts = base_q.filter(
            func.upper(func.trim(SessionModel.room)) == prop_room.upper().strip(),
            SessionModel.start_time < prop_end,
            SessionModel.end_time > prop_start,
        ).all()
        for s in room_conflicts:
            from app.models.class_ import Class as CModel
            other_cls = db.query(CModel).filter(CModel.id == s.class_id).first()
            result.has_conflict = True
            result.conflicts.append(ConflictItem(
                conflict_type="room",
                class_id=s.class_id,
                class_code=other_cls.code if other_cls else str(s.class_id),
                session_id=s.id,
                date=s.date,
                start_time=s.start_time,
                end_time=s.end_time,
                room=s.room,
                conflicting_entity=prop_room,
                message=(
                    f"Phòng {prop_room} đã bị trùng lịch với lớp "
                    f"{other_cls.code if other_cls else s.class_id} "
                    f"vào {s.date} {s.start_time}–{s.end_time}."
                ),
            ))

        # b) Xung đột giảng viên
        if lecturer_id is not None:
            from app.models.class_ import Class as CModel2
            lec_conflicts = (
                base_q.join(CModel2, SessionModel.class_id == CModel2.id)
                .filter(
                    CModel2.lecturer_id == lecturer_id,
                    SessionModel.start_time < prop_end,
                    SessionModel.end_time > prop_start,
                )
                .all()
            )
            for s in lec_conflicts:
                from app.models.class_ import Class as CModel3
                other_cls = db.query(CModel3).filter(CModel3.id == s.class_id).first()
                result.has_conflict = True
                result.conflicts.append(ConflictItem(
                    conflict_type="lecturer",
                    class_id=s.class_id,
                    class_code=other_cls.code if other_cls else str(s.class_id),
                    session_id=s.id,
                    date=s.date,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    room=s.room,
                    conflicting_entity=str(lecturer_id),
                    message=(
                        f"Giảng viên (id={lecturer_id}) đã có lịch dạy lớp "
                        f"{other_cls.code if other_cls else s.class_id} "
                        f"vào {s.date} {s.start_time}–{s.end_time}."
                    ),
                ))

        # c) Xung đột sinh viên: sinh viên enrolled ở lớp này có buổi khác trùng giờ
        enrolled_student_ids = (
            db.query(ClassStudent.student_id)
            .filter(
                ClassStudent.class_id == class_id,
                ClassStudent.status == ClassStudentStatus.enrolled,
            )
            .all()
        )
        enrolled_ids = [r[0] for r in enrolled_student_ids]

        if enrolled_ids:
            from app.models.class_ import Class as CModel4
            stu_conflicts = (
                base_q.join(CModel4, SessionModel.class_id == CModel4.id)
                .join(
                    ClassStudent,
                    and_(
                        ClassStudent.class_id == SessionModel.class_id,
                        ClassStudent.status == ClassStudentStatus.enrolled,
                        ClassStudent.student_id.in_(enrolled_ids),
                    ),
                )
                .filter(
                    SessionModel.start_time < prop_end,
                    SessionModel.end_time > prop_start,
                )
                .distinct()
                .all()
            )
            for s in stu_conflicts:
                from app.models.class_ import Class as CModel5
                other_cls = db.query(CModel5).filter(CModel5.id == s.class_id).first()
                result.has_conflict = True
                result.conflicts.append(ConflictItem(
                    conflict_type="student",
                    class_id=s.class_id,
                    class_code=other_cls.code if other_cls else str(s.class_id),
                    session_id=s.id,
                    date=s.date,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    room=s.room,
                    conflicting_entity="(nhiều sinh viên)",
                    message=(
                        f"Một số sinh viên đang học lớp {cls_code} cũng có buổi học "
                        f"ở lớp {other_cls.code if other_cls else s.class_id} "
                        f"vào {s.date} {s.start_time}–{s.end_time}."
                    ),
                ))

    return result


def check_conflicts_for_enrollment(
    db: Session,
    *,
    class_id: int,
    student_ids: list[int],
) -> dict[int, list[ConflictItem]]:
    """
    Khi ghi danh sinh viên vào lớp, kiểm tra từng sinh viên có buổi trùng với
    lịch của lớp này không.

    Trả về dict {student_id: [ConflictItem, ...]} (chỉ các sv có xung đột).
    """
    if not student_ids:
        return {}

    # Lấy các buổi scheduled/open của lớp này
    class_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.class_id == class_id,
            SessionModel.status.in_([SessionStatus.scheduled, SessionStatus.open, SessionStatus.closed]),
        )
        .all()
    )
    if not class_sessions:
        return {}

    from app.models.class_ import Class
    cls = db.query(Class).filter(Class.id == class_id).first()
    cls_code = cls.code if cls else str(class_id)

    conflicts_by_student: dict[int, list[ConflictItem]] = {}

    for student_id in student_ids:
        # Lấy tất cả lớp mà sinh viên đang enrolled (trừ lớp hiện tại)
        other_class_ids = (
            db.query(ClassStudent.class_id)
            .filter(
                ClassStudent.student_id == student_id,
                ClassStudent.status == ClassStudentStatus.enrolled,
                ClassStudent.class_id != class_id,
            )
            .all()
        )
        other_ids = [r[0] for r in other_class_ids]
        if not other_ids:
            continue

        stu_conflicts: list[ConflictItem] = []
        for cs in class_sessions:
            if cs.status == SessionStatus.cancelled:
                continue
            # Tìm buổi trùng của sinh viên
            overlap_sessions = (
                db.query(SessionModel)
                .filter(
                    SessionModel.class_id.in_(other_ids),
                    SessionModel.date == cs.date,
                    SessionModel.status != SessionStatus.cancelled,
                    SessionModel.start_time < cs.end_time,
                    SessionModel.end_time > cs.start_time,
                )
                .all()
            )
            for os_ in overlap_sessions:
                other_cls = db.query(Class).filter(Class.id == os_.class_id).first()
                stu_conflicts.append(ConflictItem(
                    conflict_type="student",
                    class_id=os_.class_id,
                    class_code=other_cls.code if other_cls else str(os_.class_id),
                    session_id=os_.id,
                    date=os_.date,
                    start_time=os_.start_time,
                    end_time=os_.end_time,
                    room=os_.room,
                    conflicting_entity=str(student_id),
                    message=(
                        f"Sinh viên (id={student_id}) đã có buổi học ở lớp "
                        f"{other_cls.code if other_cls else os_.class_id} "
                        f"vào {os_.date} {os_.start_time}–{os_.end_time}, "
                        f"trùng với lịch của lớp {cls_code}."
                    ),
                ))

        if stu_conflicts:
            conflicts_by_student[student_id] = stu_conflicts

    return conflicts_by_student
