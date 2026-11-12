# Báo cáo kiểm thử V3.3 — 08/11/2026

Đây là bản ghi các phép kiểm tra thực tế ở môi trường tạo ZIP, **không phải bằng chứng đã chạy end-to-end trên Windows/Docker**.

| Kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Kiểm thử logic FaceID YuNet/SFace, công cụ evaluation | **42/42 PASS** | pytest chạy tách biệt với `backend/tests/conftest.py` để không chạm database; sử dụng detector/recognizer giả. |
| Cú pháp Python | **205 file hợp lệ** | Python compile, không chứng minh dependency import trên Docker. |
| Cú pháp TypeScript/JavaScript | **158 file hợp lệ** | TypeScript transpile diagnostics, không phải full typecheck hoặc npm build. |
| Docker Compose YAML, TOML, `.env.example`, cấu trúc ZIP | **Được phân tích cấu trúc** | Không thể thay cho `docker compose config` hoặc Docker build. |
| Thư viện Python/Node từ Internet | **Chưa cài lại đầy đủ tại môi trường kiểm thử** | Internet bị chặn; không được coi là đã build thành công. |
| PowerShell 5.1/.bat trên Windows | **Chưa chạy trực tiếp** | Môi trường tạo ZIP không có PowerShell Windows. |
| MySQL 8, Alembic, FastAPI/Swagger, đăng nhập 3 vai trò, React | **Chưa chạy end-to-end** | Môi trường không có Docker daemon. |
| ONNX thật, webcam, độ chính xác FaceID/FAR/FRR | **Chưa chạy** | Không có trọng số và tập ảnh thử nghiệm được đồng ý. |

### Cải tiến so với V3.2

- Docker project và volume **riêng** cho V3.3 để cài mới, tránh tái sử dụng DB cũ khi đã mất `.env`; không tự xóa database.
- Kiểm tra cổng có bị container cũ chiếm trước khi build, báo rõ cần stop container cũ.
- MySQL healthcheck SQL qua TCP và script `wait_for_mysql.py` xác nhận backend có thể thực hiện `SELECT 1` với tài khoản ứng dụng trước migration.
- Bổ sung `TEST_LMS_WINDOWS.bat`, kiểm thử logic 42 ca tách database, kiểm tra đăng nhập demo qua API thực và build frontend từ Node container.
- Setup, seed, chẩn đoán đều có thông báo lỗi; script không ghi đè `.env`, không tự reset mật khẩu hoặc seed trên DB không trống.

### Hướng dẫn nghiệm thu thực tế

1. Cài từ thư mục mới, Docker Desktop → `SETUP_LMS_WINDOWS.bat` → phải có HTTP 200.
2. `SEED_DEMO_WINDOWS.bat` chỉ với DB mới → xác nhận admin/gv001/sv001 đăng nhập được; seed lần hai phải từ chối.
3. Chạy `TEST_LMS_WINDOWS.bat` → giữ log đầu ra; nếu có lỗi, **chưa coi đã hoàn tất**.
4. Admin tạo user mới và truy vấn MySQL, kiểm tra các vai trò và dữ liệu đồng bộ.
5. Tải model, đánh giá engine ready, đăng ký mặt tự nguyện và thử điểm danh trên lớp hợp lệ, lưu ảnh/video minh chứng đã được đồng ý.
6. Chạy thực nghiệm detection/recognition trên validation/test độc lập; báo cáo số liệu đo được và ngưỡng/model SHA256. Không tự tạo con số.
7. Làm rõ yêu cầu Canvas LMS với nhóm/thầy; adapter chưa được triển khai.
