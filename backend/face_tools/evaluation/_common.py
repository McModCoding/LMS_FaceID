"""Tiện ích dùng chung cho các script đánh giá (chạy từ thư mục backend: python -m face_tools.evaluation.<tên>)."""
from __future__ import annotations

from pathlib import Path

from app.face.opencv_engine import OpenCVFaceEngine


def load_engine(require_ready_thresholds: bool = False) -> OpenCVFaceEngine:
    engine = OpenCVFaceEngine()
    if not engine._ensure_loaded():
        raise SystemExit("Chưa nạp được mô hình (" + str(engine.last_error) + "). "
                         "Chạy: python face_tools/download_face_models.py")
    if require_ready_thresholds and not engine.is_ready:
        raise SystemExit("Engine chưa sẵn sàng: " + str(engine.not_ready_reason))
    return engine


def resolve(manifest: Path, relative: str) -> Path:
    path = (manifest.parent / str(relative)).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path
