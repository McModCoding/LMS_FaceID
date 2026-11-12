"""So sánh thời gian và sai sót điểm danh thủ công với FaceID bằng số đo thật (không số bịa).

CSV: session_id, students, manual_seconds, face_seconds, manual_errors, face_errors
Mỗi dòng là một buổi đã đo, cùng danh sách sinh viên và điều kiện tương đương.

    python -m face_tools.evaluation.attendance_comparison --csv data/eval/attendance.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def evaluate(path: Path, out: Path) -> dict:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    if not rows:
        raise ValueError("Không có buổi học nào được đo")
    parsed = []
    for row in rows:
        try:
            count = int(row["students"])
            ms, fs = float(row["manual_seconds"]), float(row["face_seconds"])
            me, fe = int(row["manual_errors"]), int(row["face_errors"])
        except (KeyError, ValueError) as exc:
            raise ValueError("Sai tên cột hoặc dữ liệu không hợp lệ") from exc
        if count <= 0 or min(ms, fs) < 0 or not (0 <= me <= count and 0 <= fe <= count):
            raise ValueError("Giá trị không hợp lệ")
        parsed.append((count, ms, fs, me, fe))
    total = sum(p[0] for p in parsed)
    result = {"sessions": len(parsed), "student_instances": total,
              "total_manual_seconds": round(sum(p[1] for p in parsed), 3),
              "total_face_seconds": round(sum(p[2] for p in parsed), 3),
              "average_manual_sec_per_student": round(sum(p[1] for p in parsed) / total, 4),
              "average_face_sec_per_student": round(sum(p[2] for p in parsed) / total, 4),
              "manual_error_rate": round(sum(p[3] for p in parsed) / total, 6),
              "face_error_rate": round(sum(p[4] for p in parsed) / total, 6),
              "notes": "So sánh mô tả trên các ca đo; không suy luận ý nghĩa thống kê nếu thiếu thiết kế thực nghiệm."}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/eval/result_attendance.json"))
    args = parser.parse_args()
    evaluate(args.csv, args.out)
