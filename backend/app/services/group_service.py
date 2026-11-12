"""Student group management rules for M5."""

import random

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.learning import Group, GroupMember
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.learning_access import (
    ensure_class_manager,
    ensure_class_writable,
    get_enrolled_student,
)


def list_groups(db: Session, user: User, class_id: int) -> list[dict]:
    if user.role == UserRole.student:
        get_enrolled_student(db, user, class_id)
    else:
        ensure_class_manager(db, user, class_id)
    rows = db.query(Group).filter(Group.class_id == class_id).order_by(Group.name.asc()).all()
    return [group_out(row) for row in rows]


def group_out(row: Group) -> dict:
    return {
        "id": row.id,
        "class_id": row.class_id,
        "name": row.name,
        "members": [
            {
                "student_id": member.student_id,
                "student_code": member.student.student_code,
                "full_name": member.student.full_name,
            }
            for member in row.members
        ],
    }


def create_group(db: Session, user: User, class_id: int, name: str) -> Group:
    ensure_class_manager(db, user, class_id)
    ensure_class_writable(db, class_id)
    row = Group(class_id=class_id, name=name.strip())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            detail={"code": "GROUP_NAME_EXISTS", "message": "Tên nhóm đã tồn tại trong lớp."},
        )
    db.refresh(row)
    return row


def add_group_member(db: Session, user: User, group_id: int, student_id: int) -> Group:
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(
            404,
            detail={"code": "GROUP_NOT_FOUND", "message": "Không tìm thấy nhóm."},
        )
    ensure_class_manager(db, user, group.class_id)
    ensure_class_writable(db, group.class_id)
    student = db.get(Student, student_id)
    if not student or student.is_deleted:
        raise HTTPException(
            404,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Không tìm thấy sinh viên."},
        )
    enrollment = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == group.class_id,
            ClassStudent.student_id == student_id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            409,
            detail={
                "code": "STUDENT_NOT_ENROLLED",
                "message": "Sinh viên không thuộc lớp học phần này.",
            },
        )
    existing = (
        db.query(GroupMember)
        .join(Group)
        .filter(Group.class_id == group.class_id, GroupMember.student_id == student_id)
        .first()
    )
    if existing:
        raise HTTPException(
            409,
            detail={
                "code": "STUDENT_ALREADY_GROUPED",
                "message": "Sinh viên đã thuộc một nhóm của lớp.",
            },
        )
    db.add(GroupMember(group_id=group.id, student_id=student_id))
    db.commit()
    db.refresh(group)
    return group


def remove_group_member(db: Session, user: User, group_id: int, student_id: int) -> Group:
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(
            404,
            detail={"code": "GROUP_NOT_FOUND", "message": "Không tìm thấy nhóm."},
        )
    ensure_class_manager(db, user, group.class_id)
    ensure_class_writable(db, group.class_id)
    membership = (
        db.query(GroupMember)
        .filter(GroupMember.group_id == group_id, GroupMember.student_id == student_id)
        .first()
    )
    if not membership:
        raise HTTPException(
            404,
            detail={"code": "GROUP_MEMBER_NOT_FOUND", "message": "Sinh viên không thuộc nhóm."},
        )
    db.delete(membership)
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, user: User, group_id: int) -> None:
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(
            404,
            detail={"code": "GROUP_NOT_FOUND", "message": "Không tìm thấy nhóm."},
        )
    ensure_class_manager(db, user, group.class_id)
    ensure_class_writable(db, group.class_id)
    db.query(GroupMember).filter(GroupMember.group_id == group.id).delete(
        synchronize_session=False
    )
    db.delete(group)
    db.commit()


def randomize_groups(
    db: Session,
    user: User,
    class_id: int,
    group_count: int | None,
    members_per_group: int | None,
    replace_existing: bool,
) -> list[dict]:
    ensure_class_manager(db, user, class_id)
    ensure_class_writable(db, class_id)
    existing = db.query(Group).filter(Group.class_id == class_id).all()
    if existing and not replace_existing:
        raise HTTPException(
            409,
            detail={
                "code": "GROUPS_ALREADY_EXIST",
                "message": "Lớp đã có nhóm. Hãy xác nhận thay thế trước khi chia lại.",
            },
        )
    students = [
        student_id
        for (student_id,) in db.query(ClassStudent.student_id)
        .filter(
            ClassStudent.class_id == class_id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
        .order_by(ClassStudent.student_id.asc())
        .all()
    ]
    if not students:
        raise HTTPException(
            409,
            detail={"code": "NO_ENROLLED_STUDENTS", "message": "Lớp chưa có sinh viên."},
        )
    if (group_count is None) == (members_per_group is None):
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_GROUPING_MODE",
                "message": "Chỉ chọn số nhóm hoặc số thành viên mỗi nhóm.",
            },
        )
    if members_per_group is not None:
        group_count = (len(students) + members_per_group - 1) // members_per_group
    assert group_count is not None
    group_count = min(group_count, len(students))

    if existing:
        group_ids = [group.id for group in existing]
        db.query(GroupMember).filter(GroupMember.group_id.in_(group_ids)).delete(
            synchronize_session=False
        )
        db.query(Group).filter(Group.id.in_(group_ids)).delete(synchronize_session=False)
        db.flush()

    random.SystemRandom().shuffle(students)
    groups = [Group(class_id=class_id, name=f"Nhóm {index + 1}") for index in range(group_count)]
    db.add_all(groups)
    db.flush()
    for index, student_id in enumerate(students):
        db.add(GroupMember(group_id=groups[index % group_count].id, student_id=student_id))
    db.commit()
    return list_groups(db, user, class_id)
