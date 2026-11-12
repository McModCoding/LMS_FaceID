"""Đo tỷ lệ khuôn mặt bị loại do chất lượng trên khung hình lớp học có đồng ý.

    python -m face_tools.evaluation.classroom_frame_eval --images data/consented_frames --output data/eval/frames.json

Chỉ đo chất lượng trên mặt đã phát hiện; không đo recall mặt thật sự có trong ảnh và không phân tích
danh tính. Không đưa ảnh có thể nhận dạng người vào báo cáo công khai nếu chưa có đồng ý.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.core.config import settings
from face_tools.evaluation._common import load_engine

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def evaluate_dir(folder: Path) -> dict:
    engine = load_engine()
    min_pixels = settings.FACE_IDENTIFY_MIN_FACE_PIXELS
    counts: Counter = Counter()
    reasons: Counter = Counter()
    rows = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        counts["frames_attempted"] += 1
        faces = engine.analyze(path.read_bytes(), min_pixels=min_pixels)
        if faces is None:
            counts["frames_failed_to_process"] += 1
            rows.append({"frame_index": counts["frames_attempted"], "error": "unreadable"})
            continue
        counts["frames_processed"] += 1
        counts["faces_detected"] += len(faces)
        if not faces:
            counts["frames_without_detected_faces"] += 1
        if len(faces) > settings.FACE_MAX_FACES_PER_FRAME:
            counts["frames_over_face_limit"] += 1
        rejected = [f for f in faces if f.reason]
        counts["faces_quality_rejected"] += len(rejected)
        reasons.update(f.reason for f in rejected)
        rows.append({"frame_index": counts["frames_attempted"], "faces_detected": len(faces),
                     "faces_rejected": len(rejected)})
    n = counts["faces_detected"]
    return {"counts": dict(counts), "rejection_reasons": dict(reasons), "identify_min_face_pixels": min_pixels,
            "quality_rejection_rate_of_detected_faces": round(counts["faces_quality_rejected"] / n, 5) if n else None,
            "frames": rows,
            "limitations": "Chỉ đo chất lượng trên mặt đã phát hiện; không đo recall và không phân tích danh tính."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.images.is_dir():
        raise SystemExit("Không tìm thấy thư mục ảnh có đồng ý")
    result = evaluate_dir(args.images)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Đã ghi:", args.output)
