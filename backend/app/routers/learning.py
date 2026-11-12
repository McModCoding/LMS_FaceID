# ruff: noqa: E701
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.user import User, UserRole
from app.schemas.learning import (
    AnnouncementIn,
    AnnouncementOut,
    AssignmentIn,
    AssignmentList,
    AssignmentOut,
    GroupIn,
    GroupMemberIn,
    GroupOut,
    GroupRandomizeIn,
    NotificationList,
    NotificationOut,
    SubmissionGradeIn,
    SubmissionList,
    SubmissionOut,
    SubmissionTextIn,
)
from app.services import learning_service

router = APIRouter(tags=["Learning"])


def _announcement_out(row) -> dict:
    return {
        "id": row.id,
        "class_id": row.class_id,
        "author_name": row.author.username,
        "title": row.title,
        "content": row.content,
        "is_pinned": row.is_pinned,
        "created_at": row.created_at,
    }


@router.get("/classes/{class_id}/assignments", response_model=AssignmentList)
def list_assignments(
    class_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    view: Literal["all", "todo", "submitted", "finished", "pending"] = "all",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return learning_service.list_assignments(db, current_user, class_id, page, page_size, view)


@router.post("/classes/{class_id}/assignments", response_model=AssignmentOut)
def create_assignment(
    class_id: int,
    data: AssignmentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return learning_service._assignment_out(
        learning_service.create_assignment(db, current_user, class_id, data)
    )


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    data: AssignmentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return learning_service._assignment_out(
        learning_service.update_assignment(db, current_user, assignment_id, data)
    )


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    learning_service.delete_assignment(db, current_user, assignment_id)
    return Response(status_code=204)


@router.post("/assignments/{assignment_id}/attachment", response_model=AssignmentOut)
async def upload_assignment_attachment(
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
    return learning_service._assignment_out(
        learning_service.upload_assignment_attachment(
            db, current_user, assignment_id, file.filename, file.content_type, content
        )
    )


@router.get("/assignments/{assignment_id}/attachment")
def download_assignment_attachment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = learning_service.assignment_attachment_path(db, current_user, assignment_id)
    return FileResponse(path, filename=f"bai-tap-{assignment_id}{path.suffix}")


@router.post("/assignments/{assignment_id}/submissions", response_model=SubmissionOut)
def submit_assignment(
    assignment_id: int,
    data: SubmissionTextIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.student:
        raise HTTPException(
            403, detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên có thể nộp bài."}
        )
    return learning_service._submission_out(
        learning_service.submit_text(db, current_user, assignment_id, data.text)
    )


@router.post("/assignments/{assignment_id}/submissions/file", response_model=SubmissionOut)
async def submit_assignment_file(
    assignment_id: int,
    file: UploadFile = File(...),
    text: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.student:
        raise HTTPException(
            403, detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên có thể nộp bài."}
        )
    content = await file.read(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
    return learning_service._submission_out(
        learning_service.submit_file(
            db,
            current_user,
            assignment_id,
            file.filename,
            file.content_type,
            content,
            text,
        )
    )


@router.get("/submissions/{submission_id}/file")
def download_submission_file(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = learning_service.submission_file_path(db, current_user, submission_id)
    return FileResponse(path, filename=f"bai-nop-{submission_id}{path.suffix}")


@router.get("/assignments/{assignment_id}/submissions", response_model=SubmissionList)
def list_submissions(
    assignment_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return learning_service.list_submissions(db, current_user, assignment_id, page, page_size)


@router.post("/submissions/{submission_id}/grade", response_model=SubmissionOut)
def grade_submission(
    submission_id: int,
    data: SubmissionGradeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.admin, UserRole.lecturer):
        raise HTTPException(
            403, detail={"code": "FORBIDDEN", "message": "Bạn không có quyền chấm bài."}
        )
    return learning_service._submission_out(
        learning_service.grade_submission(
            db, current_user, submission_id, data.score, data.feedback
        )
    )


@router.get("/classes/{class_id}/announcements", response_model=list[AnnouncementOut])
def list_announcements(
    class_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return [
        _announcement_out(row)
        for row in learning_service.list_announcements(db, current_user, class_id)
    ]


@router.post("/classes/{class_id}/announcements", response_model=AnnouncementOut)
def create_announcement(
    class_id: int,
    data: AnnouncementIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.admin, UserRole.lecturer):
        raise HTTPException(
            403, detail={"code": "FORBIDDEN", "message": "Bạn không có quyền tạo thông báo."}
        )
    return _announcement_out(learning_service.create_announcement(db, current_user, class_id, data))


@router.get("/announcements", response_model=list[AnnouncementOut])
def list_system_announcements(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return [_announcement_out(row) for row in learning_service.list_system_announcements(db)]


@router.post("/announcements", response_model=AnnouncementOut)
def create_system_announcement(
    data: AnnouncementIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _announcement_out(learning_service.create_system_announcement(db, current_user, data))


@router.get("/notifications", response_model=NotificationList)
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return learning_service.list_notifications(db, current_user, page, page_size)


@router.post("/notifications/read-all")
def read_all_notifications(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return {"updated": learning_service.read_all_notifications(db, current_user)}


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return learning_service.read_notification(db, current_user, notification_id)


@router.get("/classes/{class_id}/groups", response_model=list[GroupOut])
def list_groups(
    class_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return learning_service.list_groups(db, current_user, class_id)


@router.post("/classes/{class_id}/groups", response_model=GroupOut)
def create_group(
    class_id: int,
    data: GroupIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.admin, UserRole.lecturer):
        raise HTTPException(
            403, detail={"code": "FORBIDDEN", "message": "Bạn không có quyền tạo nhóm."}
        )
    return _group_out(learning_service.create_group(db, current_user, class_id, data.name))


def _group_out(row) -> dict:
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


@router.post("/groups/{group_id}/members", response_model=GroupOut)
def add_group_member(
    group_id: int,
    data: GroupMemberIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.admin, UserRole.lecturer):
        raise HTTPException(
            403, detail={"code": "FORBIDDEN", "message": "Bạn không có quyền quản lý nhóm."}
        )
    return _group_out(
        learning_service.add_group_member(db, current_user, group_id, data.student_id)
    )


@router.delete("/groups/{group_id}/members/{student_id}", response_model=GroupOut)
def remove_group_member(
    group_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _group_out(
        learning_service.remove_group_member(db, current_user, group_id, student_id)
    )


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    learning_service.delete_group(db, current_user, group_id)
    return Response(status_code=204)


@router.post("/classes/{class_id}/groups/randomize", response_model=list[GroupOut])
def randomize_groups(
    class_id: int,
    data: GroupRandomizeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return learning_service.randomize_groups(
        db,
        current_user,
        class_id,
        data.group_count,
        data.members_per_group,
        data.replace_existing,
    )
