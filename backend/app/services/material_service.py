"""Authorization, file lifecycle and HTTPS rules for class materials."""

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.user import User, UserRole
from app.schemas.material import MaterialUpdate
from app.services.audit_service import log_action
from app.services.learning_access import (
    ensure_class_manager,
    ensure_class_writable,
    get_class_or_404,
    get_enrolled_student,
)
from app.utils.uploads import remove_stored_file, store_upload, validate_upload


def _error(code: str, message: str, status: int = 422):
    raise HTTPException(status, detail={"code": code, "message": message})


def _read_access(db: Session, user: User, class_id: int):
    get_class_or_404(db, class_id)
    if user.role == UserRole.student:
        get_enrolled_student(db, user, class_id)
    else:
        ensure_class_manager(db, user, class_id)


def _item(db: Session, material_id: int) -> Material:
    row = db.get(Material, material_id)
    if not row:
        _error("MATERIAL_NOT_FOUND", "Không tìm thấy học liệu.", 404)
    return row


def material_out(row: Material) -> dict:
    return {"id": row.id, "class_id": row.class_id, "title": row.title,
            "description": row.description, "url": row.url, "filename": row.filename,
            "has_file": bool(row.file_path), "created_at": row.created_at}


def list_materials(db: Session, user: User, class_id: int, page: int, page_size: int):
    _read_access(db, user, class_id)
    query = db.query(Material).filter(Material.class_id == class_id)
    return {"items": [material_out(row) for row in query.order_by(Material.id.desc())
                      .offset((page - 1) * page_size).limit(page_size).all()],
            "total": query.count(), "page": page, "page_size": page_size}


def create_material(db: Session, user: User, class_id: int, title: str, description: str | None,
                    url: str | None, filename: str | None, content_type: str | None,
                    content: bytes | None) -> Material:
    ensure_class_manager(db, user, class_id)
    ensure_class_writable(db, class_id)
    try:
        metadata = MaterialUpdate(title=title, description=description)
    except ValidationError:
        _error("INVALID_MATERIAL", "Tiêu đề cần 1–200 ký tự; mô tả tối đa 5000 ký tự.")
    url = url.strip() if url else None
    if bool(url) == (content is not None):
        _error("MATERIAL_SOURCE_REQUIRED", "Chọn đúng một tệp hoặc một liên kết HTTPS.")
    if url:
        try:
            parts = urlsplit(url)
            if (len(url) > 2048 or parts.scheme != "https" or not parts.hostname
                    or parts.username or parts.password or any(char.isspace() for char in url)):
                raise ValueError
            _ = parts.port
        except ValueError:
            _error("INVALID_MATERIAL_URL", "Liên kết phải là HTTPS hợp lệ, không chứa thông tin đăng nhập.")
    stored = None
    if content is not None:
        suffix = validate_upload(filename, content_type, content)
        stored = store_upload("materials", class_id, suffix, content)
    row = Material(class_id=class_id, author_id=user.id, **metadata.model_dump(), url=url,
                   file_path=str(stored) if stored else None,
                   filename=filename.replace("\\", "/").split("/")[-1][:255] if stored and filename else None)
    try:
        db.add(row)
        db.flush()
        log_action(db, user.id, "CREATE_MATERIAL", "materials", str(row.id), {"class_id": class_id})
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        if stored:
            remove_stored_file(str(stored))
        raise
    return row


def update_material(db: Session, user: User, material_id: int, data: MaterialUpdate) -> Material:
    row = _item(db, material_id)
    ensure_class_manager(db, user, row.class_id)
    ensure_class_writable(db, row.class_id)
    row.title, row.description = data.title, data.description
    log_action(db, user.id, "UPDATE_MATERIAL", "materials", str(row.id), {"class_id": row.class_id})
    db.commit()
    db.refresh(row)
    return row


def delete_material(db: Session, user: User, material_id: int):
    row = _item(db, material_id)
    ensure_class_manager(db, user, row.class_id)
    ensure_class_writable(db, row.class_id)
    old_path = row.file_path
    log_action(db, user.id, "DELETE_MATERIAL", "materials", str(row.id), {"class_id": row.class_id})
    db.delete(row)
    db.commit()
    remove_stored_file(old_path)


def download_material(db: Session, user: User, material_id: int) -> tuple[Path, str]:
    row = _item(db, material_id)
    _read_access(db, user, row.class_id)
    if not row.file_path or not Path(row.file_path).is_file():
        _error("FILE_NOT_FOUND", "Tệp học liệu không còn tồn tại. Liên hệ giảng viên để kiểm tra.", 404)
    return Path(row.file_path), row.filename or "hoc-lieu"
