"""M9a: kiểm thử logic của OpenCVFaceEngine bằng detector/recognizer giả.

Không cần trọng số ONNX, webcam hay ảnh người thật. Các bài này chứng minh LOGIC (cổng chất lượng,
quy tắc điểm/margin, mã hóa embedding, trạng thái sẵn sàng); chúng KHÔNG đo độ chính xác nhận
diện. Độ chính xác chỉ có ý nghĩa khi chạy face_tools/evaluation trên ảnh có đồng ý của người thật.
"""

from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from app.core.config import Settings, settings  # noqa: E402
from app.face import opencv_engine as oe  # noqa: E402
from app.face.base import Candidate  # noqa: E402
from app.face.factory import get_engine  # noqa: E402

DIM = oe.EMBEDDING_DIM


# ----------------------------------------------------------------------------- tiện ích
def basis(i: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[i] = 1.0
    return v


def unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


def textured_image(size: int = 400, mean: float = 128.0, sigma: float = 40.0, fmt: str = ".png") -> bytes:
    rng = np.random.RandomState(0)
    img = np.clip(mean + rng.randn(size, size, 3) * sigma, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(fmt, img)
    assert ok
    return buf.tobytes()


def face_row(x: float, y: float, w: float, h: float, score: float = 0.9) -> list[float]:
    return [x, y, w, h,
            x + 0.3 * w, y + 0.35 * h, x + 0.7 * w, y + 0.35 * h,   # mắt phải, mắt trái
            x + 0.5 * w, y + 0.55 * h,                              # mũi
            x + 0.35 * w, y + 0.75 * h, x + 0.65 * w, y + 0.75 * h,  # khóe miệng
            score]


class FakeDetector:
    def __init__(self, rows):
        self.rows = rows
        self.input_size = None

    def setInputSize(self, size):  # noqa: N802 - tên của OpenCV
        self.input_size = size

    def detect(self, image):
        if not self.rows:
            return 0, None
        return 1, np.asarray(self.rows, dtype=np.float32).reshape(-1, 15)


class FakeRecognizer:
    def __init__(self, vectors=()):
        self.vectors = list(vectors)
        self.feature_calls = 0

    def alignCrop(self, image, face):  # noqa: N802
        return np.zeros((112, 112, 3), dtype=np.uint8)

    def feature(self, aligned):
        self.feature_calls += 1
        return np.asarray(self.vectors.pop(0), dtype=np.float32).reshape(1, -1)


@pytest.fixture
def tuned(monkeypatch):
    monkeypatch.setattr(settings, "FACE_MATCH_THRESHOLD", 0.6)
    monkeypatch.setattr(settings, "FACE_MARGIN_THRESHOLD", 0.1)
    monkeypatch.setattr(settings, "FACE_MIN_FACE_PIXELS", 100)
    monkeypatch.setattr(settings, "FACE_IDENTIFY_MIN_FACE_PIXELS", 64)
    monkeypatch.setattr(settings, "FACE_MIN_FACE_BLUR", 40.0)
    monkeypatch.setattr(settings, "FACE_MIN_CONTRAST", 19.0)
    monkeypatch.setattr(settings, "FACE_EMBEDDING_KEY", "")
    oe.clear_embedding_cache()
    yield
    oe.clear_embedding_cache()


def engine_with(rows, vectors=()):
    return oe.OpenCVFaceEngine(detector=FakeDetector(rows), recognizer=FakeRecognizer(vectors))


# ----------------------------------------------------------------------------- mã hóa embedding
def test_embedding_codec_plain_and_encrypted(monkeypatch, tuned):
    from cryptography.fernet import Fernet

    vec = unit(np.arange(1, DIM + 1, dtype=np.float32))
    plain = oe.encode_embedding(vec)
    assert len(plain) == DIM * 4
    assert np.allclose(oe.decode_embedding(plain), vec)

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "FACE_EMBEDDING_KEY", key)
    oe.clear_embedding_cache()
    token = oe.encode_embedding(vec)
    assert len(token) != DIM * 4 and token.startswith(b"gAAAA")
    assert np.allclose(oe.decode_embedding(token), vec)
    assert np.allclose(oe.decode_embedding(plain), vec), "dữ liệu cũ chưa mã hóa vẫn đọc được"

    monkeypatch.setattr(settings, "FACE_EMBEDDING_KEY", Fernet.generate_key().decode())
    oe.clear_embedding_cache()
    assert oe.decode_embedding(token) is None, "sai khóa không được giải mã"


@pytest.mark.parametrize("blob", [
    None, b"", b"short", b"x" * 700,
    np.full(DIM, np.nan, dtype=np.float32).tobytes(),
    np.zeros(DIM, dtype=np.float32).tobytes(),
    np.ones(DIM + 4, dtype=np.float32).tobytes(),
])
def test_decode_rejects_invalid_blobs(blob, tuned):
    assert oe.decode_embedding(blob) is None


# ----------------------------------------------------------------------------- trạng thái sẵn sàng
def test_not_ready_without_model_files_behaves_like_mock(monkeypatch, tmp_path, tuned):
    monkeypatch.setattr(settings, "FACE_MODELS_DIR", str(tmp_path))
    engine = oe.OpenCVFaceEngine()
    assert engine.is_ready is False
    assert engine.not_ready_reason == "model_missing"
    pending = engine.assess_enrollment(textured_image())
    assert pending.ok and pending.embedding is None and pending.reason is None
    stored = engine.embed_stored_image(textured_image())
    assert not stored.ok and stored.reason == "engine_not_ready"
    assert engine.identify(textured_image(), [Candidate(1, [oe.encode_embedding(basis(0))])]) == []


def test_not_ready_when_threshold_not_calibrated(monkeypatch, tuned):
    monkeypatch.setattr(settings, "FACE_MATCH_THRESHOLD", 0.0)
    engine = engine_with([face_row(120, 120, 160, 160)], [basis(0)])
    assert engine.is_ready is False and engine.not_ready_reason == "threshold_not_set"
    assert engine.identify(textured_image(), []) == []


def test_corrupt_model_file_is_reported_not_raised(monkeypatch, tmp_path, tuned):
    monkeypatch.setattr(settings, "FACE_MODELS_DIR", str(tmp_path))
    (tmp_path / settings.FACE_YUNET_MODEL).write_bytes(b"not an onnx model")
    (tmp_path / settings.FACE_SFACE_MODEL).write_bytes(b"not an onnx model")
    engine = oe.OpenCVFaceEngine()
    assert engine.is_ready is False
    assert engine.not_ready_reason == "model_load_failed"


# ----------------------------------------------------------------------------- đăng ký ảnh
def test_enrollment_accepts_single_clear_face_and_stores_normalized_vector(tuned):
    engine = engine_with([face_row(120, 120, 160, 160)], [basis(3) * 5.0])
    result = engine.assess_enrollment(textured_image())
    assert result.ok and result.reason is None
    assert result.quality_score is not None and result.quality_score >= 0.5
    stored = oe.decode_embedding(result.embedding)
    assert stored is not None and np.isclose(np.linalg.norm(stored), 1.0)
    assert np.allclose(stored, basis(3))


@pytest.mark.parametrize("rows,reason", [
    ([], "no_face"),
    ([face_row(20, 20, 160, 160), face_row(220, 120, 160, 160, 0.8)], "multiple_faces"),
    ([face_row(120, 120, 50, 50)], "face_too_small"),
    ([face_row(0, 0, 160, 160)], "near_edge"),
])
def test_enrollment_rejections(rows, reason, tuned):
    engine = engine_with(rows, [basis(0), basis(1)])
    result = engine.assess_enrollment(textured_image())
    assert not result.ok and result.reason == reason and result.embedding is None
    assert engine._recognizer.feature_calls == 0, "không trích xuất đặc trưng khi ảnh bị từ chối"


def test_enrollment_rejects_blurry_dark_and_bright_images(tuned):
    row = [face_row(120, 120, 160, 160)]
    assert engine_with(row).assess_enrollment(textured_image(sigma=0.5)).reason == "blurry"
    assert engine_with(row).assess_enrollment(textured_image(mean=20, sigma=6)).reason == "too_dark"
    assert engine_with(row).assess_enrollment(textured_image(mean=240, sigma=6)).reason == "too_bright"


def test_enrollment_rejects_unreadable_or_tiny_images(tuned):
    engine = engine_with([face_row(10, 10, 30, 30)])
    assert engine.assess_enrollment(b"not an image").reason == "invalid_image"
    assert engine.assess_enrollment(textured_image(size=64)).reason == "invalid_image"


def test_enrollment_feature_failure_is_reported(tuned):
    engine = engine_with([face_row(120, 120, 160, 160)], [np.full(DIM, np.nan)])
    assert engine.assess_enrollment(textured_image()).reason == "feature_failed"


# ----------------------------------------------------------------------------- nhận diện 1:N
def gallery():
    return [Candidate(1, [oe.encode_embedding(basis(0))]),
            Candidate(2, [oe.encode_embedding(basis(1))]),
            Candidate(3, [oe.encode_embedding(basis(2))])]


def test_identify_matched_with_margin(tuned):
    engine = engine_with([face_row(120, 120, 160, 160)], [basis(0)])
    [m] = engine.identify(textured_image(), gallery())
    assert m.status == "matched" and m.student_id == 1
    assert m.score == pytest.approx(1.0) and m.margin == pytest.approx(1.0)
    assert 0 <= m.box.x <= 1 and 0 <= m.box.y <= 1 and m.box.x + m.box.w <= 1 and m.box.y + m.box.h <= 1


def test_identify_ambiguous_when_two_students_equally_close(tuned):
    engine = engine_with([face_row(120, 120, 160, 160)], [unit(basis(0) + basis(1))])
    [m] = engine.identify(textured_image(), gallery())
    assert m.status == "ambiguous" and m.margin == pytest.approx(0.0, abs=1e-6)


def test_identify_unknown_below_threshold_has_no_identity(tuned):
    engine = engine_with([face_row(120, 120, 160, 160)], [basis(10)])
    [m] = engine.identify(textured_image(), gallery())
    assert m.status == "unknown" and m.student_id is None


def test_identify_single_candidate_margin_uses_zero_as_runner_up(tuned):
    engine = engine_with([face_row(120, 120, 160, 160)], [basis(0)])
    [m] = engine.identify(textured_image(), [Candidate(1, [oe.encode_embedding(basis(0))])])
    assert m.status == "matched" and m.margin == pytest.approx(m.score)


def test_one_lucky_sample_is_not_enough_top_two_mean(tuned):
    # Một mẫu khớp hoàn hảo, một mẫu trực giao -> trung bình hai mẫu tốt nhất = 0.5 < 0.6.
    cand = Candidate(4, [oe.encode_embedding(basis(3)), oe.encode_embedding(basis(4))])
    engine = engine_with([face_row(120, 120, 160, 160)], [basis(3)])
    [m] = engine.identify(textured_image(), [cand])
    assert m.status == "unknown"
    # Hai mẫu cùng gần truy vấn -> được chấp nhận.
    near = unit(basis(3) + 0.1 * basis(5))
    cand = Candidate(4, [oe.encode_embedding(basis(3)), oe.encode_embedding(near)])
    engine = engine_with([face_row(120, 120, 160, 160)], [basis(3)])
    [m] = engine.identify(textured_image(), [cand])
    assert m.status == "matched" and m.student_id == 4


def test_identify_low_quality_face_is_not_embedded(tuned):
    engine = engine_with([face_row(120, 120, 40, 40)], [basis(0)])
    [m] = engine.identify(textured_image(), gallery())
    assert m.status == "low_quality" and m.student_id is None and m.score is None
    assert engine._recognizer.feature_calls == 0


def test_identify_multiple_faces_returns_one_result_each_in_score_order(tuned):
    # Khuôn mặt 160 px khớp kích thước ROI 160x160 nên ảnh nhiễu giữ nguyên độ tương phản.
    rows = [face_row(20, 20, 160, 160, 0.8), face_row(220, 120, 160, 160, 0.95)]
    engine = engine_with(rows, [basis(1), basis(0)])  # khuôn mặt điểm cao được xử lý trước
    results = engine.identify(textured_image(), gallery())
    assert [r.student_id for r in results] == [2, 1]
    assert results[0].box.det_score == pytest.approx(0.95, abs=1e-6)


def test_identify_caps_faces_per_frame(monkeypatch, tuned):
    monkeypatch.setattr(settings, "FACE_MAX_FACES_PER_FRAME", 2)
    rows = [face_row(20 + 190 * i, 120, 160, 160, 0.9 - i * 0.01) for i in range(4)]
    engine = engine_with(rows, [basis(0)] * 4)
    results = engine.identify(textured_image(size=800), gallery())
    assert len(results) == 2 and all(r.status == "matched" for r in results)


def test_identify_ignores_embeddings_from_other_engines_and_empty_gallery(tuned):
    foreign = Candidate(9, [b"x" * 2048, np.ones(DIM + 1, dtype=np.float32).tobytes()])
    engine = engine_with([face_row(120, 120, 160, 160)], [basis(0)])
    [m] = engine.identify(textured_image(), [foreign])
    assert m.status == "unknown" and m.student_id is None


def test_identify_no_face_or_bad_image_returns_empty(tuned):
    assert engine_with([]).identify(textured_image(), gallery()) == []
    assert engine_with([face_row(120, 120, 160, 160)]).identify(b"junk", gallery()) == []


# ----------------------------------------------------------------------------- factory và cấu hình
def test_factory_selects_opencv_engine(monkeypatch):
    get_engine.cache_clear()
    monkeypatch.setattr(settings, "FACE_ENGINE", "opencv")
    try:
        assert isinstance(get_engine(), oe.OpenCVFaceEngine)
    finally:
        get_engine.cache_clear()


def test_config_rejects_malformed_embedding_key():
    with pytest.raises(ValueError):
        Settings(FACE_EMBEDDING_KEY="not-a-fernet-key")


def test_config_production_opencv_requires_embedding_key():
    base = dict(APP_ENV="production", SECRET_KEY="a1b2c3d4" * 8, DB_PASSWORD="Strong-db-pass-123")
    with pytest.raises(ValueError):
        Settings(FACE_ENGINE="opencv", FACE_EMBEDDING_KEY="", **base)


def test_embedding_key_is_not_exposed_in_repr():
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    assert key not in repr(Settings(FACE_EMBEDDING_KEY=key))
