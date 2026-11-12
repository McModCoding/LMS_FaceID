from functools import lru_cache

from app.core.config import settings
from app.face.mock_engine import MockFaceEngine


@lru_cache
def get_engine():
    if settings.FACE_ENGINE == "mock":
        return MockFaceEngine()
    if settings.FACE_ENGINE == "opencv":
        # M9a: YuNet + SFace qua OpenCV. Cần extra "face" (opencv-python-headless).
        try:
            from app.face.opencv_engine import OpenCVFaceEngine
        except ImportError as exc:
            raise RuntimeError(
                "FACE_ENGINE='opencv' cần opencv-python-headless: pip install -e \".[face]\""
            ) from exc
        return OpenCVFaceEngine()
    if settings.FACE_ENGINE == "insightface":
        # Module này chỉ được thêm ở M9. Import có điều kiện giữ M4 chạy được
        # và giúp M9 chỉ cần cài engine thật rồi đổi cấu hình.
        try:
            from app.face.insightface_engine import InsightFaceEngine
        except ImportError as exc:
            raise RuntimeError(
                "FACE_ENGINE='insightface' đã được chọn nhưng engine M9 chưa được cài đặt."
            ) from exc
        return InsightFaceEngine()
    raise RuntimeError(f"FACE_ENGINE={settings.FACE_ENGINE!r} không được hỗ trợ.")
