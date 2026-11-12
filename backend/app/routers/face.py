from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin, require_lecturer_or_admin
from app.face.factory import get_engine
from app.models.class_ import Class
from app.models.lecturer import Lecturer
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.schemas.face import (
    FaceConsentIn,
    FaceEnrollmentResult,
    FaceProfileOut,
    FaceStatusOut,
    RecognitionFeedOut,
    RecognitionResponse,
    ReindexResult,
)
from app.services import face_service

router = APIRouter(tags=["FaceID"])


def _require_session_lecturer(db: Session, user: User, session_id: int) -> None:
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": "Không tìm thấy buổi học."},
        )
    if user.role == UserRole.admin:
        return
    lecturer = (
        db.query(Lecturer).filter(Lecturer.user_id == user.id, Lecturer.is_deleted == False).first()
    )
    cls = db.get(Class, session.class_id)
    if user.role != UserRole.lecturer or not lecturer or not cls or cls.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Bạn không có quyền dùng điểm danh trực tiếp cho buổi này.",
            },
        )


@router.get("/face/status", response_model=FaceStatusOut)
def face_status(current_user: User = Depends(require_lecturer_or_admin)):
    engine = get_engine()
    return {"engine": engine.name, "version": engine.version, "is_ready": engine.is_ready}


@router.get("/students/me/face", response_model=FaceProfileOut)
def my_face(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên có hồ sơ khuôn mặt."},
        )
    return face_service.get_profile(db, current_user)


@router.post("/students/me/face/consent", response_model=FaceProfileOut)
def consent_face(
    data: FaceConsentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=403, detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên có thể đồng ý."}
        )
    return face_service.grant_consent(db, current_user, data.text_version)


@router.delete("/students/me/face/consent", response_model=FaceProfileOut)
def revoke_face_consent(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên có thể thu hồi đồng ý."},
        )
    return face_service.revoke_consent(db, current_user)


@router.post("/students/me/face/enroll", response_model=FaceEnrollmentResult)
async def enroll_face(
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên có thể đăng ký ảnh."},
        )
    files = [
        (image.filename, image.content_type, await image.read(face_service.MAX_IMAGE_BYTES + 1))
        for image in images
    ]
    return face_service.enroll_images(db, current_user, files)


@router.post("/admin/face/reindex", response_model=ReindexResult)
def reindex_face(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return face_service.reindex(db)


@router.post("/sessions/{session_id}/recognize", response_model=RecognitionResponse)
async def recognize_face(
    session_id: int,
    frame: UploadFile = File(...),
    frame_id: UUID | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_session_lecturer(db, current_user, session_id)
    content = await frame.read(face_service.MAX_IMAGE_BYTES + 1)
    if len(content) > face_service.MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": "Khung hình vượt quá 10 MB."},
        )
    if not face_service._valid_image_signature(frame.content_type, content):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_IMAGE", "message": "Khung hình không phải ảnh JPG/PNG hợp lệ."},
        )
    return face_service.recognize(db, session_id, content, str(frame_id) if frame_id else None)


@router.get("/sessions/{session_id}/recognition-feed", response_model=RecognitionFeedOut)
def recognition_feed(
    session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _require_session_lecturer(db, current_user, session_id)
    return face_service.recognition_feed(db, session_id)
