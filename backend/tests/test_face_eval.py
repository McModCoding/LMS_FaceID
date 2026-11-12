"""M9a: kiểm thử các script đánh giá bằng engine giả (không cần ảnh người thật hay trọng số)."""

from __future__ import annotations

import json

import pytest

cv2 = pytest.importorskip("cv2")

from app.core.config import settings  # noqa: E402
from app.face import opencv_engine as oe  # noqa: E402
from face_tools.evaluation import attendance_comparison, calibrate_threshold, identification_eval  # noqa: E402
from face_tools.evaluation.detection_eval import iou, match_counts  # noqa: E402
from tests.test_opencv_engine import (  # noqa: E402
    FakeDetector,
    FakeRecognizer,
    basis,
    face_row,
    textured_image,
)


def test_calibrate_picks_lowest_frr_within_far_limit():
    rows = [(0.9, True), (0.8, True), (0.7, True), (0.4, True),
            (0.5, False), (0.3, False), (0.2, False), (0.1, False)]
    result = calibrate_threshold.calibrate_scores(rows, max_far=0.0)
    assert result["validation_far"] == 0.0 and result["false_accepts"] == 0
    assert 0.5 < result["threshold"] <= 0.7 and result["false_rejects"] == 1


@pytest.mark.parametrize("rows,max_far", [
    ([(0.9, True)], 0.01),            # thiếu cặp khác người
    ([(0.1, False)], 0.01),           # thiếu cặp cùng người
    ([(0.9, True), (0.1, False)], 2),  # max_far ngoài [0, 1]
    ([(float("nan"), True), (0.1, False)], 0.1),
])
def test_calibrate_rejects_invalid_input(rows, max_far):
    with pytest.raises(ValueError):
        calibrate_threshold.calibrate_scores(rows, max_far)


def test_iou_and_matching():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)
    assert iou([0, 0, 10, 10], [20, 20, 5, 5]) == 0.0
    assert match_counts([[0, 0, 10, 10]], [[1, 1, 10, 10], [50, 50, 5, 5]]) == (1, 1, 0)


def test_attendance_comparison_computes_rates_and_rejects_bad_rows(tmp_path):
    good = tmp_path / "good.csv"
    good.write_text("session_id,students,manual_seconds,face_seconds,manual_errors,face_errors\n"
                    "1,40,240,60,2,1\n2,20,120,40,0,0\n", encoding="utf-8")
    result = attendance_comparison.evaluate(good, tmp_path / "out.json")
    assert result["student_instances"] == 60 and result["manual_error_rate"] == pytest.approx(2 / 60, abs=1e-6)
    bad = tmp_path / "bad.csv"
    bad.write_text("session_id,students,manual_seconds,face_seconds,manual_errors,face_errors\n"
                   "1,10,60,30,11,0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        attendance_comparison.evaluate(bad, tmp_path / "out2.json")


def test_identification_eval_counts_use_the_production_decision_path(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "FACE_MATCH_THRESHOLD", 0.5)
    monkeypatch.setattr(settings, "FACE_MARGIN_THRESHOLD", 0.1)
    monkeypatch.setattr(settings, "FACE_EMBEDDING_KEY", "")
    oe.clear_embedding_cache()
    names = ["g_a", "g_b", "q1", "q2", "q3", "q4"]
    for name in names:
        (tmp_path / f"{name}.png").write_bytes(textured_image())
    # Thứ tự trích xuất: gallery (e0, e1), rồi truy vấn (e0, e1, e7, e0).
    vectors = [basis(0), basis(1), basis(0), basis(1), basis(7), basis(0)]
    engine = oe.OpenCVFaceEngine(detector=FakeDetector([face_row(120, 120, 160, 160)]),
                                 recognizer=FakeRecognizer(vectors))
    monkeypatch.setattr(identification_eval, "load_engine", lambda require_ready_thresholds=False: engine)
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "gallery": {"sv01": ["g_a.png"], "sv02": ["g_b.png"]},
        "queries": [{"image": "q1.png", "identity": "sv01"}, {"image": "q2.png", "identity": "sv02"},
                    {"image": "q3.png", "identity": None}, {"image": "q4.png", "identity": None}],
    }), encoding="utf-8")
    summary = identification_eval.evaluate(manifest, tmp_path / "out", 0.5, 0.1)
    assert summary["counts"] == {"correct_identity": 2, "unknown_rejected": 1, "unknown_accepted": 1}
    assert summary["unknown_rejection_rate"] == pytest.approx(0.5)
    assert summary["known_identification_rate"] == pytest.approx(1.0)


def test_identification_eval_refuses_reused_images(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "FACE_MATCH_THRESHOLD", 0.5)
    monkeypatch.setattr(settings, "FACE_MARGIN_THRESHOLD", 0.1)
    (tmp_path / "a.png").write_bytes(textured_image())
    (tmp_path / "b.png").write_bytes(textured_image())
    engine = oe.OpenCVFaceEngine(detector=FakeDetector([face_row(120, 120, 160, 160)]),
                                 recognizer=FakeRecognizer([basis(0), basis(1), basis(0)]))
    monkeypatch.setattr(identification_eval, "load_engine", lambda require_ready_thresholds=False: engine)
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"gallery": {"x": ["a.png"], "y": ["b.png"]},
                                    "queries": [{"image": "a.png", "identity": "x"}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        identification_eval.evaluate(manifest, tmp_path / "out", 0.5, 0.1)
