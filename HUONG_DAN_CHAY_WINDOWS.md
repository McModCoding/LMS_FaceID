# LMS FaceID Nam + Thành — V3.3 (bản cài mới, Windows)

## Điều kiện

- Windows 10/11, Docker Desktop chạy Linux containers (Engine running), Internet cho lần build đầu.
- Không cần cài Python, MySQL, Node trên Windows. Các dịch vụ chạy bên trong Docker.
- Giải nén **toàn bộ** ZIP vào một thư mục đơn giản, ví dụ `D:\LMS_FaceID_V33`.
- Giữ `.env` bí mật. Không đăng ảnh thật hoặc file `.env`/database lên GitHub.
- V3.3 dùng **project `lms_faceid_capstone_v33` và volume `lms_faceid_capstone_v33_mysql_data` riêng**; không đụng vào volume V1/V2/V3 trước đó. Các cổng vẫn là 3307/8001/5174, do đó dừng container cũ đang chiếm cổng (không xóa volume).

## Làm từ đầu (chạy đúng thứ tự)

1. Mở **Docker Desktop** → kiểm tra `Engine running`.
2. Trong thư mục vừa giải nén, nhấn đúp **`SETUP_LMS_WINDOWS.bat`** (không chạy file V3.2 cũ).
   - Lần đầu chương trình tạo file `.env` với mật khẩu MySQL/JWT/Fernet ngẫu nhiên. Không chỉnh sửa hoặc xóa file `.env` sau khi có dữ liệu.
   - Script kiểm tra Docker và cổng, build image, kiểm tra import FastAPI/Pydantic/bcrypt, khởi động MySQL, xác nhận kết nối `SELECT 1` từ backend, chạy Alembic, cố tải model, khởi động backend/frontend và kiểm tra HTTP.
   - **Chỉ coi là thành công khi xuất hiện `PASS: backend, Swagger, OpenAPI and frontend HTTP 200` + `SUCCESS`.**
   - Model ONNX không tải được không làm dừng LMS; FaceID thật sẽ báo chưa sẵn sàng.
3. Mở giao diện `http://127.0.0.1:5174/` và API `http://127.0.0.1:8001/api/docs`. Thử `http://127.0.0.1:8001/health` (status ok).
4. Với database V3.3 **mới/trống**, chạy **`SEED_DEMO_WINDOWS.bat`** và nhập **`DEMO`**. Script từ chối nếu đã có user, không reset mật khẩu.
5. Đăng nhập lần lượt `admin / Demo@123`, `gv001 / Demo@123`, `sv001 / Demo@123` (các tài khoản khác thường có mật khẩu `DevPass@123`). Các mật khẩu mẫu chỉ để thử nghiệm; thay đổi ngay khi cần dùng dữ liệu thực tế.
6. Nhấn đúp **`TEST_LMS_WINDOWS.bat`**: xác nhận endpoint, import/auth, MySQL TCP, thông tin tài khoản, bộ kiểm thử FaceID 42 ca không dùng database và frontend build. Kết quả lưu trong `LMS_V33_LAST_RUN.log`.
7. Trên tài khoản sinh viên vào đăng ký khuôn mặt với ảnh đã được đồng ý; với tài khoản giảng viên tạo/mở buổi học và thử điểm danh. Cần tải model YuNet+SFace và chạy thử với dữ liệu thật mới có thể kết luận nhận diện chính xác.

## Dùng những lần sau

- Mở Docker Desktop → nhấn `START_LMS_WINDOWS.bat`.
- Để dừng: `STOP_LMS_WINDOWS.bat` (không xóa dữ liệu).
- Không lặp lại seed nếu đã có user; không dùng `docker compose down -v` hay `docker volume rm`.

## Các câu lệnh PowerShell hữu ích

Mở PowerShell tại thư mục có `docker-compose.yml`:

```powershell
docker compose ps
curl.exe -i http://127.0.0.1:8001/health
docker compose logs --tail=100 backend
docker compose logs --tail=100 mysql
```

Nếu setup bị lỗi, chạy **`DIAGNOSE_LMS_WINDOWS.bat`**; xem `KET_QUA_DIAGNOSE.txt` và `LMS_V33_LAST_RUN.log`. Đọc lại và che mọi thông tin nhạy cảm trước khi chia sẻ.

Nếu thấy báo cổng 5174/8001/3307 đang bận: mở Docker Desktop → Containers → **Stop** các container V1/V2/V3 cũ đang chạy. **Đừng Delete/Remove volume**.

Nếu `.env` đã bị mất nhưng `lms_faceid_capstone_v33_mysql_data` còn tồn tại: **khôi phục `.env` đã sao lưu**, không tạo lại khóa để tránh mất khả năng đăng nhập/giải mã dữ liệu.

## Đánh giá chất lượng FaceID và báo cáo khóa luận

Trong thư mục `backend/face_tools/evaluation` đã có công cụ kiểm thử/hiệu chỉnh. Ngưỡng nhận diện chỉ là giá trị mẫu, chưa được xác nhận với tập dữ liệu người thật. Không công bố độ chính xác/Precision/Recall/FAR/FRR nếu chưa chạy thực nghiệm. Hệ thống chưa có bảo vệ chống giả mạo khuôn mặt (liveness) được chứng minh.

## Chức năng giới hạn

- Giữ nguyên LMS/FaceID của bản gốc; **không có đăng ký tài khoản sinh viên công khai**. Admin tạo user.
- Canvas LMS chưa được tích hợp vào backend chính.
- Việc kiểm chứng Docker/MySQL/React/điểm danh hoàn chỉnh phải thực hiện trên máy Windows đang chạy Docker thật. Các phép kiểm tra trước khi phát hành gói không thay thế nghiệm thu.
