# Kiểm thử bản xuất mã nguồn GitHub

## EXPORT-SOURCE — 07/11/2026

Phạm vi: bản xuất chọn file theo danh sách cho phép, không thay đổi nghiệp vụ.
Môi trường: Windows, Python 3.13, MySQL 8 cô lập. Các database kiểm thử và seed
được tạo mới, tách khỏi dữ liệu ứng dụng; giữ lại sau kiểm tra.

## Happy path

- Backend của bản xuất chạy toàn bộ pytest trên MySQL: **334 passed**, 621.82 giây.
- Ruff kiểm tra `app` và `tests` ngay trong bản xuất: đạt.
- TypeScript `tsc --noEmit` cho cấu hình app và node: đạt.
- ESLint `src` với `--max-warnings=0`: đạt.
- TypeScript và ESLint chạy tại checkout có dependency sẵn; toàn bộ file nguồn,
  cấu hình và lockfile tương ứng trong bản xuất được so sánh byte, không thay đổi.
- Alembic upgrade head từ database MySQL trống: đạt.
- Chạy `scripts/seed.py` của bản xuất hai lần: đạt, số bản ghi không tăng.
- Seed cơ bản: 60 sinh viên, 5 giảng viên, 4 lớp, 104 buổi, 2 bài tập,
  4 câu hỏi, 1 đề, 2 học liệu, 4 thành phần điểm.
- OpenAPI tạo trực tiếp từ ứng dụng đã gắn router: 155 thao tác HTTP, gồm /health.

## Test phá và biên

Toàn suite backend có các nhóm kiểm tra phân quyền/truy cập chéo, cấu hình
production không an toàn, import lỗi, trùng lịch, mốc thời gian điểm danh,
hạn nộp bài, deadline/nộp lại bài thi, chính sách kết quả, trọng số và làm tròn,
retry khung hình, consent/thu hồi và lỗi xóa dữ liệu khuôn mặt.
Kết quả của các nhóm này nằm trong tổng pytest nêu trên, không cộng riêng lần nữa.

## Kiểm tra phạm vi xuất

- File nguồn được chọn theo allowlist thay vì sao chép toàn bộ thư mục.
- Loại .git/lịch sử Git, .env, profile cá nhân, upload/ảnh/embedding,
  database/dump, log/cache/dependency/build, báo cáo Word/PDF, ảnh/video minh chứng,
  mockup và script sửa lỗi dùng một lần.
- Hai fixture Excel của test chứa dữ liệu tổng hợp đã đối chiếu; metadata creator
  là openpyxl, không có macro hoặc liên kết workbook bên ngoài.
- Quét các giá trị secret có trong cấu hình cục bộ, mẫu khóa/token phổ biến,
  URL nhúng credential và đường dẫn thư mục người dùng trong các file xuất.
  URL user:pass@example.org trong test âm là chuỗi kiểm thử được đối chiếu riêng.
- Kiểm CRC của ZIP, danh mục file và SHA-256 từng file qua EXPORT-MANIFEST.json.
- Không stage, commit, push hoặc thay đổi file riêng trên máy.

## Giới hạn

- Không chạy lại Playwright/E2E trong đợt đóng gói này. Các test theo phase
  còn cần môi trường, dữ liệu seed và cổng đúng với cấu hình riêng.
- FaceID hiện là mock; không có độ chính xác nhận diện thật hoặc hiệu chỉnh M9.
- Quét secret theo giá trị/mẫu và allowlist không thay thế kiểm toán bảo mật độc lập.
- Chưa triển khai production hay tải nội dung lên GitHub; gói là snapshot nguồn
  để chủ dự án chọn repository và đăng tải.


## DOCS-TEAM — 07/11/2026

Bổ sung hướng dẫn thành viên mới và liên kết README. Kiểm cú pháp 24 khối PowerShell, liên kết tương đối, cấu hình Compose trên bản sao với giá trị kiểm thử và quét thông tin riêng: đạt. 365 file nguồn đã kiểm thử giữ nguyên từng byte; kết quả 334 pytest/Ruff/TypeScript/ESLint và migration/seed nêu trên được giữ làm tham chiếu, không phải lượt chạy mới cho sửa tài liệu. Chưa chạy lại toàn bộ cài đặt Docker trên máy mới.


## M9A-OPENCV-ENGINE — 07/11/2026

Phạm vi: thêm engine FaceID OpenCV (YuNet + SFace) cắm vào `FaceEngine`, cấu hình, script tải trọng số và đánh giá. Không đổi schema (không migration), không đổi `face_service`/`attendance_service`.
Môi trường kiểm tra: sandbox Linux, Python 3, OpenCV 5.0.0, numpy, cryptography. **Không có** MySQL, FastAPI, pytest, ruff, Node, trọng số ONNX, webcam hay ảnh người thật.

### Happy path
- 33 ca của `test_opencv_engine.py` và 9 ca của `test_face_eval.py` đạt khi chạy bằng trình chạy tối giản thay pytest và mô phỏng pydantic-settings; không phải pytest thật.
- Bao phủ: mã hóa/giải mã embedding (thô, Fernet, sai khóa, blob hỏng), trạng thái sẵn sàng (thiếu trọng số, trọng số hỏng thật qua OpenCV, thiếu ngưỡng), từ chối đăng ký theo từng lý do, quy tắc điểm trung bình hai mẫu, `margin`, `ambiguous`, `unknown`, `low_quality`, giới hạn số mặt mỗi khung, factory, kiểm tra cấu hình, các script đánh giá bằng engine giả.
- `py_compile` cho toàn bộ file Python mới/sửa: đạt.

### Test phá và biên
- Blob sai kích thước, NaN, vector không, token sai khóa, ảnh không giải mã được, ảnh dưới 96 px, hai khuôn mặt, mặt sát mép, mặt nhỏ, ảnh nhòe/tối/cháy sáng, gallery chứa embedding của engine khác, manifest dùng lại ảnh gallery làm ảnh test, CSV đo điểm danh sai giá trị.

### Giới hạn
- **Chưa chạy**: toàn bộ 334 test backend trên MySQL, `ruff`, `tsc`, `eslint`, Playwright; chỉnh sửa `FaceEnrollmentPage.tsx` (thêm mã lý do, sửa dòng mô tả) chưa được biên dịch.
- **Chưa đo**: độ chính xác phát hiện/nhận diện, FAR/FRR, độ trễ thật, tỷ lệ loại do chất lượng trên camera lớp học; chưa tải hay chạy trọng số YuNet/SFace thật. Ngưỡng `.env` chỉ là giá trị tạm.
- Không chống giả mạo (ảnh in/video). Test dùng detector/recognizer giả nên chỉ chứng minh logic, không chứng minh nhận diện đúng người.
- Việc cần làm tiếp để đóng M9: chạy `pytest`/`ruff`/`tsc`/`eslint` trên máy có MySQL, tải trọng số, thu ảnh có đồng ý, chạy `face_tools/evaluation`, cập nhật mục này bằng số đo thật.
