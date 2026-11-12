"""Lưu và kiểm tra tệp M5 ngoài thư mục public.

Chỉ lưu tên ngẫu nhiên; đường dẫn thật không bao giờ được trả trực tiếp qua API.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings

_ALLOWED_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    ".xls": {"application/vnd.ms-excel", "application/octet-stream"},
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/octet-stream",
    },
    ".ppt": {"application/vnd.ms-powerpoint", "application/octet-stream"},
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
        "application/octet-stream",
    },
    ".zip": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
}


def _content_matches_signature(suffix: str, content: bytes) -> bool:
    if suffix == ".pdf":
        return content.startswith(b"%PDF-")
    if suffix in {".docx", ".xlsx", ".pptx", ".zip"}:
        return content.startswith(b"PK\x03\x04")
    if suffix in {".doc", ".xls", ".ppt"}:
        return content.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
    if suffix in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if suffix == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix == ".txt":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return b"\x00" not in content
    return False


def validate_upload(filename: str | None, content_type: str | None, content: bytes) -> str:
    """Trả phần mở rộng đã chuẩn hóa hoặc ném lỗi nghiệp vụ."""
    suffix = Path(filename or "").suffix.lower()
    allowed_mimes = _ALLOWED_TYPES.get(suffix)
    if not allowed_mimes or (content_type or "") not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": "Định dạng tệp không được hỗ trợ.",
                "details": {"allowed_extensions": sorted(_ALLOWED_TYPES)},
            },
        )
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "EMPTY_FILE", "message": "Tệp tải lên đang rỗng."},
        )
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"Tệp không được vượt quá {settings.MAX_UPLOAD_SIZE_MB} MB.",
            },
        )
    if not _content_matches_signature(suffix, content):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "FILE_CONTENT_MISMATCH",
                "message": "Nội dung tệp không khớp với định dạng đã khai báo.",
            },
        )
    return suffix


def store_upload(scope: str, owner_id: int, suffix: str, content: bytes) -> Path:
    folder = Path(settings.UPLOAD_STORAGE_DIR).resolve() / scope / str(owner_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{uuid4().hex}{suffix}"
    target.write_bytes(content)
    return target


def remove_stored_file(path: str | None) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        # Tệp cũ không được phép làm hỏng giao dịch nộp lại đã hoàn tất.
        return

