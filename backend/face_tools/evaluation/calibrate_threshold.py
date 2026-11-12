"""Chọn ngưỡng cosine 1:1 trên manifest VALIDATION độc lập (FAR tối đa cho trước, FRR nhỏ nhất).

Ngưỡng này chỉ áp dụng so khớp cặp đơn mẫu. Chính sách trung bình hai mẫu tốt nhất và ``margin`` 1:N
cần được hiệu chỉnh/đo riêng bằng identification_eval. Không dùng ngưỡng chọn trên tập test.

    python -m face_tools.evaluation.calibrate_threshold --validation-manifest data/eval/val_pairs.json --max-far 0.01
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from face_tools.evaluation.recognition_eval import score_pairs


def calibrate_scores(rows, max_far: float = 0.01) -> dict:
    """rows = [(cosine, same), ...]; cần cả hai nhãn."""
    if not 0 <= max_far <= 1:
        raise ValueError("max_far phải trong [0, 1]")
    genuine = [float(s) for s, same in rows if same is True]
    impostor = [float(s) for s, same in rows if same is False]
    if not genuine or not impostor:
        raise ValueError("Cần cả cặp cùng người và khác người")
    if not all(math.isfinite(s) and -1.001 <= s <= 1.001 for s, _ in rows):
        raise ValueError("Cosine không hợp lệ")
    candidates = [-1.00001] + sorted({s for s, _ in rows}) + [1.00001]
    valid = []
    for threshold in candidates:
        fp = sum(s >= threshold for s in impostor)
        fn = sum(s < threshold for s in genuine)
        far, frr = fp / len(impostor), fn / len(genuine)
        if far <= max_far:
            valid.append((frr, far, -threshold, threshold, fp, fn))
    if not valid:
        raise ValueError("Không chọn được ngưỡng thỏa FAR yêu cầu")
    frr, far, _, threshold, fp, fn = min(valid)
    return {"threshold": round(threshold, 6), "false_accepts": fp, "false_rejects": fn,
            "n_genuine": len(genuine), "n_impostor": len(impostor),
            "validation_far": round(far, 6), "validation_frr": round(frr, 6), "requested_max_far": max_far,
            "caution": "Ít cặp thì độ bất định cao. Chỉ áp dụng cho cặp 1:1 đơn mẫu; 1:N nhiều mẫu cần đo riêng."}


def run(manifest: Path, out: Path, max_far: float) -> dict:
    scored, total, unique, rejected = score_pairs(manifest)
    result = calibrate_scores([(s, same) for s, same, *_ in scored], max_far)
    result.update(n_pairs_total=total, n_pairs_scored=len(scored), pairs_rejected_by_quality=len(rejected),
                  n_unique_images=unique,
                  note="Số liệu validation. Không suy ra FAR/FRR của tập test hay khả năng chống giả mạo.")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--validation-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/eval/threshold_validation.json"))
    parser.add_argument("--max-far", type=float, default=0.01)
    args = parser.parse_args()
    print(json.dumps(run(args.validation_manifest, args.out, args.max_far), ensure_ascii=False, indent=2))
