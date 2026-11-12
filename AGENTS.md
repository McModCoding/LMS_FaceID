# Quy tắc dự án CNTT-KLCN360

- Trước mọi việc, đọc toàn bộ SPEC.md ở thư mục gốc. SPEC.md là nguồn sự thật duy nhất.
- Chỉ làm đúng cột mốc (mục 12 của SPEC.md) mà người dùng chỉ định. Không làm trước cột mốc sau.
- Không thêm tính năng ngoài phạm vi P0/P1. Không làm P2.
- Mọi thay đổi database đi qua Alembic migration.
- Logic nghiệp vụ nằm ở backend/app/services/, không nằm trong router hay component React.
- Trước khi báo xong: chạy ruff, pytest, tsc --noEmit, eslint; chạy lại scripts/seed.py từ DB trống.
- Không commit .env, ảnh khuôn mặt, file dump database.
- Không có nút "giả lập nhận diện" trong bản nộp (xem mục 7.4 của SPEC.md).
- Khi yêu cầu mâu thuẫn hoặc thiếu thông tin: hỏi lại, đừng đoán.
Quy tắc bổ sung:
- Ngày và giờ của buổi học là giờ địa phương Asia/Ho_Chi_Minh, lưu bằng DATE và TIME, không đổi sang UTC.
- Khi một lệnh lỗi: thử tối đa 3 hướng khác nhau, sau đó DỪNG, tóm tắt nguyên nhân và hỏi người dùng. Khi sửa chỉ chạy lại lệnh liên quan.
- Không chạy lệnh phá hủy khi chưa hỏi: docker volume prune/rm, docker-compose down -v, drop database, rm -rf, git reset --hard, git clean. Không tự git commit hoặc push.
- Giao diện: mỗi màn hình có skeleton khi tải, trạng thái rỗng có hướng dẫn, hiển thị lỗi thật từ backend, đúng ở cả chế độ sáng/tối, không tràn khung khi thu nhỏ cửa sổ. Dùng component dùng chung và design token, không viết màu hex cứng, không thêm thư viện UI khác.
- Chưa làm hiệu ứng, ảnh minh họa, tinh chỉnh thẩm mỹ. Chỉ làm ở cột mốc trau chuốt (M8).
- Không dùng dữ liệu giả trong giao diện. Dữ liệu demo chỉ đến từ scripts/seed.py.
- Kết quả kiểm thử của các lần sửa lỗi được cập nhật chung vào docs/KIEM-THU-TONG-HOP.md: ghi mã lỗi, ngày, môi trường, happy path, test phá, kết quả và giới hạn; không tạo báo cáo kiểm thử Markdown riêng cho từng Fxx.
Quy tắc thời gian:
- Mọi so sánh thời gian nghiệp vụ (mở buổi, mốc trễ/vắng, hạn xin vắng, cửa sổ sửa) đi qua MỘT hàm lấy thời gian hiện tại (clock) theo Asia/Ho_Chi_Minh có thể thay thế khi test. Không gọi datetime.now() rải rác trong mã nghiệp vụ.
