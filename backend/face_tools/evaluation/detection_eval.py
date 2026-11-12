"""Đánh giá phát hiện khuôn mặt: IoU, precision, recall, F1, độ trễ.

Manifest JSON: [{"image": "images/001.jpg", "boxes": [[x, y, w, h], ...]}, ...] (điểm ảnh, đường dẫn
tương đối với manifest). Chỉ đo trên đúng các ảnh được liệt kê; không tự tạo nhãn hay số liệu.

    python -m face_tools.evaluation.detection_eval --manifest data/eval/det.json
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

from face_tools.evaluation._common import load_engine, resolve


def iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    inter = max(0.0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0.0, min(ay + ah, by + bh) - max(ay, by))
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def match_counts(gt, pred, threshold=0.5):
    pairs = sorted(((iou(g, p), i, j) for i, g in enumerate(gt) for j, p in enumerate(pred)
                    if iou(g, p) >= threshold), reverse=True)
    used_g, used_p = set(), set()
    for _, i, j in pairs:
        if i not in used_g and j not in used_p:
            used_g.add(i)
            used_p.add(j)
    return len(used_g), len(pred) - len(used_p), len(gt) - len(used_g)


def evaluate(manifest: Path, out: Path, threshold: float) -> dict:
    items = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("Manifest phải là mảng không rỗng")
    engine = load_engine()
    out.mkdir(parents=True, exist_ok=True)
    tp = fp = fn = unreadable = 0
    times, rows = [], []
    for item in items:
        path = resolve(manifest, item["image"])
        gt = item["boxes"]
        if not isinstance(gt, list) or any(len(b) != 4 for b in gt):
            raise ValueError("Nhãn bbox không hợp lệ: " + str(item["image"]))
        start = time.perf_counter()
        faces = engine.analyze(path.read_bytes())
        elapsed = (time.perf_counter() - start) * 1000
        if faces is None:
            unreadable += 1
            continue
        a, b, c = match_counts(gt, [[f.x, f.y, f.w, f.h] for f in faces], threshold)
        tp, fp, fn = tp + a, fp + b, fn + c
        times.append(elapsed)
        rows.append({"image": item["image"], "gt_faces": len(gt), "pred_faces": len(faces),
                     "TP": a, "FP": b, "FN": c, "latency_ms": round(elapsed, 3)})
    if not rows:
        raise ValueError("Không ảnh nào đọc được")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    mean = statistics.mean(times)
    result = {"model": engine.version, "num_images": len(rows), "unreadable_images": unreadable,
              "iou_threshold": threshold, "TP": tp, "FP": fp, "FN": fn,
              "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6),
              "latency_mean_ms": round(mean, 3), "latency_median_ms": round(statistics.median(times), 3),
              "fps_estimate_from_mean_latency": round(1000 / mean, 3) if mean > 0 else None,
              "metric_scope": "Độ trễ gồm giải mã ảnh, phát hiện và đo chất lượng trên máy chạy script; "
                              "không phải độ trễ end-to-end qua mạng/trình duyệt. Không suy ra tổng quát hóa."}
    with (out / "per_image.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (out / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/eval/results_detection"))
    parser.add_argument("--iou", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 < args.iou <= 1:
        parser.error("IoU phải nằm trong (0, 1]")
    evaluate(args.manifest, args.out, args.iou)
