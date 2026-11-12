"""Kiểm tra engine FaceID thật (OpenCV YuNet + SFace) đã sẵn sàng chưa.

    python face_tools/check_face_engine.py
    python face_tools/check_face_engine.py --image anh.jpg                 # phát hiện + chất lượng
    python face_tools/check_face_engine.py --image-a a.jpg --image-b b.jpg # độ tương đồng cosine

Chỉ in kết quả đo được; không suy diễn độ chính xác. Dùng ảnh của chính bạn hoặc ảnh có đồng ý.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.face.opencv_engine import OpenCVFaceEngine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path)
    parser.add_argument("--image-a", type=Path)
    parser.add_argument("--image-b", type=Path)
    args = parser.parse_args()

    engine = OpenCVFaceEngine()
    yunet, sface = engine._model_paths()
    print(f"Engine         : {engine.name} {engine.version}")
    print(f"FACE_ENGINE    : {settings.FACE_ENGINE} (phải là 'opencv' để hệ thống dùng engine này)")
    print(f"YuNet          : {yunet} ({'có' if yunet.is_file() else 'THIẾU'})")
    print(f"SFace          : {sface} ({'có' if sface.is_file() else 'THIẾU'})")
    print(f"Mã hóa embedding: {'bật' if settings.FACE_EMBEDDING_KEY.strip() else 'TẮT (đặt FACE_EMBEDDING_KEY)'}")
    print(f"Ngưỡng         : match={settings.FACE_MATCH_THRESHOLD} margin={settings.FACE_MARGIN_THRESHOLD} "
          "(phải hiệu chỉnh bằng face_tools/evaluation)")
    print(f"is_ready       : {engine.is_ready}" + ("" if engine.is_ready else f"  (lý do: {engine.not_ready_reason})"))

    if args.image:
        faces = engine.analyze(args.image.read_bytes())
        if faces is None:
            print("Không đọc được ảnh hoặc mô hình chưa nạp.")
            return 1
        print(f"Số khuôn mặt   : {len(faces)}")
        for i, f in enumerate(faces, 1):
            print(f"  #{i}: box=({f.x:.0f},{f.y:.0f},{f.w:.0f},{f.h:.0f}) det={f.det_score:.3f} "
                  f"px={f.pixels} blur={f.blur:.1f} sáng={f.brightness:.1f} tương phản={f.contrast:.1f} "
                  f"nghiêng={f.roll_degrees:.1f}° sát mép={f.near_edge} lý do loại={f.reason}")
    if args.image_a and args.image_b:
        va, ra, _ = engine.extract_vector(args.image_a.read_bytes())
        vb, rb, _ = engine.extract_vector(args.image_b.read_bytes())
        if va is None or vb is None:
            print(f"Không trích xuất được: a={ra} b={rb}")
            return 1
        print(f"Cosine(a, b)   : {float(np.dot(va, vb)):.4f}")
    return 0 if engine.is_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
