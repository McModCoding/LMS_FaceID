# Hướng dẫn thành viên trong nhóm lấy và chạy LMS FaceID

Cập nhật: 07/11/2026. Dùng cho thành viên clone repository hoặc nhận gói mã nguồn GitHub sạch.

Mục tiêu sau khi làm xong: mở được giao diện, đăng nhập đủ ba vai trò, có dữ liệu demo trên máy riêng và biết cách nhận các thay đổi tiếp theo của nhóm.

## 1. Chọn cách chạy

| Nhu cầu | Cách phù hợp |
| --- | --- |
| Mới lấy dự án, muốn chạy thử nhanh | Chạy toàn bộ bằng Docker, theo mục 2–7 |
| Sửa frontend, muốn dùng Node trên máy | Chạy MySQL/backend bằng Docker, frontend trực tiếp, theo mục 10 |
| Sửa/debug backend bằng IDE | Chạy MySQL bằng Docker, backend trong môi trường Python riêng, theo mục 11 |
| Kiểm tra trước khi gửi thay đổi | Theo mục 12–13 |

Các lệnh chính bên dưới dùng **PowerShell trên Windows** và được chạy tại thư mục gốc có `docker-compose.yml`, trừ khi ghi rõ thư mục khác. Đường dẫn cài đặt trên máy mỗi người có thể khác nhau.

Với macOS/Linux, các lệnh Docker/Git vẫn dùng như bên dưới; thay `Copy-Item` bằng `cp`, cách gán biến môi trường theo shell đang dùng. Ví dụ `LMS_API_PROXY=http://127.0.0.1:8001 npm run dev`.

## 2. Chuẩn bị công cụ

**Nếu chạy toàn bộ bằng Docker:**

- Git để clone và làm việc nhóm; nếu chỉ nhận ZIP thì có thể giải nén để chạy thử.
- Docker Desktop đã mở, Docker engine đang chạy; trên Windows chọn Linux containers.
- Docker Compose v2 có hỗ trợ `--wait`.
- Trình duyệt và trình soạn thảo mã nguồn.

Không bắt buộc cài Python, Node hoặc MySQL trên máy nếu chỉ dùng cách chạy Docker. Python/Node được cung cấp trong image của dự án. Lần build đầu cần mạng để tải image và dependency.

Kiểm tra:

```powershell
git --version
docker --version
docker compose version
docker info
```

Nếu `docker info` chưa kết nối được engine, mở Docker Desktop và đợi engine sẵn sàng trước khi tiếp tục.

Nếu chạy trực tiếp trên máy: backend cần Python 3.11 trở lên; frontend dùng Node 20 như Dockerfile và CI của dự án. Dùng `package-lock.json` đi kèm khi cài frontend.

## 3. Lấy mã nguồn

### Cách A — Clone repository của nhóm

Lấy URL repository từ trưởng nhóm. Thay chuỗi mẫu dưới đây bằng URL thực tế trước khi chạy:

```powershell
$repoUrl = 'URL_REPOSITORY_DO_NHOM_CUNG_CAP'
git clone $repoUrl lms-faceid
Set-Location lms-faceid
```

Repository private yêu cầu tài khoản GitHub của bạn được cấp quyền. Đăng nhập bằng cơ chế Git/GitHub trên máy; không ghi token vào URL hoặc commit token vào mã.

### Cách B — Nhận gói ZIP

Giải nén gói mã nguồn vào thư mục mới, sau đó mở thư mục `lms-faceid` bên trong. Không chép đè ZIP lên thư mục đang có công việc chưa lưu. ZIP sạch không có lịch sử `.git`; muốn làm việc nhóm lâu dài thì nên clone repository.

### Xác nhận đang ở đúng thư mục

```powershell
Test-Path .\docker-compose.yml
Test-Path .\.env.example
Test-Path .\backend\pyproject.toml
Test-Path .\frontend\package-lock.json
```

Cả bốn kết quả phải là `True`.

## 4. Tạo cấu hình riêng trên máy

Mỗi thành viên tự tạo `.env`; không lấy `.env`, database, ảnh khuôn mặt hoặc thư mục `.local` từ máy người khác.

Chỉ sao chép cấu hình mẫu nếu chưa có `.env`:

```powershell
if (-not (Test-Path .\.env)) {
    Copy-Item .\.env.example .\.env
}
```

Mở `.env` trong trình soạn thảo và điền:

| Biến | Cách điền cho lần chạy Docker đầu |
| --- | --- |
| `DB_USER` | Giữ `lms_user`; ứng dụng không dùng tài khoản root |
| `DB_NAME` | Giữ `lms_db` cho bộ dữ liệu cơ bản |
| `DB_PASSWORD` | Mật khẩu riêng của tài khoản DB ứng dụng |
| `MYSQL_ROOT_PASSWORD` | Mật khẩu root riêng cho MySQL trên máy bạn, khác mật khẩu ứng dụng |
| `SECRET_KEY` | Khóa riêng sinh ngẫu nhiên, nên dùng 64 ký tự hex |
| `APP_ENV` | `development` cho cách chạy cơ bản |
| `FACE_ENGINE` | Giữ `mock` |
| `DEV_ALLOW_OPEN_ANYTIME` | Giữ `false` |
| `DEV_FACE_SIMULATOR` | Giữ `false` |

Sinh **ba giá trị khác nhau** cho hai mật khẩu và khóa. Nếu đã có Python:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Nếu chỉ cài Docker, có thể dùng:

```powershell
docker run --rm python:3.11-slim python -c "import secrets; print(secrets.token_hex(32))"
```

Chạy lại riêng từng lần để có các giá trị khác nhau, rồi dán vào `.env` trên máy mình. Không chụp terminal chứa các giá trị này để gửi nhóm.

**Phân biệt địa chỉ DB:** trong Docker, backend được Compose ghi đè `DB_HOST=mysql`, `DB_PORT=3306`. Công cụ DB chạy trên máy dùng `127.0.0.1:3307`. Không đổi cấu hình nội bộ container thành cổng `3307`.

Không cần chỉnh `VITE_API_BASE_URL` để chạy frontend hiện tại: API client dùng `/api/v1`, Vite chuyển tiếp `/api` sang backend. Khi chạy frontend ngoài Docker, dùng `LMS_API_PROXY` như mục 10.

## 5. Khởi tạo lần đầu bằng Docker

Chỉ dùng quy trình seed bên dưới cho database demo mới trên máy riêng.

### Bước 1 — Kiểm tra cấu hình và build

```powershell
docker compose config --quiet
docker compose build
```

`config --quiet` chỉ kiểm tra tính hợp lệ. Không gửi bản `docker compose config` đầy đủ vào nhóm vì nội dung render có thể chứa mật khẩu.

### Bước 2 — Khởi động MySQL và chờ sẵn sàng

```powershell
docker compose up -d --wait mysql
docker compose ps mysql
```

MySQL phải ở trạng thái chạy và healthy. Nếu CLI không nhận `--wait`, cập nhật Compose hoặc dùng `docker compose up -d mysql`, sau đó đợi `docker compose ps mysql` hiển thị healthy.

### Bước 3 — Chạy migration

```powershell
docker compose run --rm backend alembic upgrade head
```

Lệnh phải kết thúc thành công trước khi seed. Toàn bộ schema được tạo qua Alembic; không tạo/sửa bảng bằng tay để bỏ qua lỗi migration.

### Bước 4 — Tạo dữ liệu mẫu cơ bản

```powershell
docker compose run --rm backend python scripts/seed.py
```

Seed cơ bản tạo 1 Admin, 5 giảng viên, 60 sinh viên, 4 lớp cùng lịch/buổi, chuyên cần, bài tập, học liệu, đề mẫu và thành phần điểm. Đây là dữ liệu tổng hợp phục vụ demo.

Các lệnh `run --rm` dùng container chạy tác vụ một lần; dữ liệu MySQL vẫn nằm ở volume của dịch vụ MySQL.

### Bước 5 — Chạy backend và frontend

```powershell
docker compose up -d backend frontend
docker compose ps
```

Mở giao diện và đăng nhập theo mục 6. Không chạy lại seed mỗi lần bật dự án: seed có thể đặt lại mật khẩu/trạng thái của tài khoản và dữ liệu mẫu.

### Tùy chọn — Bộ dữ liệu mở rộng

Bộ mở rộng có 120 sinh viên, 8 giảng viên, 12 lớp và nhiều trạng thái học tập hơn. Chỉ chọn trên **môi trường demo mới, riêng biệt**, trước khi khởi tạo MySQL ở bước 2:

```dotenv
APP_ENV=test
DB_NAME=lms_rich_demo_team_test
```

Tên DB phải bắt đầu bằng `lms_rich_demo_`. Sau migration, thay lệnh seed cơ bản ở bước 4 bằng:

```powershell
docker compose run --rm backend python scripts/seed.py --rich-demo
```

Nếu `APP_ENV` hoặc tên DB không đúng điều kiện, script sẽ từ chối. Không cần profile máy của người khác để dùng cách cấu hình này.

Nếu đã chạy bộ cơ bản hoặc đã có volume dữ liệu, **không chỉ đổi `DB_NAME` rồi mong Docker tạo lại DB**: MySQL chỉ áp dụng thông tin khởi tạo trên volume mới. Nhờ người phụ trách tạo môi trường demo riêng khi muốn đổi bộ dữ liệu; giữ nguyên dữ liệu đang làm việc.

## 6. Địa chỉ và tài khoản demo

| Thành phần | Địa chỉ khi chạy toàn bộ bằng Compose |
| --- | --- |
| Giao diện | http://localhost:5174 |
| Health check backend | http://localhost:8001/health |
| Swagger UI | http://localhost:8001/api/docs |
| ReDoc | http://localhost:8001/api/redoc |
| MySQL từ công cụ trên máy | Host `127.0.0.1`, port `3307`, DB/user theo `.env` |

`/health` xác nhận tiến trình backend phản hồi; để kiểm tra DB/schema/dữ liệu, cần đăng nhập và mở danh sách lớp.

| Vai trò | Tài khoản bắt đầu thử | Mật khẩu của seed hiện tại |
| --- | --- | --- |
| Admin | `admin` | `Demo@123` |
| Giảng viên | `gv001` | `Demo@123` |
| Sinh viên | `sv001` | `Demo@123` |

Đây là tài khoản demo do seed tạo, chỉ dùng trên môi trường thử riêng. Mật khẩu DB, mật khẩu root và `SECRET_KEY` là các giá trị riêng bạn đã đặt, không phải mật khẩu đăng nhập web.

Nếu bạn đã đổi mật khẩu qua UI, dùng mật khẩu đã đổi; đừng seed lại chỉ để xử lý quên mật khẩu. Dùng chức năng quản trị tài khoản phù hợp.

FaceID hiện dùng mock. Banner **“FaceID chưa kích hoạt”** và reindex bị chặn khi engine chưa sẵn sàng là hành vi đúng của phiên bản này. Điểm danh vẫn thực hiện được bằng thao tác thủ công.

## 7. Kiểm tra nhanh sau khi cài

Thử bằng các phiên trình duyệt tách biệt hoặc đăng xuất giữa các vai trò:

1. **Admin:** mở trang chủ → danh sách sinh viên → danh sách lớp → chi tiết lớp/lịch. Xác nhận có dữ liệu từ backend.
2. **Giảng viên:** mở lớp được phân công, ví dụ `IT101-01` → học liệu/bài tập → buổi học/chuyên cần → kiểm tra → bảng điểm.
3. **Sinh viên:** mở lớp đang tham gia → xem học liệu và chuyên cần → thử bài tập/đề còn hạn → xem thông báo.
4. **Bảng điểm:** sinh viên chỉ thấy điểm sau khi giảng viên/Admin công bố và tổng trọng số hợp lệ.
5. **Trình duyệt:** thử sáng/tối và thu nhỏ cửa sổ; nếu lỗi, ghi lại vai trò, màn hình và thao tác gây lỗi.

Không sửa trực tiếp DB để mở buổi hoặc đưa đề nháp sang công bố. Các hành động này phải đi qua UI/API có quyền và đúng điều kiện nghiệp vụ.

Hạn bài tập/đề của seed được tạo theo thời điểm khởi tạo, không tự gia hạn chỉ vì chạy lại seed. Sau một thời gian, bài có thể hết hạn đúng quy tắc. Tạo nội dung mới hoặc điều chỉnh bằng chức năng được phép để thử tiếp.

Với bộ mở rộng: `DEMO-07` là lớp nháp, `DEMO-08` là lớp đã đóng; có thể dùng để đối chiếu giới hạn thao tác. Lượt thi đang làm mẫu có thời hạn ngắn và sẽ tự chốt khi hết giờ.

## 8. Bật/tắt dự án hằng ngày

Ở thư mục gốc:

```powershell
# Bật lại các dịch vụ đã khởi tạo
docker compose up -d

# Xem trạng thái
docker compose ps

# Xem log gần nhất khi có lỗi
docker compose logs --tail 100 backend frontend

# Dừng, giữ nguyên container và dữ liệu
docker compose stop
```

Thông thường không cần build lại, chạy migration hoặc seed khi chỉ bật/tắt máy. Khi vừa nhận mã mới, làm theo mục 9.

## 9. Nhận thay đổi mới từ nhóm

Trong bản clone có Git:

```powershell
git status --short
```

Nếu còn thay đổi chưa lưu/commit, xử lý công việc đó theo quy trình của nhóm trước khi kéo mã. Không dùng lệnh reset/clean để làm mất thay đổi.

Khi nhánh hiện tại đã sẵn sàng nhận cập nhật:

```powershell
git pull --ff-only
docker compose build
docker compose run --rm backend alembic upgrade head
docker compose up -d
```

Nếu đang ở nhánh công việc, việc đồng bộ với nhánh chính theo quy ước repository của nhóm; `pull` chỉ cập nhật nhánh đang đứng. Nếu Git báo lịch sử phân kỳ, dừng và trao đổi trong nhóm để chọn merge/rebase phù hợp.

- Có migration mới: luôn `alembic upgrade head`.
- Có dependency/Dockerfile đổi: build lại image; frontend chạy trực tiếp thì cài lại từ lockfile.
- Chỉ sửa mã frontend/backend: volume và dev server hỗ trợ tải lại; nếu không nhận, xem log rồi khởi động lại dịch vụ liên quan.
- Nếu thay `.env` của Compose: dùng `docker compose up -d --force-recreate backend frontend` để container nhận môi trường mới; `restart` đơn thuần không thay environment đã gắn vào container.
- Không tự đổi mật khẩu/DB name của MySQL đang có dữ liệu; biến khởi tạo không sửa tài khoản trong volume cũ.
- Không seed lại theo thói quen sau mỗi `pull`.

## 10. Sửa frontend trực tiếp bằng Node trên máy

Giữ MySQL/backend Docker đã khởi tạo. Dừng frontend Docker để dễ phân biệt hai giao diện:

```powershell
docker compose stop frontend
docker compose up -d mysql backend
Set-Location frontend
npm.cmd ci --legacy-peer-deps
$env:LMS_API_PROXY = 'http://127.0.0.1:8001'
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Mở http://localhost:5173. API vẫn do backend Docker ở port `8001` xử lý. Giữ cửa sổ này chạy; dùng cửa sổ khác cho lệnh kiểm tra.

`npm.cmd` tránh vướng PowerShell execution policy đối với `npm.ps1`; không cần đổi policy toàn máy. Trên macOS/Linux dùng `npm`.

Kiểm tra frontend, trong `frontend`:

```powershell
npm.cmd run type-check
npm.cmd run lint
npm.cmd run build
```

Dừng dev server bằng `Ctrl+C`. Khi chuyển lại cách chạy toàn bộ Docker, ở thư mục gốc chạy `docker compose up -d frontend` và dùng lại port `5174`.

## 11. Sửa/debug backend trực tiếp bằng Python trên máy

Giữ MySQL Docker đã khởi tạo; dừng backend Docker để tránh chạy hai scheduler trên cùng dữ liệu:

```powershell
docker compose stop backend frontend
docker compose up -d mysql
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Chạy lệnh tạo `.venv` một lần; nếu đã có môi trường ảo của dự án thì dùng lại. Không cần kích hoạt môi trường bằng PowerShell script, có thể gọi thẳng `python.exe` như ví dụ.

Tạo `backend/.env` riêng nếu chưa có:

```powershell
if (-not (Test-Path .\.env)) {
    Copy-Item ..\.env.example .\.env
}
```

Điền cấu hình ứng dụng khớp với DB demo đã tạo:

- `DB_HOST=127.0.0.1`, `DB_PORT=3307`.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` đúng với MySQL trên máy bạn.
- `SECRET_KEY` riêng; `APP_ENV=development` hoặc cấu hình `test` đúng bộ demo bạn chọn.
- Giữ `FACE_ENGINE=mock`, `DEV_ALLOW_OPEN_ANYTIME=false`.
- `backend/.env` không cần `MYSQL_ROOT_PASSWORD`; biến đó dành cho khởi tạo MySQL ở Compose.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Mở http://localhost:8000/api/docs. Nếu frontend cũng chạy trực tiếp, trong cửa sổ frontend đặt `LMS_API_PROXY=http://127.0.0.1:8000`, rồi chạy lại Vite.

Không bật backend Docker đồng thời với backend trực tiếp trên cùng database khi thử các tác vụ nền. Khi chuyển lại Docker, dừng Uvicorn bằng `Ctrl+C`, về thư mục gốc rồi chạy `docker compose up -d backend frontend`.

## 12. Kiểm thử backend bằng MySQL riêng

Ruff trong backend Docker đang chạy:

```powershell
docker compose exec -T backend python -m ruff check app tests
```

Pytest phải dùng database **mới** có chữ `test`, không dùng DB đang mở trên giao diện. Dùng cửa sổ PowerShell riêng và chỉ thực hiện trên MySQL demo của chính máy bạn.

Ví dụ chạy trong backend container đã bật, dùng root của MySQL local để fixture tự tạo DB test và chạy migration. Root chỉ được truyền cho process kiểm thử, không thay `.env` hay tài khoản DB của ứng dụng:

```powershell
$testDb = 'lms_team_' + [guid]::NewGuid().ToString('N').Substring(0, 10) + '_test'
$testSecret = Read-Host 'Nhap MYSQL_ROOT_PASSWORD cua MySQL demo local' -AsSecureString
$env:DB_PASSWORD = [System.Net.NetworkCredential]::new('', $testSecret).Password
$env:TEST_DB_ADMIN_PASSWORD = $env:DB_PASSWORD
try {
    docker compose exec -T `
        -e APP_ENV=test `
        -e "DB_NAME=$testDb" `
        -e "TEST_DB_NAME=$testDb" `
        -e DB_USER=root `
        -e DB_PASSWORD `
        -e TEST_DB_ADMIN_USER=root `
        -e TEST_DB_ADMIN_PASSWORD `
        -e TEST_KEEP_DB=1 `
        -e REQUIRE_MYSQL_TESTS=1 `
        -e FACE_STORAGE_DIR=/tmp/lms-team-test-face `
        -e UPLOAD_STORAGE_DIR=/tmp/lms-team-test-uploads `
        backend python -m pytest -q
} finally {
    Remove-Item Env:DB_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:TEST_DB_ADMIN_PASSWORD -ErrorAction SilentlyContinue
}
```

Database được giữ lại sau test nhờ `TEST_KEEP_DB=1`. Mỗi lần chạy lại dùng tên mới; không trỏ vào DB test đã có dữ liệu cần giữ. Nếu không kết nối được MySQL, `REQUIRE_MYSQL_TESTS=1` sẽ dừng để tránh âm thầm chuyển sang SQLite.

Image backend hiện không cài Docker CLI nên các ca kiểm tra Docker Compose có thể bị skip khi pytest chạy trong container. Khi cần nghiệm thu đầy đủ như bản xuất, chạy pytest trên máy có Docker CLI bằng môi trường Python riêng, với cùng nguyên tắc DB mới và các biến cấu hình test. Kết quả tham chiếu và phạm vi nằm trong [KIEM-THU-TONG-HOP.md](KIEM-THU-TONG-HOP.md).

Nếu dùng backend trực tiếp, Ruff chạy bằng `.\.venv\Scripts\python.exe -m ruff check app tests` tại `backend`. Không chạy pytest mặc định mà chưa xác định rõ DB test.

## 13. Kiểm thử trình duyệt và luồng nghiệp vụ

Playwright nằm trong `frontend/e2e`. Khi cần dùng, tại `frontend` đã cài dependency:

```powershell
npx.cmd playwright install chromium
```

Các lệnh `npm.cmd run test:e2e:phase1` đến `phase4` dùng cấu hình từng giai đoạn. Cần đọc file `playwright*.config.ts` để chuẩn bị đúng base URL/cổng, backend và dữ liệu seed trước khi chạy. Không coi một lệnh E2E ở máy mới là tự động tạo đủ môi trường.

Một số kịch bản được viết cho bố cục ở thời điểm nghiệm thu trước. Nếu UI đã thay đổi, đối chiếu selector và kịch bản trước khi kết luận lỗi chức năng; không sửa nghiệp vụ chỉ để làm selector cũ chạy qua.

Sau mỗi thay đổi, chọn kiểm tra phù hợp rồi ghi kết quả vào `docs/KIEM-THU-TONG-HOP.md`: mã công việc/lỗi, ngày, môi trường, happy path, test phá, kết quả, giới hạn. Trước khi hoàn thành một cột mốc, phải có Ruff, pytest, TypeScript, ESLint và migration/seed trên DB trống riêng theo quy tắc dự án.

## 14. Các vị trí mã nguồn thường dùng

| Thư mục/file | Nội dung |
| --- | --- |
| `SPEC.md` | Nguồn yêu cầu, phạm vi và quyết định nghiệp vụ; đọc cả các cập nhật cuối file |
| `AGENTS.md` | Quy tắc làm việc và kiểm tra trước khi báo xong |
| `backend/app/routers` | Endpoint HTTP, dependency và schema vào/ra |
| `backend/app/services` | Nghiệp vụ, kiểm quyền theo lớp, deadline và tính điểm |
| `backend/app/models`, `schemas` | Mô hình ORM và hợp đồng dữ liệu |
| `backend/alembic/versions` | Migration; không tự sửa schema bằng tay |
| `backend/app/utils/clock.py` | `now_local()` và clock thay thế cho test |
| `backend/app/face` | Hợp đồng engine và mock |
| `frontend/src/api` | Gọi API |
| `frontend/src/pages`, `routes`, `layouts` | Màn hình, đường dẫn và bố cục theo vai trò |
| `frontend/src/components` | Component dùng chung và UI primitive |
| `frontend/src/index.css` | Design token và theme |
| `scripts/seed.py` | Entrypoint dữ liệu demo; phần triển khai ở `backend/app/seed_data.py` |
| `docs/openapi.json` | Bản hợp đồng API; Swagger trực tiếp phản ánh ứng dụng đang chạy |

## 15. Quy tắc làm việc chung

1. Xác nhận công việc/cột mốc được giao, đọc SPEC và các cập nhật liên quan; chỉ làm phạm vi được giao.
2. Tạo nhánh công việc theo quy ước nhóm. Không dùng nhánh chính để trộn nhiều việc chưa liên quan.
3. Nghiệp vụ đặt ở backend services; React và router không tự quyết định điểm, thời hạn hoặc quyền.
4. Schema thay đổi qua Alembic; kiểm tra migration từ DB trống riêng và DB đã có migration cũ.
5. Dùng component/token có sẵn, giữ trạng thái tải/rỗng/lỗi và sáng/tối; không thêm UI framework khác.
6. Dữ liệu demo chỉ từ seed; không nhúng danh sách giả vào giao diện. Không thêm nút giả lập nhận diện vào bản nộp.
7. Chạy kiểm tra liên quan và cập nhật nhật ký tổng hợp. Nếu lệnh lỗi, thử tối đa ba hướng theo AGENTS, sau đó dừng, ghi nguyên nhân và trao đổi trong nhóm.
8. Trước khi tự commit/push, xem từng thay đổi và danh sách file staged. Chỉ chọn file thuộc công việc, rồi mở PR theo quy trình nhóm.

Các lệnh đọc để tự kiểm tra trước khi đưa mã lên GitHub:

```powershell
git status --short
git diff
git diff --cached --name-only
git diff --cached
```

Không đưa `.env`, `backend/.env`, `.local`, ảnh khuôn mặt/embedding, upload/bài nộp thật, dump DB, log có dữ liệu riêng, cache/build/dependency hoặc token vào commit. Dùng dữ liệu tổng hợp khi gửi ảnh minh chứng.

## 16. Lỗi thường gặp

| Biểu hiện | Kiểm tra và xử lý |
| --- | --- |
| Docker chưa chạy / không kết nối daemon | Mở Docker Desktop, chờ engine; kiểm tra `docker info` |
| `Set DB_PASSWORD`, `Set SECRET_KEY` hoặc thiếu root password | Kiểm tra đúng file `.env` ở gốc và điền đủ giá trị; không gửi file đó vào nhóm |
| MySQL `Access denied` sau khi đổi `.env` | Dùng credential đúng với volume đã khởi tạo; sửa biến không tự đổi tài khoản trong DB cũ |
| MySQL chưa healthy | Xem `docker compose ps mysql` và log MySQL; đợi khởi tạo hoặc giải quyết lỗi cấu hình trước migration |
| Thiếu bảng / `Table ... doesn't exist` | Chạy Alembic trên đúng DB; kiểm tra DB name/host và log, không tạo tay bảng |
| Trùng port hoặc tên container | Xác định dịch vụ nào đang dùng; phối hợp đổi mapping phía máy/đóng đúng môi trường cũ. Không xóa container/volume chưa rõ dữ liệu |
| `npm.ps1 cannot be loaded` | Dùng `npm.cmd`/`npx.cmd` trên PowerShell |
| Frontend mở được nhưng gọi API lỗi / 502 | Nếu Node chạy trên máy, đặt đúng `LMS_API_PROXY`; nếu Docker, kiểm tra backend và proxy `backend:8000` |
| Login báo sai tài khoản | Kiểm tra seed đã thành công trên đúng DB, đúng môi trường/cổng; mật khẩu web khác mật khẩu DB |
| `PASSWORD_CHANGE_REQUIRED` | Đổi mật khẩu theo luồng giao diện trước khi dùng các chức năng khác |
| Mở buổi bị từ chối | Kiểm tra lớp active, quyền, giờ địa phương và cửa sổ mở; Admin mở ngoài giờ cần lý do |
| Không nộp bài / không bắt đầu thi được | Kiểm tra lớp/ghi danh, trạng thái công bố, hạn nộp, giờ mở/đóng và số lượt |
| Sinh viên chưa thấy điểm | Kiểm tra công bố bảng điểm, tổng trọng số 100%; kết quả thi còn phụ thuộc `show_result` |
| FaceID chưa sẵn sàng / reindex 409 | Đúng với engine mock; dùng điểm danh thủ công. Engine thật thuộc M9 |
| `--rich-demo` bị chặn | Cần môi trường test và DB riêng có prefix `lms_rich_demo_`, theo mục 5 |
| Pytest báo MySQL không khả dụng | Kiểm tra DB test và credential quản trị test; giữ yêu cầu MySQL, không bỏ chốt bảo vệ để chạy vào dữ liệu ứng dụng |

Khi báo lỗi cho nhóm, gửi: nhánh/phiên bản đang dùng, cách chạy Docker hay trực tiếp, vai trò, màn hình/API, các bước tái hiện, kết quả mong đợi/thực tế và đoạn lỗi đã che dữ liệu riêng. Không xử lý bằng xóa volume, drop database, reset/clean mã hoặc ghi đè cấu hình của người khác.

## 17. Checklist bàn giao cho thành viên mới

- [ ] Đã lấy đúng repository/ZIP, đứng đúng thư mục gốc.
- [ ] Đã tự tạo `.env` riêng và không đưa credential lên Git.
- [ ] Docker/MySQL healthy, migration thành công, seed đúng bộ demo trên DB mới.
- [ ] Đăng nhập thử Admin, giảng viên, sinh viên và mở được lớp có dữ liệu.
- [ ] Biết các cổng `5174/8001/3307` của Docker và cổng khác khi chạy trực tiếp.
- [ ] Biết bật/tắt hằng ngày và nhận cập nhật mà không seed/reset dữ liệu tùy tiện.
- [ ] Biết FaceID đang mock, thời gian nghiệp vụ dùng giờ Việt Nam và điểm chỉ công bố theo quyền.
- [ ] Biết nơi sửa mã, lệnh kiểm tra và quy trình báo lỗi/PR của nhóm.
