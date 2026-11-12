# Engine FaceID OpenCV (M9a): YuNet + SFace

Engine thật cắm vào hợp đồng `FaceEngine` (SPEC mục 7) bằng một file: `backend/app/face/opencv_engine.py`.
Mặc định hệ thống vẫn dùng `FACE_ENGINE=mock`. Engine này **chưa được hiệu chỉnh hay đo độ chính xác**
cho đến khi bạn chạy các script trong `backend/face_tools/evaluation` trên ảnh có đồng ý của người thật.

## Bật engine bằng Docker (khuyến nghị; PowerShell, tại thư mục gốc có `docker-compose.yml`)

Compose gắn `./scripts` đè lên `/app/scripts` trong container, vì vậy công cụ FaceID nằm ở `backend/face_tools`.

```powershell
docker compose build                                               # cài thêm opencv (extra "face")
docker compose run --rm backend python face_tools/download_face_models.py   # cần mạng; ghi lại 2 SHA-256
docker compose run --rm backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Chạy không dùng Docker: trong thư mục `backend`, `python -m pip install -e ".[dev,face]"` rồi chạy các lệnh
`python face_tools/...` như trên.

Trong `.env` (không commit):

```
FACE_ENGINE=opencv
FACE_EMBEDDING_KEY=<khóa vừa sinh>
FACE_MATCH_THRESHOLD=0.363     # tạm thời; phải hiệu chỉnh
FACE_MARGIN_THRESHOLD=0.05     # tạm thời; phải hiệu chỉnh
```

Kiểm tra rồi khởi động lại backend:

```powershell
# Đặt ảnh vào backend\data\eval\ (thư mục này nằm ngoài Git) để container nhìn thấy
docker compose run --rm backend python face_tools/check_face_engine.py --image data/eval/anh.jpg
docker compose up -d backend frontend
```

Nếu sinh viên đã đăng ký ảnh khi còn mock (trạng thái `pending_embedding`), quản trị viên gọi
`POST /admin/face/reindex` để tạo embedding từ ảnh đã lưu (chỉ cho consent còn hiệu lực).

## Hành vi

| Tình huống | Kết quả |
|---|---|
| Thiếu trọng số, trọng số hỏng, hoặc `FACE_MATCH_THRESHOLD <= 0` | `is_ready=false`: giống mock (ảnh vào `pending_embedding`, `/recognize` trả `ready=false`), giao diện hiện banner |
| Ảnh đăng ký có đúng một khuôn mặt đạt chất lượng | Lưu embedding 128 chiều (mã hóa Fernet nếu có `FACE_EMBEDDING_KEY`), `status=active` |
| Ảnh đăng ký bị từ chối | Mã lý do: `invalid_image`, `no_face`, `multiple_faces`, `face_too_small`, `blurry`, `too_dark`, `too_bright`, `low_contrast`, `tilted_head`, `near_edge`, `feature_failed` |
| Khung hình điểm danh | Tối đa `FACE_MAX_FACES_PER_FRAME` khuôn mặt; mỗi mặt: `matched` / `ambiguous` / `unknown` / `low_quality` |

Quy tắc điểm: điểm của một sinh viên là trung bình hai độ tương đồng cosine cao nhất với các mẫu của
sinh viên đó; `margin` là chênh lệch với sinh viên tốt thứ hai (chỉ một ứng viên thì coi thứ hai là 0).
`services/face_service.py` và `attendance_service.py` vẫn là nơi áp ngưỡng, chuỗi `FACE_MIN_HITS` và
chống tính lặp theo `frame_id`; engine chỉ đưa ra điểm và trạng thái đề xuất. Khuôn mặt không đạt chất
lượng được ghi vào nhật ký với trạng thái `unknown` (service gộp mọi kết quả không có `student_id`).

## Quyền riêng tư và bảo mật

- Production với `FACE_ENGINE=opencv` bắt buộc có `FACE_EMBEDDING_KEY`; khóa sai định dạng làm ứng dụng
  không khởi động. Mất khóa nghĩa là mất khả năng đọc embedding cũ (phải đăng ký lại hoặc reindex).
- Bật khóa sau khi đã có embedding thô: engine vẫn đọc được dữ liệu cũ; reindex/đăng ký lại để mã hóa.
- Ảnh, embedding và trọng số không được commit (`.gitignore`). Consent, thu hồi và xóa dữ liệu giữ nguyên
  như M4/F07.

## Giới hạn đã biết (đừng trình bày như tính năng)

- **Không chống giả mạo** (ảnh in, màn hình, video phát lại); `frame_id` chỉ chống tính lặp retry.
- Ngưỡng chất lượng (độ nét, sáng, tương phản, nghiêng) là heuristic trên ROI 160x160, chưa hiệu chỉnh cho camera lớp học.
- Khuôn mặt sát mép khung hình bị loại; sinh viên ngồi xa có thể dưới `FACE_IDENTIFY_MIN_FACE_PIXELS`.
  Hãy đo tỷ lệ này bằng `face_tools.evaluation.classroom_frame_eval`.
- Chỉ có một ứng viên có mẫu trong lớp thì `margin` luôn bằng điểm: người lạ có điểm vượt ngưỡng sẽ bị nhận nhầm.
  Đây là giới hạn của nhận diện tập đóng; đo bằng `identification_eval` (chỉ số `unknown_accepted`).
- Chọn YuNet + SFace thay cho InsightFace (SCRFD + ArcFace) ghi ở SPEC mục 3 theo yêu cầu của chủ dự án;
  InsightFace vẫn có thể cắm sau qua `FACE_ENGINE=insightface`.
- Kiểm thử trong repo dùng detector/recognizer giả để chứng minh logic; chúng không đo độ chính xác.
