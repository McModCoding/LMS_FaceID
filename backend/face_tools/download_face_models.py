"""Tải trọng số YuNet + SFace chính thức của OpenCV Zoo vào backend/models/face (cần mạng).

Không đóng gói trọng số theo mã nguồn (*.onnx nằm trong .gitignore). Script chỉ dùng thư viện chuẩn.
Sau khi tải, SHA-256 được in ra; hãy ghi lại và dùng --expect-yunet/--expect-sface ở các lần cài
đặt sau để bảo đảm mọi máy dùng cùng một bản trọng số (cần cho báo cáo thực nghiệm).

    python face_tools/download_face_models.py
    python face_tools/download_face_models.py --expect-yunet <sha256> --expect-sface <sha256>
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "models" / "face"
BASE = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
MODELS = {
    "face_detection_yunet_2023mar.onnx": "face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": "face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
MIN_SIZE = {"face_detection_yunet_2023mar.onnx": 100_000, "face_recognition_sface_2021dec.onnx": 20_000_000}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(name: str, relative: str, expected: str | None) -> None:
    target = ROOT / name
    if target.is_file() and target.stat().st_size >= MIN_SIZE[name]:
        print("Đã có:", name)
    else:
        print("Đang tải:", name, flush=True)
        part = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(BASE + relative, timeout=90) as response:  # noqa: S310 - URL cố định, HTTPS
            if not response.geturl().startswith("https://"):
                raise RuntimeError("Từ chối chuyển hướng không an toàn")
            with part.open("wb") as out:
                while chunk := response.read(1024 * 512):
                    out.write(chunk)
        if part.stat().st_size < MIN_SIZE[name]:
            part.unlink(missing_ok=True)
            raise RuntimeError("Tệp tải về quá nhỏ (có thể là con trỏ Git LFS)")
        part.replace(target)
    digest = sha256(target)
    print(f"  {name}: {target.stat().st_size} byte, SHA-256 {digest}")
    if expected and digest.lower() != expected.lower():
        target.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 của {name} không khớp giá trị mong đợi; đã xóa tệp")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--expect-yunet")
    parser.add_argument("--expect-sface")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    expected = {"face_detection_yunet_2023mar.onnx": args.expect_yunet,
                "face_recognition_sface_2021dec.onnx": args.expect_sface}
    try:
        for name, relative in MODELS.items():
            fetch(name, relative, expected[name])
    except Exception as exc:  # noqa: BLE001
        print("LỖI:", exc, file=sys.stderr)
        print("Tải thủ công từ https://github.com/opencv/opencv_zoo và đặt vào", ROOT, file=sys.stderr)
        return 1
    print("Hoàn tất. Chạy: python face_tools/check_face_engine.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
