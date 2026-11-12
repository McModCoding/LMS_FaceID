> **Bản tích hợp V3.3 dành cho cài đặt sạch trên Windows:** xem [HUONG_DAN_CHAY_WINDOWS.md](HUONG_DAN_CHAY_WINDOWS.md).
> Có các file `SETUP_LMS_WINDOWS.bat`, `SEED_DEMO_WINDOWS.bat`, `TEST_LMS_WINDOWS.bat`, `DIAGNOSE_LMS_WINDOWS.bat`.
> Không tự đăng ký tài khoản công khai; Admin quản lý người dùng. Docker project riêng `lms_faceid_capstone_v33`; không bao gồm trọng số ONNX.

> **Capstone delivery:** For Windows/Docker setup, use [HUONG_DAN_CHAY_WINDOWS.md](HUONG_DAN_CHAY_WINDOWS.md). For verified scope, test limits and submission checklist, read [DANH_GIA_SAN_SANG_NOP.md](DANH_GIA_SAN_SANG_NOP.md) and [KET_QUA_KIEM_THU_BAN_GIAO.md](KET_QUA_KIEM_THU_BAN_GIAO.md). This package does not expose public self-registration.

# LMS FaceID

[Hướng dẫn dành cho thành viên mới](docs/HUONG-DAN-THANH-VIEN-NHOM.md):
lấy mã, tự tạo cấu hình, khởi tạo Docker, dùng dữ liệu mẫu, nhận cập nhật và kiểm thử.

Ứng dụng quản lý học tập cho Admin, giảng viên và sinh viên: lớp học phần,
lịch/buổi học, chuyên cần, học liệu, bài tập, kiểm tra trực tuyến, bảng điểm,
nhóm, thông báo và nhật ký. FaceID mặc định dùng **MockFaceEngine** (không tạo nhận diện giả). Engine thật OpenCV YuNet + SFace (M9a) bật bằng `FACE_ENGINE=opencv`, xem [docs/FACE-ENGINE-OPENCV.md](docs/FACE-ENGINE-OPENCV.md); ngưỡng chưa được hiệu chỉnh và độ chính xác chưa được đo cho đến khi bạn chạy `backend/face_tools/evaluation`.

## Công nghệ

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic, APScheduler.
- Dữ liệu: MySQL 8 (utf8mb4, InnoDB).
- Frontend: React 18, TypeScript, Vite, shadcn/ui, Tailwind, TanStack Query/Table.
- Kiểm tra: Ruff, pytest, TypeScript, ESLint, Playwright.

## Chạy bằng Docker Compose

1. Cài Docker và Docker Compose; giải nén mã nguồn vào một thư mục mới.
2. Sao chép `.env.example` thành `.env` khi chưa có file cấu hình riêng.
3. Điền `DB_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `SECRET_KEY` bằng các giá trị riêng.
   Sinh riêng từng giá trị bằng `python -c "import secrets; print(secrets.token_hex(32))"`.
   Giữ `APP_ENV=development`; không dùng mật khẩu root cho tài khoản DB ứng dụng.
4. Trong thư mục gốc chạy:

```sh
docker compose config --quiet
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

Chỉ trên **database demo mới**, tạo dữ liệu mẫu:

```sh
docker compose exec backend python scripts/seed.py
```

Bộ dữ liệu mở rộng `--rich-demo` chỉ chạy với `APP_ENV=test` và database riêng
có tên bắt đầu bằng `lms_rich_demo_`; đọc mục tùy chọn trong hướng dẫn thành viên mới
trước khi khởi tạo môi trường. Dữ liệu mẫu do seed tạo; tài khoản/mật khẩu demo chỉ dùng thử.

- Giao diện: http://localhost:5174
- API: http://localhost:8001
- Swagger: http://localhost:8001/api/docs
- ReDoc: http://localhost:8001/api/redoc
- Lược đồ API: [docs/openapi.json](docs/openapi.json)

Compose phục vụ development, các cổng chỉ bind 127.0.0.1. Khi dùng volume cũ,
cần đúng credential đã thiết lập; không xóa volume hoặc reset dữ liệu để sửa lỗi cấu hình.
Triển khai public cần frontend build, HTTPS/reverse proxy và cấu hình bảo mật riêng.

## Chạy trực tiếp

Trong `backend`, tạo môi trường Python riêng và cài:

```sh
python -m pip install -e ".[dev]"
```

Cấu hình các biến DB/SECRET_KEY và `APP_ENV=development` trong môi trường hoặc
`backend/.env` riêng. Với MySQL từ Compose, backend ngoài Docker dùng
`DB_HOST=127.0.0.1`, `DB_PORT=3307`; backend trong Docker dùng `mysql:3306`.

```sh
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Trong `frontend`:

```sh
npm ci --legacy-peer-deps
```

Đặt `LMS_API_PROXY=http://127.0.0.1:8000` trong môi trường rồi chạy `npm run dev`.
Ví dụ PowerShell: `$env:LMS_API_PROXY='http://127.0.0.1:8000'`.
Ví dụ Bash: `LMS_API_PROXY=http://127.0.0.1:8000 npm run dev`.
Frontend trực tiếp mặc định dùng cổng 5173.

## Kiểm thử

Backend, trong `backend`:

```sh
python -m ruff check app tests
python -m pytest -q
```

Trước pytest, cấu hình MySQL kiểm thử riêng: DB_HOST/DB_PORT/DB_USER/DB_PASSWORD,
TEST_DB_ADMIN_USER/TEST_DB_ADMIN_PASSWORD; đặt DB_NAME và TEST_DB_NAME thành cùng
một tên database **mới** có chữ `test`, `REQUIRE_MYSQL_TESTS=1`, `TEST_KEEP_DB=1`,
`APP_ENV=test`. Tài khoản quản trị kiểm thử cần quyền tạo database và migration.
Không dùng database ứng dụng hoặc database test đã có dữ liệu cần giữ.
TEST_KEEP_DB=1 giữ database sau khi chạy. Không đưa credential kiểm thử vào Git.

Frontend, trong `frontend`:

```sh
npm run type-check
npm run lint
npm run build
```

Các test E2E nằm ở `frontend/e2e`, với cấu hình Playwright đi kèm.
E2E cần backend/frontend đang chạy và dữ liệu seed phù hợp; cổng/base URL được
chỉ định trong từng cấu hình hoặc biến môi trường. Các test theo phase là kịch bản
nghiệm thu từng thời điểm; không coi tất cả đã được chạy lại trên mọi bố cục hiện tại.
Kết quả và giới hạn của bản xuất: [docs/KIEM-THU-TONG-HOP.md](docs/KIEM-THU-TONG-HOP.md).

## Cấu trúc

```text
backend/app/          API, services, models, schemas, FaceEngine
backend/alembic/      Lịch sử migration
backend/tests/        Test và fixture tổng hợp dành cho test
frontend/src/         Giao diện, API client và component chung
frontend/e2e/         Kịch bản Playwright
scripts/seed.py       Entrypoint dữ liệu demo
docs/openapi.json     Hợp đồng API
SPEC.md               Yêu cầu và các cập nhật nghiệp vụ
```

Ngày/giờ buổi học dùng DATE/TIME theo Asia/Ho_Chi_Minh; mọi so sánh nghiệp vụ
qua clock chung. Các dữ liệu timestamp khác tuân theo schema API.
Mọi thay đổi database phải đi qua Alembic. Engine FaceID thật (M9a) là tùy chọn và cần hiệu chỉnh trước khi tin kết quả; xem docs/FACE-ENGINE-OPENCV.md.

## Phạm vi bản xuất

Chỉ có mã nguồn, migration, cấu hình mẫu, test/fixture tổng hợp và tài liệu kỹ thuật.
Không kèm .git/lịch sử Git, .env, profile máy cá nhân, upload, ảnh/embedding,
database/dump, log, cache, dependency/build, ảnh/video minh chứng, báo cáo Word
hoặc script sửa lỗi dùng một lần. Các file gốc trên máy được giữ nguyên.
EXPORT-MANIFEST.json liệt kê các file cùng SHA-256 để kiểm tra bản xuất.

Giải nén gói này rồi tải **nội dung thư mục mã nguồn** lên repository GitHub mong muốn;
không cần tải file ZIP vào repository. Tự tạo cấu hình riêng sau khi clone.
