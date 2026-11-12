"""Engine FaceID thật (M9a): OpenCV YuNet (phát hiện) + SFace (nhận diện).

Cắm vào hợp đồng ``app.face.base.FaceEngine`` (SPEC mục 7) bằng một file duy nhất; bật bằng
``FACE_ENGINE=opencv``. Không có trọng số nào được đóng gói theo mã nguồn: tải bằng
``python face_tools/download_face_models.py``. Khi thiếu trọng số hoặc chưa đặt ngưỡng,
``is_ready`` là ``False`` và hệ thống hành xử như MockFaceEngine (không tạo kết quả giả).

Quy ước dữ liệu
- Embedding: 128 số float32 đã chuẩn hóa L2 (512 byte). Nếu ``FACE_EMBEDDING_KEY`` được đặt
  thì bản lưu trong DB là token Fernet (mã hóa khi lưu). Đọc được cả hai dạng để có thể
  bật khóa sau khi đã có dữ liệu; chạy reindex hoặc đăng ký lại để mã hóa dữ liệu cũ.
- Điểm của một sinh viên = trung bình hai độ tương đồng cosine cao nhất giữa khuôn mặt
  truy vấn và các mẫu của sinh viên đó (một mẫu thì dùng chính nó), để một ảnh may mắn
  không quyết định kết quả. ``margin`` = điểm tốt nhất - điểm sinh viên tốt thứ hai; khi chỉ
  có một ứng viên, điểm thứ hai coi là 0.0.
- Các chỉ số chất lượng (độ nét, sáng, tương phản, nghiêng, kích thước) là heuristic trên ROI
  khuôn mặt 160x160, chưa được hiệu chỉnh cho camera của bạn; ngưỡng nhận diện phải được
  hiệu chỉnh bằng thực nghiệm (xem ``face_tools/evaluation``). Engine này không chống giả mạo
  (ảnh in, video phát lại); đây là giới hạn đã biết, không phải tính năng.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.face.base import Candidate, EnrollResult, FaceBox, MatchResult

logger = logging.getLogger(__name__)

NAME = "opencv-yunet-sface"
VERSION = "yunet-2023mar+sface-2021dec"
EMBEDDING_DIM = 128
_RAW_BYTES = EMBEDDING_DIM * 4
_BACKEND_ROOT = Path(__file__).resolve().parents[2]

_MIN_IMAGE_SIDE = 96
_MAX_PIXELS = 12_000_000
_DARK_LIMIT = 45.0
_BRIGHT_LIMIT = 215.0
_MAX_ROLL_DEGREES = 25.0
_ROI_SIZE = 160

# Mã lý do dùng chung với giao diện (frontend/src/pages/student/FaceEnrollmentPage.tsx).
REASON_INVALID_IMAGE = "invalid_image"
REASON_NO_FACE = "no_face"
REASON_MULTIPLE_FACES = "multiple_faces"
REASON_FACE_TOO_SMALL = "face_too_small"
REASON_BLURRY = "blurry"
REASON_TOO_DARK = "too_dark"
REASON_TOO_BRIGHT = "too_bright"
REASON_LOW_CONTRAST = "low_contrast"
REASON_TILTED = "tilted_head"
REASON_NEAR_EDGE = "near_edge"
REASON_FEATURE_FAILED = "feature_failed"
REASON_ENGINE_NOT_READY = "engine_not_ready"


# --------------------------------------------------------------------------- embedding codec
@lru_cache(maxsize=2)
def _fernet_for(key: str):
    from cryptography.fernet import Fernet

    return Fernet(key.encode())


def _fernet():
    key = (settings.FACE_EMBEDDING_KEY or "").strip()
    return _fernet_for(key) if key else None


def encode_embedding(vector: np.ndarray) -> bytes:
    """float32 -> bytes (mã hóa Fernet khi có FACE_EMBEDDING_KEY)."""
    raw = np.asarray(vector, dtype=np.float32).reshape(-1).tobytes()
    cipher = _fernet()
    return cipher.encrypt(raw) if cipher else raw


def decode_embedding(blob: bytes | None) -> np.ndarray | None:
    """bytes -> vector chuẩn hóa L2, hoặc None nếu sai kích thước/khóa/không hữu hạn."""
    if not blob:
        return None
    try:
        if len(blob) == _RAW_BYTES:
            raw = bytes(blob)
        else:
            cipher = _fernet()
            if cipher is None:
                return None
            raw = cipher.decrypt(bytes(blob))
        arr = np.frombuffer(raw, dtype=np.float32)
    except Exception:  # noqa: BLE001 - sai khóa, token hỏng, dữ liệu của engine khác
        return None
    if arr.size != EMBEDDING_DIM or not np.isfinite(arr).all():
        return None
    norm = float(np.linalg.norm(arr))
    if norm < 1e-8:
        return None
    out = (arr / norm).astype(np.float32)
    out.flags.writeable = False
    return out


@lru_cache(maxsize=4096)
def _decode_cached(blob: bytes) -> np.ndarray | None:
    return decode_embedding(blob)


def clear_embedding_cache() -> None:
    _decode_cached.cache_clear()
    _fernet_for.cache_clear()


# --------------------------------------------------------------------------- phân tích khung
@dataclass
class FaceAnalysis:
    """Một khuôn mặt đã phát hiện, kèm chỉ số chất lượng (toạ độ điểm ảnh)."""

    x: float
    y: float
    w: float
    h: float
    det_score: float
    pixels: int
    blur: float
    brightness: float
    contrast: float
    roll_degrees: float
    near_edge: bool
    reason: str | None
    quality_score: float


class OpenCVFaceEngine:
    name = NAME
    version = VERSION

    def __init__(self, detector=None, recognizer=None):
        """``detector``/``recognizer`` chỉ dùng để thử nghiệm (đối tượng giả có cùng giao diện)."""
        self._lock = threading.RLock()
        self._detector = detector
        self._recognizer = recognizer
        self._injected = detector is not None and recognizer is not None
        self._signature: tuple | None = None
        self.last_error: str | None = None

    # ------------------------------------------------------------------ trạng thái
    @staticmethod
    def _model_paths() -> tuple[Path, Path]:
        root = Path(settings.FACE_MODELS_DIR)
        if not root.is_absolute():
            root = _BACKEND_ROOT / root
        return root / settings.FACE_YUNET_MODEL, root / settings.FACE_SFACE_MODEL

    def _ensure_loaded(self) -> bool:
        if self._injected:
            return True
        det_path, rec_path = self._model_paths()
        try:
            signature = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in (det_path, rec_path))
        except OSError:
            with self._lock:
                self._detector = self._recognizer = None
                self._signature = None
                self.last_error = "model_missing"
            return False
        with self._lock:
            if self._signature == signature:
                return self._detector is not None and self._recognizer is not None
            self._detector = self._recognizer = None
            self._signature = signature
            try:
                self._detector = cv2.FaceDetectorYN.create(
                    str(det_path), "", (320, 320), settings.FACE_DETECT_SCORE, 0.3, 5000)
                self._recognizer = cv2.FaceRecognizerSF.create(str(rec_path), "")
                self.last_error = None
            except (cv2.error, AttributeError, OSError, ValueError) as exc:
                self._detector = self._recognizer = None
                self.last_error = "model_load_failed"
                logger.error("Không tải được mô hình FaceID (%s): %s", type(exc).__name__, exc)
            return self._detector is not None

    @property
    def not_ready_reason(self) -> str | None:
        if not self._ensure_loaded():
            return self.last_error or "model_missing"
        if settings.FACE_MATCH_THRESHOLD <= 0:
            return "threshold_not_set"
        return None

    @property
    def is_ready(self) -> bool:
        return self.not_ready_reason is None

    # ------------------------------------------------------------------ xử lý ảnh
    @staticmethod
    def _decode_image(data: bytes | None) -> np.ndarray | None:
        if not data:
            return None
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return None
        h, w = image.shape[:2]
        if min(h, w) < _MIN_IMAGE_SIDE or h * w > _MAX_PIXELS:
            return None
        return image

    def _detect(self, image: np.ndarray) -> list[np.ndarray]:
        h, w = image.shape[:2]
        with self._lock:
            self._detector.setInputSize((w, h))
            _, faces = self._detector.detect(image)
        if faces is None:
            return []
        rows = [np.asarray(f, dtype=np.float32).reshape(-1) for f in faces]
        rows = [r for r in rows if r.size >= 15 and np.isfinite(r[:15]).all()]
        return sorted(rows, key=lambda r: -float(r[14]))

    @staticmethod
    def _measure(image: np.ndarray, face: np.ndarray) -> dict:
        h, w = image.shape[:2]
        x, y, bw, bh = (float(v) for v in face[:4])
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(w, int(x + bw)), min(h, int(y + bh))
        if x1 <= x0 or y1 <= y0:
            return {"valid": False}
        roi = cv2.cvtColor(cv2.resize(image[y0:y1, x0:x1], (_ROI_SIZE, _ROI_SIZE)), cv2.COLOR_BGR2GRAY)
        # Năm điểm mốc của YuNet: mắt phải, mắt trái, mũi, hai khóe miệng.
        pts = np.asarray(face[4:14], dtype=np.float64).reshape(5, 2)
        angle = float(np.degrees(np.arctan2(pts[1, 1] - pts[0, 1], pts[1, 0] - pts[0, 0])))
        roll = abs((angle + 90.0) % 180.0 - 90.0)
        return {
            "valid": True,
            "pixels": int(min(bw, bh)),
            "blur": float(cv2.Laplacian(roi, cv2.CV_64F).var()),
            "brightness": float(roi.mean()),
            "contrast": float(roi.std()),
            "roll": roll,
            "near_edge": bool(x0 < 4 or y0 < 4 or x1 > w - 4 or y1 > h - 4),
        }

    @staticmethod
    def _reject_reason(m: dict, min_pixels: int) -> str | None:
        if not m["valid"]:
            return REASON_INVALID_IMAGE
        if m["pixels"] < min_pixels:
            return REASON_FACE_TOO_SMALL
        if m["blur"] < settings.FACE_MIN_FACE_BLUR:
            return REASON_BLURRY
        if m["brightness"] < _DARK_LIMIT:
            return REASON_TOO_DARK
        if m["brightness"] > _BRIGHT_LIMIT:
            return REASON_TOO_BRIGHT
        if m["contrast"] < settings.FACE_MIN_CONTRAST:
            return REASON_LOW_CONTRAST
        if m["roll"] > _MAX_ROLL_DEGREES:
            return REASON_TILTED
        if m["near_edge"]:
            return REASON_NEAR_EDGE
        return None

    @staticmethod
    def _quality_score(m: dict, det_score: float, min_pixels: int) -> float:
        """Điểm "mắt xích yếu nhất" trong [0, 1]; qua cổng chất lượng thì >= 0.5. Heuristic."""
        parts = [
            min(1.0, m["pixels"] / (2.0 * max(min_pixels, 1))),
            min(1.0, m["blur"] / (2.0 * max(settings.FACE_MIN_FACE_BLUR, 1.0))),
            min(1.0, m["contrast"] / (2.0 * max(settings.FACE_MIN_CONTRAST, 1.0))),
            max(0.0, min(1.0, det_score)),
        ]
        return round(float(min(parts)), 4)

    def _embed(self, image: np.ndarray, face: np.ndarray) -> np.ndarray | None:
        try:
            with self._lock:
                aligned = self._recognizer.alignCrop(image, face)
                feature = self._recognizer.feature(aligned)
        except cv2.error:
            return None
        vec = np.asarray(feature, dtype=np.float32).reshape(-1)
        if vec.size != EMBEDDING_DIM or not np.isfinite(vec).all():
            return None
        norm = float(np.linalg.norm(vec))
        if norm < 1e-8:
            return None
        return (vec / norm).astype(np.float32)

    @staticmethod
    def _box(face: np.ndarray, width: int, height: int) -> FaceBox:
        x = min(max(float(face[0]) / width, 0.0), 1.0)
        y = min(max(float(face[1]) / height, 0.0), 1.0)
        w = min(max(float(face[2]) / width, 0.0), 1.0 - x)
        h = min(max(float(face[3]) / height, 0.0), 1.0 - y)
        return FaceBox(x=x, y=y, w=w, h=h, det_score=float(face[14]))

    # ------------------------------------------------------------------ API công khai bổ sung
    def analyze(self, image: bytes, min_pixels: int | None = None) -> list[FaceAnalysis] | None:
        """Phát hiện và đo chất lượng mọi khuôn mặt. None nếu ảnh không đọc được/engine chưa nạp."""
        if not self._ensure_loaded():
            return None
        img = self._decode_image(image)
        if img is None:
            return None
        limit = settings.FACE_MIN_FACE_PIXELS if min_pixels is None else min_pixels
        out: list[FaceAnalysis] = []
        for face in self._detect(img):
            m = self._measure(img, face)
            reason = self._reject_reason(m, limit)
            out.append(FaceAnalysis(
                x=float(face[0]), y=float(face[1]), w=float(face[2]), h=float(face[3]),
                det_score=float(face[14]), pixels=m.get("pixels", 0), blur=m.get("blur", 0.0),
                brightness=m.get("brightness", 0.0), contrast=m.get("contrast", 0.0),
                roll_degrees=m.get("roll", 0.0), near_edge=m.get("near_edge", False), reason=reason,
                quality_score=0.0 if not m["valid"] else self._quality_score(m, float(face[14]), limit),
            ))
        return out

    def extract_vector(self, image: bytes) -> tuple[np.ndarray | None, str | None, float | None]:
        """Ảnh đăng ký một người -> (vector chuẩn hóa, lý do từ chối, điểm chất lượng).

        Dùng chung cho đăng ký, reindex và các script đánh giá để mọi nơi cùng một quy tắc.
        """
        if not self._ensure_loaded():
            return None, REASON_ENGINE_NOT_READY, None
        img = self._decode_image(image)
        if img is None:
            return None, REASON_INVALID_IMAGE, None
        faces = self._detect(img)
        if not faces:
            return None, REASON_NO_FACE, None
        if len(faces) > 1:
            return None, REASON_MULTIPLE_FACES, None
        m = self._measure(img, faces[0])
        score = self._quality_score(m, float(faces[0][14]), settings.FACE_MIN_FACE_PIXELS) if m["valid"] else 0.0
        reason = self._reject_reason(m, settings.FACE_MIN_FACE_PIXELS)
        if reason:
            return None, reason, score
        vec = self._embed(img, faces[0])
        if vec is None:
            return None, REASON_FEATURE_FAILED, score
        return vec, None, score

    # ------------------------------------------------------------------ hợp đồng FaceEngine
    def assess_enrollment(self, image: bytes) -> EnrollResult:
        if not self.is_ready:
            # Giống mock: giữ ảnh ở trạng thái pending_embedding để reindex sau.
            return EnrollResult(ok=True, quality_score=None, embedding=None, reason=None)
        vec, reason, score = self.extract_vector(image)
        if vec is None:
            return EnrollResult(ok=False, quality_score=score, embedding=None, reason=reason or "rejected")
        return EnrollResult(ok=True, quality_score=score, embedding=encode_embedding(vec), reason=None)

    def embed_stored_image(self, image: bytes) -> EnrollResult:
        if not self.is_ready:
            return EnrollResult(ok=False, quality_score=None, embedding=None, reason=REASON_ENGINE_NOT_READY)
        vec, reason, score = self.extract_vector(image)
        if vec is None:
            return EnrollResult(ok=False, quality_score=score, embedding=None, reason=reason or "rejected")
        return EnrollResult(ok=True, quality_score=score, embedding=encode_embedding(vec), reason=None)

    @staticmethod
    def _gallery(candidates: list[Candidate]) -> list[tuple[int, np.ndarray]]:
        gallery: list[tuple[int, np.ndarray]] = []
        for candidate in candidates:
            vectors = [v for v in (_decode_cached(bytes(b)) for b in candidate.embeddings) if v is not None]
            if vectors:
                gallery.append((candidate.student_id, np.stack(vectors)))
        return gallery

    @staticmethod
    def _rank(vec: np.ndarray, gallery: list[tuple[int, np.ndarray]]) -> list[tuple[int, float]]:
        ranking = []
        for student_id, matrix in gallery:
            sims = np.sort(matrix @ vec)[::-1]
            ranking.append((student_id, float(np.mean(sims[:2]))))
        ranking.sort(key=lambda item: -item[1])
        return ranking

    def identify(self, image: bytes, candidates: list[Candidate]) -> list[MatchResult]:
        if not self.is_ready:
            return []
        img = self._decode_image(image)
        if img is None:
            return []
        height, width = img.shape[:2]
        faces = self._detect(img)[: max(1, settings.FACE_MAX_FACES_PER_FRAME)]
        if not faces:
            return []
        gallery = self._gallery(candidates)
        results: list[MatchResult] = []
        for face in faces:
            box = self._box(face, width, height)
            m = self._measure(img, face)
            if self._reject_reason(m, settings.FACE_IDENTIFY_MIN_FACE_PIXELS) is not None:
                results.append(MatchResult(box=box, student_id=None, status="low_quality", score=None, margin=None))
                continue
            vec = self._embed(img, face)
            if vec is None:
                results.append(MatchResult(box=box, student_id=None, status="low_quality", score=None, margin=None))
                continue
            ranking = self._rank(vec, gallery)
            if not ranking:
                results.append(MatchResult(box=box, student_id=None, status="unknown", score=None, margin=None))
                continue
            best_id, best = ranking[0]
            second = ranking[1][1] if len(ranking) > 1 else 0.0
            margin = best - second
            if best < settings.FACE_MATCH_THRESHOLD:
                results.append(MatchResult(box=box, student_id=None, status="unknown", score=best, margin=None))
            elif margin < settings.FACE_MARGIN_THRESHOLD:
                results.append(MatchResult(box=box, student_id=best_id, status="ambiguous", score=best, margin=margin))
            else:
                results.append(MatchResult(box=box, student_id=best_id, status="matched", score=best, margin=margin))
        return results
