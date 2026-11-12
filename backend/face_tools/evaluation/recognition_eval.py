"""Xác minh cặp ảnh 1:1: cosine, FAR, FRR và tỷ lệ ảnh không đạt chất lượng (FTA).

Manifest: [{"image_a": "...", "image_b": "...", "same": true}, ...]. Ngưỡng phải được chọn trên tập
validation độc lập (calibrate_threshold) rồi mới áp lên tập test; không chọn ngưỡng trên test.

    python -m face_tools.evaluation.recognition_eval --manifest data/eval/test_pairs.json --threshold 0.363
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from face_tools.evaluation._common import load_engine, resolve


def score_pairs(manifest: Path, engine=None):
    """Trả (các cặp (cosine, same), số cặp bị loại, số ảnh duy nhất, lý do bị loại)."""
    items = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("Manifest rỗng")
    engine = engine or load_engine()
    cache: dict[Path, tuple] = {}
    scored, rejected_reasons = [], []
    for item in items:
        if not isinstance(item.get("same"), bool):
            raise ValueError("'same' phải là true/false")
        vectors = []
        for key in ("image_a", "image_b"):
            path = resolve(manifest, item[key])
            if path not in cache:
                cache[path] = engine.extract_vector(path.read_bytes())
            vectors.append(cache[path])
        if any(v[0] is None for v in vectors):
            rejected_reasons.append([v[1] for v in vectors if v[0] is None][0])
            continue
        scored.append((float(np.dot(vectors[0][0], vectors[1][0])), item["same"], item["image_a"], item["image_b"]))
    return scored, len(items), len(cache), rejected_reasons


def evaluate(manifest: Path, out: Path, threshold: float) -> dict:
    scored, total, unique, rejected = score_pairs(manifest)
    tp = sum(s >= threshold and same for s, same, *_ in scored)
    fn = sum(s < threshold and same for s, same, *_ in scored)
    fp = sum(s >= threshold and not same for s, same, *_ in scored)
    tn = sum(s < threshold and not same for s, same, *_ in scored)
    if not (tp + fn) or not (fp + tn):
        raise ValueError("Cần cả cặp cùng người và khác người (sau khi loại ảnh kém chất lượng)")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "pairs.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["image_a", "image_b", "same_person", "cosine", "accepted"])
        for s, same, a, b in scored:
            writer.writerow([a, b, same, round(s, 6), s >= threshold])
    result = {"n_pairs_total": total, "n_pairs_scored": len(scored), "pairs_rejected_by_quality": len(rejected),
              "rejection_reasons": {r: rejected.count(r) for r in sorted(set(rejected))},
              "n_unique_images": unique, "threshold": threshold,
              "genuine_accepted_TP": tp, "genuine_rejected_FN": fn,
              "impostor_accepted_FP": fp, "impostor_rejected_TN": tn,
              "FAR": round(fp / (fp + tn), 6), "FRR": round(fn / (tp + fn), 6),
              "accuracy": round((tp + tn) / len(scored), 6),
              "warning": "Xác minh 1:1 trên các cặp đã cho, không phải độ chính xác định danh 1:N; "
                         "không kiểm tra chống giả mạo. Cặp bị loại vì chất lượng KHÔNG nằm trong FAR/FRR."}
    (out / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/eval/results_recognition"))
    parser.add_argument("--threshold", type=float, required=True, help="đã chọn từ validation, không chọn trên test")
    args = parser.parse_args()
    evaluate(args.manifest, args.out, args.threshold)
