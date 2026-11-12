# Đánh giá FaceID (M9)

Công cụ đo cho engine `FACE_ENGINE=opencv`. Chạy từ thư mục `backend`:

```
python face_tools/download_face_models.py
python face_tools/check_face_engine.py --image anh_cua_ban.jpg
python -m face_tools.evaluation.calibrate_threshold --validation-manifest data/eval/val_pairs.json --max-far 0.01
python -m face_tools.evaluation.recognition_eval    --manifest data/eval/test_pairs.json --threshold <từ validation>
python -m face_tools.evaluation.identification_eval --manifest data/eval/ident.json --threshold <t> --margin <m>
python -m face_tools.evaluation.detection_eval      --manifest data/eval/det.json
python -m face_tools.evaluation.classroom_frame_eval --images data/consented_frames --output data/eval/frames.json
python -m face_tools.evaluation.attendance_comparison --csv data/eval/attendance.csv
```

Quy tắc để số liệu dùng được trong báo cáo:

1. Chỉ dùng ảnh có đồng ý bằng văn bản; không commit ảnh/embedding (`data/` đã nằm trong `.gitignore`).
2. Tập validation (chọn ngưỡng) và tập test (báo cáo) tách rời; một người không xuất hiện ở cả hai nếu có thể.
3. Ghi nguyên tình trạng camera, ánh sáng, khoảng cách và SHA-256 của hai tệp trọng số.
4. Sau khi chọn `FACE_MATCH_THRESHOLD` và `FACE_MARGIN_THRESHOLD`, đo lại bằng `identification_eval`
   (đường xử lý giống hệ thống thật) rồi mới ghi vào `.env`.
5. Các script KHÔNG kiểm tra chống giả mạo (ảnh in/video). Báo cáo phải nêu rõ giới hạn này.
