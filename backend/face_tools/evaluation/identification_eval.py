"""Đánh giá định danh 1:N bằng ĐÚNG đường xử lý của hệ thống (engine.identify + ngưỡng + margin).

Manifest:
  {"gallery": {"sv01": ["images/a1.jpg", "images/a2.jpg"], "sv02": [...]},
   "queries": [{"image": "images/q1.jpg", "identity": "sv01"}, {"image": "images/la.jpg", "identity": null}]}

Ảnh test KHÔNG được trùng ảnh gallery; ngưỡng/margin phải chọn trước trên validation. Mỗi ảnh truy vấn
nên chứa đúng một khuôn mặt; nếu có nhiều, dùng khuôn mặt có điểm phát hiện cao nhất.

    python -m face_tools.evaluation.identification_eval --manifest data/eval/ident.json --threshold 0.363 --margin 0.05
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.face.base import Candidate
from app.face.opencv_engine import encode_embedding
from face_tools.evaluation._common import load_engine, resolve


def evaluate(manifest: Path, out: Path, threshold: float, margin: float) -> dict:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    gallery, queries = data.get("gallery", {}), data.get("queries", [])
    if not isinstance(gallery, dict) or len(gallery) < 2 or not queries:
        raise ValueError("Cần ít nhất 2 danh tính trong gallery và có truy vấn")
    settings.FACE_MATCH_THRESHOLD = threshold
    settings.FACE_MARGIN_THRESHOLD = margin
    engine = load_engine(require_ready_thresholds=True)

    seen: set[Path] = set()
    ids = {name: index for index, name in enumerate(gallery, start=1)}
    candidates, enroll_rejected = [], Counter()
    for name, images in gallery.items():
        blobs = []
        for relative in images:
            path = resolve(manifest, relative)
            if path in seen:
                raise ValueError("Một ảnh không được dùng ở nhiều chỗ: " + str(relative))
            seen.add(path)
            vec, reason, _ = engine.extract_vector(path.read_bytes())
            if vec is None:
                enroll_rejected[reason] += 1
            else:
                blobs.append(encode_embedding(vec))
        if not blobs:
            raise ValueError("Không đăng ký được ảnh nào cho " + name)
        candidates.append(Candidate(student_id=ids[name], embeddings=blobs))

    names = {v: k for k, v in ids.items()}
    counts: Counter = Counter()
    rows = []
    for item in queries:
        truth = item.get("identity")
        if truth is not None and truth not in ids:
            raise ValueError("Danh tính truy vấn không có trong gallery: " + str(truth))
        path = resolve(manifest, item["image"])
        if path in seen:
            raise ValueError("Ảnh test trùng ảnh gallery: " + str(item["image"]))
        results = engine.identify(path.read_bytes(), candidates)
        top = results[0] if results else None
        status = top.status if top else "no_face"
        predicted = names.get(top.student_id) if top and status == "matched" else None
        if truth is None:
            label = "unknown_rejected" if predicted is None else "unknown_accepted"
        elif predicted == truth:
            label = "correct_identity"
        elif predicted is None:
            label = "known_rejected"
        else:
            label = "wrong_identity"
        counts[label] += 1
        rows.append({"image": item["image"], "truth": truth, "predicted": predicted, "engine_status": status,
                     "result": label, "score": round(top.score, 5) if top and top.score is not None else None,
                     "margin": round(top.margin, 5) if top and top.margin is not None else None})
    known = counts["correct_identity"] + counts["known_rejected"] + counts["wrong_identity"]
    unknown = counts["unknown_rejected"] + counts["unknown_accepted"]
    summary = {"threshold": threshold, "margin": margin, "n_queries": len(rows), "counts": dict(counts),
               "enrollment_images_rejected": dict(enroll_rejected),
               "known_identification_rate": counts["correct_identity"] / known if known else None,
               "wrong_identity_rate_known": counts["wrong_identity"] / known if known else None,
               "unknown_rejection_rate": counts["unknown_rejected"] / unknown if unknown else None,
               "note": "Tỷ lệ trên tập cụ thể; không đại diện chống giả mạo hay điều kiện ngoài tập. "
                       "Định danh sai (wrong_identity) và nhận nhầm người lạ (unknown_accepted) là lỗi nghiêm trọng nhất."}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "decisions.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/eval/results_identification"))
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--margin", type=float, required=True)
    args = parser.parse_args()
    evaluate(args.manifest, args.out, args.threshold, args.margin)
