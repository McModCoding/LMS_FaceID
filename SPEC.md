# SPEC.md — CNTT-KLCN360: Hệ thống quản lý học tập tích hợp FaceID

> Tài liệu đặc tả cho AI coding agent. **Đọc toàn bộ file này trước mỗi phiên làm việc.**
> Nếu yêu cầu mâu thuẫn hoặc thiếu, hỏi lại. Không tự thêm tính năng ngoài mục 2.

---

## 0. Quy tắc làm việc cho agent (bắt buộc)

1. Chỉ làm đúng phạm vi ở mục 2. Tính năng P2 **không được làm** trừ khi chủ dự án yêu cầu.
2. Làm theo **lát cắt dọc** (DB → API → UI → test) từng cột mốc ở mục 12. Mỗi cột mốc phải chạy được và có demo trước khi sang cột mốc tiếp.
3. Mọi thay đổi schema đi qua **Alembic migration**. Không sửa tay database.
4. Mọi endpoint có Pydantic schema, có phân quyền (mục 5), có test tối thiểu cho: quyền truy cập, trường hợp lỗi chính.
5. Logic nghiệp vụ nằm ở `services/`, không nằm trong router hoặc component React.
6. Không hardcode secret. Dùng `.env`; commit `.env.example`.
7. Commit nhỏ, thông điệp rõ ràng. Không commit file ảnh khuôn mặt, `.env`, dump DB.
8. Trước khi báo hoàn thành một cột mốc: chạy `ruff`, `pytest`, `tsc --noEmit`, `eslint`, và chạy lại script seed từ DB trống.
9. UI tiếng Việt. Mã, tên biến, tên bảng bằng tiếng Anh.
10. Không dùng dữ liệu giả trong UI. Dữ liệu demo chỉ đến từ `scripts/seed.py`.

---

## 1. Tổng quan

**Mô tả một câu:** Admin tạo lớp và nạp danh sách sinh viên → sinh viên đăng ký khuôn mặt (có đồng ý) → giảng viên mở buổi học và điểm danh (FaceID cắm sau, hiện có điểm danh thủ công) → hệ thống tính chuyên cần → giảng viên giao bài tập, tổ chức kiểm tra trực tuyến → bảng điểm tổng hợp tự động → xuất Excel.

**Đối tượng:** Admin (Phòng Đào tạo), Giảng viên (cơ hữu / thỉnh giảng), Sinh viên.

**Trạng thái FaceID:** *chưa triển khai engine*, nhưng **hợp đồng cắm (plug) phải hoàn chỉnh** (mục 7) để ghép engine thật sau mà không sửa lõi hệ thống.

**Mục tiêu điểm cao:** ưu tiên (a) luồng đầu-cuối chạy mượt, (b) dữ liệu nhất quán, (c) có test và tài liệu, (d) giao diện trực quan, nhất quán. Ít tính năng nhưng chạy đúng hơn nhiều tính năng dở dang.

---

## 2. Phạm vi

### P0 — Lõi (bắt buộc, làm trước)
- Xác thực, phân quyền 3 vai trò, đổi mật khẩu, khóa/mở tài khoản.
- Danh mục: học kỳ, môn học.
- Quản lý giảng viên (cơ hữu/thỉnh giảng), sinh viên (có import Excel).
- Quản lý lớp học phần: tạo lớp, phân công giảng viên, thêm/xóa sinh viên (đơn lẻ + import), lịch học lặp tuần, sinh danh sách buổi học, kiểm tra trùng lịch.
- Buổi học: mở/đóng buổi, **điểm danh thủ công**, sửa điểm danh có lý do + audit log, xuất Excel.
- Khung FaceID: đăng ký khuôn mặt + đồng ý, giao diện điểm danh trực tiếp, hợp đồng engine (mục 7).

### P1 — Đầy đủ chức năng (làm sau P0, đều bắt buộc cho "điểm cao")
- **Kiểm tra trực tuyến** (mục 8): ngân hàng câu hỏi, tạo đề, làm bài có đồng hồ phía server, tự chấm trắc nghiệm, chấm tay tự luận, nhật ký hành vi, thống kê.
- **Bài tập**: giao bài, nộp file, nộp trễ, chấm điểm + nhận xét.
- **Bảng điểm**: thành phần điểm có trọng số, tự lấy từ chuyên cần/bài tập/kiểm tra, công bố điểm, xuất Excel.
- **Phân nhóm**: tạo nhóm, chia thủ công hoặc ngẫu nhiên.
- **Đơn xin vắng**: sinh viên gửi, giảng viên duyệt → buổi đó thành `excused`.
- **Thông báo lớp + thông báo trong ứng dụng** (chuông, polling).
- **Thời khóa biểu tuần** cho giảng viên và sinh viên.
- **Dashboard** theo vai trò, có biểu đồ.
- **Báo cáo chuyên cần**: tỷ lệ theo lớp/sinh viên, cảnh báo vắng nhiều.
- **Nhật ký hệ thống (audit log)** xem được bởi Admin.

### P2 — KHÔNG LÀM (ghi vào "Hướng phát triển" của báo cáo)
Email/SMS, WebSocket/thời gian thực thật, giám sát thi bằng camera, liveness, đăng nhập SSO, tích hợp Canvas/LTI, ứng dụng di động, chat, video bài giảng, chống đạo văn, thanh toán, đa ngôn ngữ, đa cơ sở.

---

## 3. Công nghệ

| Lớp | Chọn |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, PyMySQL, passlib[bcrypt], python-jose (JWT), openpyxl, APScheduler, pytest, httpx, ruff |
| DB | MySQL 8, `utf8mb4`, InnoDB, múi giờ lưu **UTC** |
| Frontend | React 18, Vite, TypeScript, React Router, TanStack Query, Ant Design 5, axios, react-hook-form + zod, dayjs, Recharts |
| Hạ tầng | docker-compose: `mysql`, `backend`, `frontend` (dev). Có `scripts/seed.py` |
| FaceID (sau) | InsightFace (SCRFD + ArcFace) qua onnxruntime — **không cài ở giai đoạn này** |

### Cấu trúc repo
```
lms-faceid/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/        # config, security, deps (RBAC), errors, logging
│  │  ├─ db/          # base, session
│  │  ├─ models/      # SQLAlchemy
│  │  ├─ schemas/     # Pydantic
│  │  ├─ routers/     # mỗi module một file
│  │  ├─ services/    # logic nghiệp vụ
│  │  ├─ face/        # base.py, mock_engine.py, factory.py  (mục 7)
│  │  └─ utils/       # excel, files, time
│  ├─ alembic/
│  ├─ tests/
│  └─ pyproject.toml
├─ frontend/
│  └─ src/ {api, auth, components, features, hooks, layouts, pages, routes, types}
├─ scripts/seed.py
├─ docs/               # use case, ERD, sequence, báo cáo kiểm thử
├─ docker-compose.yml
├─ .env.example
└─ SPEC.md
```

### Quy ước chung
- Prefix API: `/api/v1`. JSON `snake_case`. Thời gian ISO-8601 UTC; UI hiển thị `Asia/Ho_Chi_Minh`.
- Phân trang: `?page=1&page_size=20` → `{ "items": [], "total": 0, "page": 1, "page_size": 20 }`.
- Lỗi thống nhất: `{ "error": { "code": "STRING_CODE", "message": "tiếng Việt", "details": {} } }`.
- Xóa mềm cho `users`, `students`, `lecturers`, `classes` (cột `is_deleted` hoặc `status`).
- JWT: access 30 phút, refresh 7 ngày. Mật khẩu bcrypt. Giới hạn đăng nhập sai (5 lần/15 phút/IP+tài khoản).
- Upload file: kiểm tra đuôi + MIME + dung lượng (mặc định 10 MB), lưu ngoài thư mục public với tên ngẫu nhiên, tải xuống qua endpoint có kiểm quyền.

---

## 4. Mô hình dữ liệu

Tất cả bảng có `id` (BIGINT PK), `created_at`, `updated_at` trừ khi ghi khác. FK có index. Dưới đây liệt kê cột chính.

### Người dùng và danh mục
| Bảng | Cột chính |
|---|---|
| `users` | username (unique), email, password_hash, role ENUM(admin, lecturer, student), is_active, last_login_at |
| `lecturers` | user_id, code (unique), full_name, phone, degree, department, type ENUM(full_time, visiting) |
| `students` | user_id, student_code (unique), full_name, admin_class, dob, gender, phone, email, status ENUM(studying, suspended, graduated) |
| `semesters` | name, start_date, end_date, is_current |
| `subjects` | code (unique), name, credits |

### Lớp học
| Bảng | Cột chính |
|---|---|
| `classes` | code (unique), subject_id, semester_id, lecturer_id, max_students, status ENUM(draft, active, closed), late_after_min (mặc định 10), absent_after_min (mặc định 30), weight_present (1.0), weight_late (0.5), weight_excused (1.0), attendance_warning_absences (mặc định 3) |
| `class_students` | class_id, student_id, status ENUM(enrolled, dropped), UNIQUE(class_id, student_id) |
| `schedules` | class_id, weekday (0–6), start_time, end_time, room, start_date, end_date |
| `sessions` | class_id, schedule_id (nullable), session_no, date, start_time, end_time, room, status ENUM(scheduled, open, closed, cancelled), opened_at, closed_at |
| `groups`, `group_members` | groups(class_id, name); group_members(group_id, student_id), UNIQUE |

### FaceID (khung, chưa có engine thật)
| Bảng | Cột chính |
|---|---|
| `face_consents` | student_id, text_version, consented_at, revoked_at |
| `face_templates` | student_id, image_path, embedding (BLOB NULL), quality_score NULL, engine_name NULL, engine_version NULL, status ENUM(pending_embedding, active, revoked) |
| `recognition_logs` | session_id, student_id NULL, status ENUM(matched, unknown, ambiguous, no_face, low_quality), score NULL, margin NULL, engine_name, frame_at |

> Ảnh đăng ký được **lưu lại** ở trạng thái `pending_embedding` để khi engine thật cắm vào chỉ cần chạy lệnh reindex, không bắt sinh viên đăng ký lại. Chỉ lưu khi có `face_consents` còn hiệu lực.

### Điểm danh
| Bảng | Cột chính |
|---|---|
| `attendance_records` | session_id, student_id, status ENUM(present, late, absent, excused), source ENUM(face, manual, leave, system), first_seen_at NULL, hit_count (0), confidence NULL, note, modified_by NULL; UNIQUE(session_id, student_id) |
| `leave_requests` | student_id, session_id, reason, attachment_path NULL, status ENUM(pending, approved, rejected), reviewed_by NULL, reviewed_at NULL, review_note |

### Học tập
| Bảng | Cột chính |
|---|---|
| `announcements` | class_id NULL (NULL = toàn hệ thống), author_id, title, content, is_pinned |
| `notifications` | user_id, type, title, body, link, is_read, read_at |
| `assignments` | class_id, title, description, due_at, max_score, allow_late, attachment_path NULL, status ENUM(draft, published) |
| `submissions` | assignment_id, student_id, file_path NULL, text NULL, submitted_at, is_late, score NULL, feedback, graded_by NULL, graded_at NULL; UNIQUE(assignment_id, student_id) (nộp lại = ghi đè, giữ `submitted_at` mới nhất) |
| `grade_components` | class_id, name, weight (0–100), type ENUM(attendance, assignment, exam, manual), ref_id NULL; tổng weight của lớp = 100 khi công bố |
| `grades` | component_id, student_id, score NULL (0–10), updated_by; UNIQUE(component_id, student_id) |
| `grade_publications` | class_id, published_at, published_by (công bố bảng điểm; sinh viên chỉ thấy điểm sau khi công bố) |

### Kiểm tra trực tuyến
| Bảng | Cột chính |
|---|---|
| `questions` | subject_id, created_by, type ENUM(single, multiple, true_false, essay), content, difficulty ENUM(easy, medium, hard), explanation |
| `question_options` | question_id, content, is_correct, order_no |
| `exams` | class_id, title, description, duration_min, open_at, close_at, shuffle_questions, shuffle_options, max_attempts, score_policy ENUM(highest, last), show_result ENUM(never, after_submit, after_close), max_violations (0 = không giới hạn), auto_submit_on_violation, status ENUM(draft, published, closed) |
| `exam_questions` | exam_id, question_id, points, order_no |
| `exam_attempts` | exam_id, student_id, attempt_no, started_at, deadline_at, submitted_at NULL, status ENUM(in_progress, submitted, auto_submitted, graded), question_order JSON, option_order JSON, score NULL, violation_count |
| `attempt_answers` | attempt_id, question_id, selected_option_ids JSON NULL, essay_text NULL, is_correct NULL, score NULL, feedback, saved_at; UNIQUE(attempt_id, question_id) |
| `exam_events` | attempt_id, type ENUM(tab_hidden, window_blur, fullscreen_exit, copy, paste, reconnect), occurred_at, meta JSON |

### Hệ thống
| Bảng | Cột chính |
|---|---|
| `audit_logs` | user_id NULL, action, entity, entity_id, detail JSON, ip, created_at |
| `system_settings` | key (unique), value (JSON) |

---

## 5. Phân quyền

`A` = Admin, `L` = Giảng viên **của lớp đó**, `S` = Sinh viên **thuộc lớp đó**. Mọi truy cập dữ liệu lớp phải kiểm tra tư cách thành viên/giảng viên ở tầng service (không chỉ kiểm vai trò).

| Chức năng | A | L | S |
|---|:-:|:-:|:-:|
| CRUD học kỳ, môn, giảng viên, sinh viên, tài khoản | ✔ | – | – |
| Tạo/sửa lớp, phân công giảng viên, thêm/xóa sinh viên | ✔ | – | – |
| Xem lớp mình dạy / học | ✔ | ✔ | ✔ |
| Tạo lịch, buổi học | ✔ | ✔ (lớp mình) | – |
| Mở/đóng buổi, điểm danh, sửa điểm danh | ✔ | ✔ | – |
| Xem điểm danh của mình | – | – | ✔ |
| Đăng ký khuôn mặt của mình / thu hồi đồng ý | – | – | ✔ |
| Quản lý cấu hình FaceID, reindex | ✔ | – | – |
| Gửi đơn xin vắng | – | – | ✔ |
| Duyệt đơn xin vắng | ✔ | ✔ | – |
| Ngân hàng câu hỏi (theo môn) | ✔ | ✔ | – |
| Tạo/công bố bài kiểm tra, chấm tay, xem thống kê | ✔ | ✔ | – |
| Làm bài kiểm tra, xem kết quả (theo `show_result`) | – | – | ✔ |
| Giao bài, chấm bài | ✔ | ✔ | – |
| Nộp bài | – | – | ✔ |
| Quản lý thành phần điểm, công bố điểm | ✔ | ✔ | – |
| Xem điểm của mình (sau công bố) | – | – | ✔ |
| Thông báo lớp (tạo) | ✔ | ✔ | – |
| Thông báo toàn hệ thống (tạo) | ✔ | – | – |
| Xem audit log, cấu hình hệ thống | ✔ | – | – |

---

## 6. Luật nghiệp vụ

### 6.1 Buổi học và điểm danh
- Tạo lịch (`schedules`) → sinh `sessions` cho mọi tuần từ `start_date` đến `end_date`. Kiểm tra **trùng lịch**: cùng phòng, hoặc cùng giảng viên, hoặc (sinh viên đã vào lớp có lịch khác) trùng giờ → từ chối với mã lỗi `SCHEDULE_CONFLICT` và chỉ ra bên xung đột.
- Trạng thái buổi: `scheduled → open → closed`; `scheduled → cancelled`. Không mở lại buổi đã `closed` trừ Admin (ghi audit).
- **Khi mở buổi:** tạo `attendance_records` cho mọi sinh viên `enrolled` với `status = absent`, `source = system`. Sinh viên có đơn xin vắng `approved` cho buổi này → `excused`, `source = leave`.
- **Quy tắc theo thời gian** (so với `start_time` của buổi), áp dụng khi có một lượt xác nhận có mặt (từ FaceID hoặc thủ công):
  - `now ≤ start + late_after_min` → `present`
  - `start + late_after_min < now ≤ start + absent_after_min` → `late`
  - `now > start + absent_after_min` → giữ nguyên `absent` (giảng viên có thể sửa tay)
- Bản ghi đã `present/late` **không bị hạ cấp** bởi nhận diện sau đó. Chỉ giảng viên/Admin mới đổi thủ công.
- **Sửa thủ công** bắt buộc có `note` (lý do); ghi `modified_by`, `source = manual` và một dòng `audit_logs` (trạng thái cũ → mới).
- **Khi đóng buổi:** bản ghi còn `absent` giữ nguyên; buổi không sửa được trừ Admin.
- **Chuyên cần của sinh viên trong lớp:**
  `attendance_score = 10 × Σ(trọng số theo trạng thái) / số buổi đã đóng`, với trọng số mặc định present = 1, late = 0.5, excused = 1, absent = 0 (cấu hình trong `classes`). Chỉ tính các buổi `closed`.
- **Cảnh báo:** số buổi `absent` ≥ `attendance_warning_absences` → gửi 1 thông báo cho sinh viên và hiện cờ cảnh báo trong báo cáo của giảng viên (không gửi lặp lại cho cùng ngưỡng).

### 6.2 Đơn xin vắng
- Sinh viên chỉ gửi cho buổi `scheduled` hoặc buổi đã qua trong vòng 7 ngày; một đơn đang chờ cho mỗi (sinh viên, buổi).
- Duyệt → buổi đó (nếu đã mở/đóng) cập nhật thành `excused`; nếu buổi chưa mở thì áp dụng khi mở buổi. Từ chối không đổi điểm danh. Gửi thông báo cho sinh viên.

### 6.3 Bài tập
- Chỉ sinh viên đã `enrolled` nộp được; nộp trễ khi `now > due_at`: nếu `allow_late = false` → từ chối `ASSIGNMENT_CLOSED`; nếu true → `is_late = true`.
- Nộp lại ghi đè file cũ, cập nhật `submitted_at`. Điểm đã chấm bị xóa khi nộp lại (có cảnh báo trên UI).
- Điểm 0 ≤ score ≤ max_score. Khi quy đổi vào bảng điểm: `score / max_score × 10`.

### 6.4 Bảng điểm
- Mỗi lớp có danh sách `grade_components` với tổng trọng số = 100 mới được công bố.
- Thành phần `attendance` lấy từ 6.1; `assignment` lấy từ bài tập (trung bình theo `ref_id` hoặc nhóm bài tập — chọn một bài tập cụ thể qua `ref_id`); `exam` lấy từ bài kiểm tra theo `score_policy`; `manual` do giảng viên nhập.
- **Điểm tổng kết = Σ(score × weight) / 100**, làm tròn 1 chữ số thập phân (HALF_UP). Thành phần chưa có điểm tính là 0 nhưng hiển thị rõ "chưa có".
- Chưa công bố → sinh viên không thấy điểm. Sau công bố, mọi sửa điểm phải ghi audit log.

### 6.5 Phân nhóm
- Mỗi sinh viên tối đa 1 nhóm trong một lớp. Chia ngẫu nhiên theo số nhóm hoặc số người/nhóm; có thể chuyển người thủ công.

---

## 7. Hợp đồng cắm FaceID (plug contract)

**Mục tiêu:** toàn bộ hệ thống (DB, API, giao diện điểm danh trực tiếp) hoàn chỉnh và chạy được với `MockFaceEngine`. Khi có engine thật, chỉ viết thêm **một file** `insightface_engine.py` và đổi cấu hình `FACE_ENGINE=insightface`.

### 7.1 Interface (`app/face/base.py`)
```python
@dataclass
class FaceBox:  x: float; y: float; w: float; h: float; det_score: float   # tọa độ chuẩn hóa 0..1

@dataclass
class EnrollResult:
    ok: bool
    quality_score: float | None
    embedding: bytes | None          # None khi engine chưa tạo được
    reason: str | None               # "no_face" | "multiple_faces" | "blurry" | "too_dark" | ...

@dataclass
class Candidate: student_id: int; embeddings: list[bytes]

@dataclass
class MatchResult:
    box: FaceBox
    student_id: int | None
    status: Literal["matched", "unknown", "ambiguous", "low_quality"]
    score: float | None
    margin: float | None             # chênh lệch với ứng viên tốt thứ hai

class FaceEngine(Protocol):
    name: str
    version: str
    is_ready: bool                   # mock = False
    def assess_enrollment(self, image: bytes) -> EnrollResult: ...
    def identify(self, image: bytes, candidates: list[Candidate]) -> list[MatchResult]: ...
    def embed_stored_image(self, image: bytes) -> EnrollResult: ...   # dùng cho reindex
```
- `factory.get_engine()` đọc `FACE_ENGINE` (`mock` mặc định).
- `MockFaceEngine`: `is_ready = False`; `assess_enrollment` trả `ok=True, embedding=None, quality=None` (ảnh được lưu `pending_embedding`); `identify` trả danh sách rỗng.

### 7.2 Luật dùng kết quả nhận diện (độc lập với engine, nằm ở `services/attendance_service.py`)
- Chỉ chấp nhận `status = matched` khi `score ≥ FACE_MATCH_THRESHOLD` **và** `margin ≥ FACE_MARGIN_THRESHOLD` (cấu hình, **chưa có giá trị mặc định cố định**; đặt giá trị tạm trong `.env.example` kèm ghi chú "phải hiệu chỉnh bằng thực nghiệm").
- Một sinh viên chỉ được tính có mặt sau `FACE_MIN_HITS` lượt `matched` liên tiếp hợp lệ (mặc định 3), ghi vào `hit_count`.
- `student_id` phải thuộc lớp của buổi và `enrolled`, nếu không bỏ qua và ghi `recognition_logs` loại `unknown`.
- Mọi lượt đều ghi `recognition_logs` (không lưu ảnh khung hình).
- `ambiguous`/`unknown`/`low_quality` **không** đổi điểm danh; hiện ở danh sách "Cần giảng viên xác nhận".

### 7.3 Endpoint
| Method | Đường dẫn | Vai trò | Mô tả |
|---|---|---|---|
| GET | `/face/status` | A, L | `{engine, version, is_ready}` — UI dùng để hiện banner "FaceID chưa kích hoạt" |
| POST | `/students/me/face/consent` | S | Ghi đồng ý (kèm `text_version`) |
| DELETE | `/students/me/face/consent` | S | Thu hồi: đặt template `revoked`, xóa file ảnh và embedding |
| POST | `/students/me/face/enroll` | S | Upload 1–5 ảnh (cần đồng ý). Lưu ảnh, gọi `assess_enrollment`, trả kết quả từng ảnh |
| GET | `/students/me/face` | S | Trạng thái hồ sơ khuôn mặt, số ảnh, `pending_embedding`/`active` |
| POST | `/admin/face/reindex` | A | Với mọi template `pending_embedding`: gọi `embed_stored_image`, cập nhật `embedding`, `status=active` (trả `409 ENGINE_NOT_READY` nếu mock) |
| POST | `/sessions/{id}/recognize` | L | Nhận một ảnh khung hình, trả `{engine, ready, faces: [...], attendance_changes: [...]}`. Với mock: `ready=false, faces=[]` |
| GET | `/sessions/{id}/recognition-feed` | L | Danh sách cần xác nhận + nhật ký gần nhất (UI polling 2 giây) |

### 7.4 Giao diện điểm danh trực tiếp (làm đầy đủ ngay bây giờ)
- Trang `/lecturer/sessions/:id/live`: khung video webcam (`getUserMedia`), nút Bắt đầu/Dừng quét, lớp phủ khung nhận diện, danh sách sinh viên theo trạng thái (màu **và** biểu tượng), bộ đếm có mặt/vắng, danh sách "Cần xác nhận", nút đổi trạng thái thủ công từng sinh viên.
- Cứ ~1 giây chụp một khung hình, gửi `POST /recognize`. Nếu `ready=false`: **hiện banner rõ ràng** "FaceID chưa kích hoạt — đang dùng điểm danh thủ công", vẫn cho điểm danh tay.
- Cấm thêm "nút giả lập nhận diện" vào bản nộp. Nếu cần demo luồng trước khi có engine, chỉ bật bằng biến `DEV_FACE_SIMULATOR=true` và hiển thị nhãn "MÔ PHỎNG" nổi bật; mặc định tắt.

> Lưu ý trung thực cho báo cáo: nếu nộp mà FaceID vẫn là mock, báo cáo phải nói rõ phần nhận diện chưa triển khai. Không được trình bày điểm danh thủ công như kết quả của FaceID.

---

## 8. Kiểm tra trực tuyến (chi tiết)

### 8.1 Câu hỏi
- Loại: `single` (1 đáp án đúng), `multiple` (≥ 1 đáp án đúng), `true_false`, `essay`.
- Ràng buộc: `single` có đúng 1 đáp án đúng; `multiple` ≥ 1; trắc nghiệm có từ 2 đến 6 lựa chọn.
- Ngân hàng theo **môn học**; lọc theo loại, độ khó, từ khóa; import từ Excel (mẫu tải về, báo lỗi theo dòng).

### 8.2 Tạo đề
- Chọn câu hỏi từ ngân hàng, đặt điểm từng câu, thứ tự. Tổng điểm quy về thang 10 khi vào bảng điểm.
- Cài đặt: thời lượng, khung `open_at`–`close_at`, xáo câu, xáo lựa chọn, số lần làm, chính sách điểm (cao nhất/lần cuối), khi nào xem kết quả, giới hạn vi phạm.
- Chỉ sửa nội dung đề khi **chưa có ai bắt đầu làm**; sau đó chỉ cho phép đổi `close_at`/trạng thái.

### 8.3 Làm bài (quy tắc quan trọng — phía server là nguồn sự thật)
1. `POST /exams/{id}/attempts` kiểm tra: sinh viên thuộc lớp, đề `published`, trong khung giờ, chưa vượt `max_attempts`, không có lượt `in_progress` khác (nếu có thì trả lại lượt đó để **tiếp tục làm**).
2. Server tạo `deadline_at = min(started_at + duration, close_at)`, sinh `question_order`/`option_order` bằng **Fisher–Yates** (seed theo `attempt_id` để tái lập được), lưu vào attempt.
3. API trả đề theo đúng thứ tự đã lưu, **không trả `is_correct` hay `explanation`**.
4. Đồng hồ hiển thị ở client chỉ để xem; server từ chối lưu/nộp sau `deadline_at` (cho phép trễ tối đa 5 giây, hằng số cấu hình). Đồng bộ lại thời gian còn lại với server mỗi lần tải lại trang.
5. Lưu nháp tự động: `PUT /attempts/{id}/answers/{question_id}` (debounce ở client), có thể reload mà không mất bài.
6. Nộp: `POST /attempts/{id}/submit`. Hết giờ mà chưa nộp → tự chốt `auto_submitted` bởi (a) tiến trình nền APScheduler quét mỗi 30 giây và (b) kiểm tra "lười" khi có bất kỳ truy cập nào vào attempt quá hạn.
7. Chấm tự động: `single`/`true_false` đúng hết hoặc 0; `multiple` điểm = points × max(0, (đúng chọn − sai chọn) / tổng đúng); `essay` để `score = NULL` chờ giảng viên. Attempt chuyển `graded` khi mọi câu đã có điểm.

### 8.4 Nhật ký hành vi (hạn chế gian lận, **không** phải giám sát đảm bảo)
- Client gửi sự kiện `visibilitychange`, `blur`, thoát toàn màn hình, copy, paste tới `POST /attempts/{id}/events`. Server tăng `violation_count` cho các loại cấu hình và nếu đạt `max_violations` + `auto_submit_on_violation` thì tự nộp.
- Giảng viên xem dòng thời gian sự kiện của từng bài. Nhật ký chỉ là **chỉ báo để xem xét**, không phải bằng chứng gian lận.
- Báo cáo phải nêu giới hạn: không chặn được thiết bị thứ hai, ảnh chụp màn hình, người hỗ trợ bên cạnh; sinh viên có thể vô hiệu hóa script phía client.

### 8.5 Kết quả và thống kê
- Sinh viên xem điểm và đáp án theo `show_result`.
- Giảng viên: điểm trung bình/cao/thấp, **histogram phân bố điểm**, tỷ lệ đúng từng câu (để phát hiện câu quá khó/quá dễ), danh sách bài đang làm/đã nộp/chưa làm, xuất Excel.
- Chấm tay tự luận: giao diện lần lượt từng bài, nhập điểm (≤ points) + nhận xét.

---

## 9. API tóm tắt

Chi tiết schema do agent sinh từ Pydantic; **cập nhật OpenAPI sau mỗi cột mốc**. Tất cả dưới `/api/v1`.

| Module | Endpoint chính |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/change-password`, `GET /auth/me` |
| Users | `GET/POST /users`, `PATCH /users/{id}` (khóa/mở, reset mật khẩu), `POST /users/import` |
| Danh mục | `/semesters`, `/subjects` (CRUD) |
| Giảng viên / Sinh viên | `/lecturers`, `/students` (CRUD, lọc, tìm kiếm, import/export Excel) |
| Lớp | `/classes` (CRUD), `/classes/{id}/students` (GET, POST, DELETE, import), `/classes/{id}/schedules`, `/classes/{id}/sessions`, `/classes/{id}/groups`, `/classes/{id}/attendance-report` |
| Buổi học | `POST /sessions/{id}/open`, `POST /sessions/{id}/close`, `GET /sessions/{id}/attendance`, `PATCH /sessions/{id}/attendance/{student_id}` (kèm `note`), `GET /sessions/{id}/attendance/export` |
| FaceID | Mục 7.3 |
| Đơn xin vắng | `POST /sessions/{id}/leave-requests`, `GET /leave-requests?status=`, `POST /leave-requests/{id}/review` |
| Ngân hàng câu hỏi | `GET/POST /subjects/{id}/questions`, `GET/PUT/DELETE /questions/{id}`; tải mẫu, xem trước và xác nhận nhập Excel tại `/subjects/{id}/questions/import/{template,preview,confirm}` |
| Kiểm tra | `/classes/{id}/exams` (CRUD đề nháp), `GET /classes/{id}/student-exams`, `POST /exams/{id}/attempts`, `GET /attempts/{id}`, `PUT /attempts/{id}/answers/{qid}`, `POST /attempts/{id}/submit`; các API publish/events/results/stats/grade còn thiếu |
| Bài tập | `/classes/{id}/assignments` (CRUD), `POST /assignments/{id}/submissions`, `GET /assignments/{id}/submissions`, `POST /submissions/{id}/grade` |
| Bảng điểm | `/classes/{id}/grade-components`, `GET /classes/{id}/gradebook`, `PUT /grades`, `POST /classes/{id}/gradebook/publish`, `GET /classes/{id}/gradebook/export`, `GET /students/me/grades` |
| Thông báo | `/classes/{id}/announcements`, `/announcements` (hệ thống), `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Dashboard | `GET /dashboard/admin`, `/dashboard/lecturer`, `/dashboard/student` |
| Hệ thống | `GET /audit-logs`, `GET/PUT /settings` |

---

## 10. Giao diện và luồng

### 10.1 Nguyên tắc UX (để "trực quan, luồng rõ ràng")
- Điều hướng bên trái theo vai trò; thanh trên có chuông thông báo, tên người dùng, đăng xuất.
- Mỗi trang có **tiêu đề, đường dẫn (breadcrumb), một hành động chính nổi bật**.
- Trạng thái điểm danh dùng màu **kèm** biểu tượng và chữ (có mặt ✔ xanh lá, trễ ◐ vàng cam, vắng ✖ đỏ, có phép ● xanh dương), nhất quán toàn hệ thống.
- Mọi bảng: phân trang phía server, tìm kiếm, lọc, trạng thái rỗng có hướng dẫn, trạng thái tải (skeleton), thông báo lỗi tiếng Việt cụ thể.
- Thao tác nguy hiểm (xóa, đóng buổi, nộp bài, công bố điểm) có hộp xác nhận nêu rõ hậu quả.
- Dùng Ant Design theo một theme duy nhất; không trộn thư viện UI khác.

### 10.2 Màn hình theo vai trò
**Chung:** Đăng nhập, Đổi mật khẩu, Hồ sơ cá nhân, Trung tâm thông báo.

**Admin:** Dashboard (số liệu + biểu đồ chuyên cần theo lớp) · Học kỳ · Môn học · Giảng viên · Sinh viên (+ import Excel có xem trước/báo lỗi dòng) · Lớp học phần (danh sách, tạo/sửa, tab: Sinh viên / Lịch & Buổi / Nhóm / Cài đặt điểm danh) · Cấu hình FaceID (trạng thái engine, reindex) · Nhật ký hệ thống · Cài đặt.

**Giảng viên:** Dashboard (buổi hôm nay, bài chờ chấm, lớp có sinh viên vắng nhiều) · Thời khóa biểu tuần · Lớp của tôi → trang lớp có tab: Tổng quan · Sinh viên · Buổi học · Điểm danh · Bài tập · Kiểm tra · Bảng điểm · Nhóm · Thông báo · Báo cáo chuyên cần · **Điểm danh trực tiếp** (mục 7.4) · Duyệt đơn xin vắng · Ngân hàng câu hỏi · Thống kê kiểm tra.

**Sinh viên:** Dashboard (lịch hôm nay, hạn nộp/kiểm tra sắp tới, tỷ lệ chuyên cần, cảnh báo) · Thời khóa biểu · Lớp của tôi → trang lớp: Thông báo · Bài tập · Kiểm tra · Điểm danh của tôi · Điểm · Nhóm · Đơn xin vắng · Đăng ký khuôn mặt (có văn bản đồng ý, hướng dẫn chụp, trạng thái hồ sơ, nút thu hồi) · **Màn hình làm bài** (toàn màn hình, đồng hồ, bảng điều hướng câu, trạng thái đã lưu).

### 10.3 Ba luồng chính phải trơn tru
1. **Thiết lập lớp (Admin):** tạo môn/học kỳ → tạo lớp → phân công giảng viên → import danh sách sinh viên → tạo lịch → hệ thống sinh buổi và báo xung đột nếu có.
2. **Một buổi học (Giảng viên):** vào buổi hôm nay → Mở buổi → điểm danh (live/thủ công) → xử lý "cần xác nhận" → Đóng buổi → xuất Excel. Chuyên cần cập nhật vào bảng điểm.
3. **Một bài kiểm tra:** giảng viên tạo đề + công bố → sinh viên nhận thông báo → làm bài (lưu nháp, đồng hồ server) → nộp/tự nộp → giảng viên chấm tự luận → xem thống kê → công bố điểm vào bảng điểm.

---

## 11. Phi chức năng và kiểm thử

### 11.1 Bảo mật và dữ liệu
- RBAC ở dependency của FastAPI **và** kiểm tra thành viên lớp ở service. Có test cho truy cập chéo (sinh viên A xem dữ liệu lớp B → 403/404).
- Không trả `password_hash`, `embedding`, đường dẫn file thật trong response.
- Chống SQL injection bằng ORM/tham số hóa; CORS cấu hình theo `.env`; header bảo mật cơ bản.
- Dữ liệu khuôn mặt là dữ liệu sinh trắc học: cần đồng ý rõ ràng, có thể thu hồi (xóa thật ảnh và embedding), phân quyền truy cập, không đưa vào log. Báo cáo dẫn Nghị định 13/2023/NĐ-CP.

### 11.2 Hiệu năng cơ bản
- Danh sách phân trang; index cho mọi FK và trường lọc thường dùng; tránh N+1 (dùng `selectinload`/`joinedload`).
- Lưu nháp bài thi và quét khung hình phải trả lời dưới ~300 ms ở lớp 60 sinh viên (đo bằng test đơn giản, báo kết quả).

### 11.3 Test bắt buộc (pytest)
- **Điểm danh:** xác định trạng thái theo mốc thời gian (biên: đúng `late_after_min`, đúng `absent_after_min`); không hạ cấp present; đơn xin vắng → excused; công thức `attendance_score`; cảnh báo không gửi lặp.
- **Lịch:** phát hiện trùng phòng/giảng viên/sinh viên; số buổi sinh ra đúng.
- **Bảng điểm:** tổng trọng số, làm tròn HALF_UP, thành phần thiếu điểm, chưa công bố thì sinh viên không thấy.
- **Kiểm tra:** Fisher–Yates tái lập được theo seed và là hoán vị đủ phần tử; chấm `multiple` các trường hợp biên; từ chối lưu sau `deadline_at`; tự nộp khi quá hạn; không lộ `is_correct`; vượt `max_attempts`; tiếp tục lượt đang làm.
- **Bài tập:** nộp trễ khi `allow_late` true/false; nộp lại ghi đè.
- **Phân quyền:** ma trận mục 5 (mỗi nhóm endpoint ít nhất một test cho vai trò sai).
- **FaceID khung:** mock engine → `/recognize` trả `ready=false`; đồng ý → đăng ký lưu ảnh `pending_embedding`; thu hồi → xóa file; reindex với mock → 409.
- Frontend: kiểm thử E2E (Playwright) cho 3 luồng ở mục 10.3 nếu có thể.

### 11.4 Dữ liệu mẫu (`scripts/seed.py`, chạy lặp lại được)
1 admin; 5 giảng viên (3 cơ hữu, 2 thỉnh giảng); 60 sinh viên; 6 môn; 1 học kỳ hiện tại; 4 lớp với lịch; mỗi lớp ≥ 12 buổi, một nửa đã `closed` có điểm danh đa dạng; 1 đề kiểm tra `published` với đủ 4 loại câu; 2 bài tập (có bài nộp đúng hạn/trễ); thành phần điểm mẫu; vài thông báo và đơn xin vắng. Tài khoản demo in ra màn hình khi seed.

---

## 12. Cột mốc (mỗi cột mốc: migration + API + UI + test + seed + cập nhật docs)

| # | Cột mốc | Điều kiện hoàn thành (demo được) |
|---|---|---|
| M0 | Nền tảng | docker-compose lên được; healthcheck; Alembic chạy; CI chạy lint + test; layout React + đăng nhập + route guard theo vai trò |
| M1 | Danh mục và người dùng | CRUD học kỳ, môn, giảng viên, sinh viên; import Excel sinh viên có báo lỗi dòng; khóa/mở tài khoản |
| M2 | Lớp học | Tạo lớp, phân công, thêm sinh viên, lịch → sinh buổi, báo trùng lịch; thời khóa biểu tuần |
| M3 | Điểm danh | Mở/đóng buổi, điểm danh thủ công, sửa có lý do + audit, đơn xin vắng, xuất Excel, báo cáo chuyên cần + cảnh báo |
| M4 | Khung FaceID | Đồng ý + đăng ký ảnh, `FaceEngine` + mock, `/recognize`, trang điểm danh trực tiếp hoàn chỉnh với banner "chưa kích hoạt", reindex trả 409 |
| M5 | Bài tập + Thông báo | Giao/nộp/chấm, thông báo lớp, chuông thông báo, nhóm |
| M6 | Kiểm tra trực tuyến | Đủ mục 8: ngân hàng, tạo đề, làm bài, tự chấm, chấm tay, sự kiện, thống kê |
| M7 | Bảng điểm + Dashboard | Thành phần điểm, tự tổng hợp, công bố, xuất Excel; dashboard 3 vai trò |
| M8 | Hoàn thiện | Audit log viewer, cài đặt, rà soát UX/lỗi, hiệu năng, bảo mật, tài liệu, quay video demo |
| M9 | **FaceID thật** (làm sau) | Viết `insightface_engine.py`, reindex ảnh đã lưu, hiệu chỉnh ngưỡng bằng thực nghiệm, đo chỉ số, cập nhật UI |

**Kịch bản demo chấp nhận (chạy từ DB trống + seed):**
1. Admin đăng nhập, tạo lớp, import 30 sinh viên (1 dòng lỗi được báo rõ), tạo lịch (1 lần bị báo trùng phòng).
2. Sinh viên đăng ký khuôn mặt có đồng ý; thu hồi và kiểm tra ảnh bị xóa.
3. Sinh viên gửi đơn xin vắng; giảng viên duyệt.
4. Giảng viên mở buổi, điểm danh 3 sinh viên ở các mốc giờ khác nhau (có mặt/trễ), sửa một người kèm lý do, đóng buổi, xuất Excel.
5. Giảng viên giao bài tập; sinh viên nộp đúng hạn và trễ; chấm điểm.
6. Giảng viên tạo và công bố đề thi; sinh viên làm bài, reload giữa chừng không mất bài, chuyển tab bị ghi nhận, hết giờ tự nộp.
7. Giảng viên chấm tự luận, xem histogram và tỷ lệ đúng từng câu.
8. Công bố bảng điểm; sinh viên thấy điểm tổng kết khớp công thức; xuất Excel.
9. Admin xem audit log của toàn bộ thao tác trên.

---

## 13. Đối chiếu thang điểm đề cương (để chuẩn bị tài liệu nộp)

### Quyết định giai đoạn 1 — M5a học liệu cơ bản (chủ dự án chốt 05/11/2026)
- Mỗi lớp có tab Học liệu, danh sách phân trang. Mỗi mục gồm tiêu đề, mô tả và một tệp hoặc một liên kết HTTPS. Không chia chương/tuần, không theo dõi tiến độ.
- Admin/giảng viên phụ trách được thêm, sửa, xóa; sinh viên đang enrolled chỉ xem/tải. Lớp đã đóng chỉ đọc. Học liệu mới có hiệu lực ngay sau khi lưu, không có vòng đời nháp/công bố riêng.
- Tệp dùng bộ kiểm tra đuôi, MIME, chữ ký và dung lượng hiện có (mặc định 10 MB); lưu ngoài public bằng tên ngẫu nhiên, tải qua API có kiểm quyền. API không trả đường dẫn thật. Link chỉ HTTPS, không tự tải nội dung phía server; mở tab mới có noopener/noreferrer.
- Mọi thay đổi schema qua migration; nghiệp vụ nằm trong services. Dữ liệu học liệu demo chỉ tạo qua scripts/seed.py. Không bổ sung thông báo tự động cho học liệu ở đợt này.
- API: GET/POST /classes/{id}/materials (POST multipart: title, description, url hoặc file); PATCH /materials/{id} (sửa title/description); DELETE /materials/{id}; GET /materials/{id}/file. Muốn thay nội dung nguồn, tạo mục mới và xóa mục cũ; không ghi đè tệp đang được sử dụng.
- Mã kiểm thử G1-1.8 thuộc báo cáo tổng hợp; phải có kiểm tra quyền chéo, HTTPS, tệp sai/quá cỡ, lớp đóng và ảnh minh chứng web. Không thêm đính kèm đơn xin vắng trong phạm vi này.

| Hạng mục đề cương | Sản phẩm cần có trong `docs/` hoặc repo |
|---|---|
| Khảo sát nghiệp vụ, công nghệ (CLO1.1) | Báo cáo tuần 1–3 (đã có); bảng so sánh Canvas/Moodle/Classroom ↔ tính năng đã chọn |
| Kế hoạch, phân công (CLO6) | Bảng cột mốc M0–M9; lịch sử commit/issue theo cột mốc |
| Phân tích hệ thống (CLO1.2) | Use case theo vai trò, quy trình hiện tại và đề xuất, kịch bản triển khai (mục 12) |
| Thiết kế hệ thống (CLO2.1) | Sơ đồ kiến trúc, sơ đồ triển khai, bảng công nghệ |
| Thiết kế mô hình (CLO2.2) | ERD đầy đủ, sơ đồ trạng thái (buổi học, bài thi), thiết kế pipeline FaceID và hợp đồng engine |
| Cài đặt chức năng (CLO3) | Hệ thống chạy được theo M0–M8; **phần FaceID (M9) và kiểm thử nhận diện là hạng mục không thể bỏ** |
| Kiểm thử, triển khai (CLO4) | Báo cáo kết quả pytest/E2E, hướng dẫn cài bằng docker-compose |
| Nội dung / hình thức báo cáo, slide | Do nhóm viết; dùng ảnh chụp màn hình thật và số liệu thật |

> Ghi chú về rủi ro điểm: bảng điểm trong đề cương bị lệch dòng nên chưa chắc điểm của từng mục con; cần xác nhận với GVHD, nhưng phần FaceID và kiểm thử nhận diện nhiều khả năng chiếm tỷ trọng lớn trong 4.5 điểm cài đặt. Hoàn thành M0–M8 mà bỏ M9 sẽ không đạt điểm cao.
## Cập nhật sau M1 và quyết định M2

### Tài khoản và đăng nhập (bổ sung mục 4, 6)
- users có cột must_change_password. Tạo tài khoản: username = mã SV/GV (chữ thường), mật khẩu tạm sinh ngẫu nhiên 10 ký tự (chữ + số), must_change_password = true. Chỉ lưu bản băm bcrypt.
- Khi must_change_password = true, mọi API (trừ đổi mật khẩu và GET /auth/me) trả 403 PASSWORD_CHANGE_REQUIRED.
- Mỗi request kiểm tra is_active và is_deleted từ DB; khóa/xóa/reset/đổi mật khẩu thu hồi refresh token.
- Mật khẩu mới: tối thiểu 8 ký tự, có chữ và số, không trùng tên đăng nhập hoặc mật khẩu cũ.
- Import sinh viên: xem trước -> xác nhận; MSSV đã tồn tại bị bỏ qua, không đổi mật khẩu; file mật khẩu tạm tạo trong bộ nhớ, trả một lần, không lưu đĩa/DB.
- Import tạo sinh viên mới yêu cầu cột mã khoa: đối chiếu danh mục khoa đang hoạt động, hiển thị mã và tên khoa khi xem trước, kiểm tra lại ở bước xác nhận. Dòng thiếu mã, mã không tồn tại hoặc khoa ngừng hoạt động là lỗi. Không tự suy đoán khoa; hồ sơ cũ không bị thay đổi qua import này. Import ghi danh sinh viên vào lớp là luồng riêng.

### Công nghệ giao diện (thay mục 3)
- Frontend: React 18, Vite, TypeScript, React Router, TanStack Query, shadcn/ui + Tailwind CSS, TanStack Table, react-hook-form + zod, dayjs, Recharts (qua thành phần biểu đồ của shadcn).
- Hỗ trợ giao diện Sáng / Tối / Theo hệ thống bằng biến CSS; component dùng chung nằm ở components/common.

### Lớp học và lịch (bổ sung mục 6.1)
- Ngày/giờ buổi học lưu bằng DATE/TIME giờ địa phương (Asia/Ho_Chi_Minh), không đổi UTC. weekday: 0 = Thứ Hai ... 6 = Chủ nhật.
- Lớp: draft -> active -> closed; active cần giảng viên và ít nhất 1 lịch; closed chỉ đọc; chỉ xóa lớp draft chưa có sinh viên và buổi.
- Ghi danh: chỉ sinh viên studying; rút = dropped; không vượt max_students (khóa hàng khi kiểm tra).
- Xung đột (trên các buổi cụ thể, bỏ qua buổi cancelled; giao nhau khi start < end_kia và start_kia < end): cùng phòng, cùng giảng viên, cùng sinh viên; kiểm tra cả khi tạo/sửa lịch và khi ghi danh; lỗi 409 SCHEDULE_CONFLICT có danh sách xung đột.
- Sửa/xóa lịch chỉ ảnh hưởng buổi scheduled; không đụng buổi open/closed. Có hủy buổi, sửa một buổi, thêm buổi bù.
- Thời khóa biểu: /me/timetable (giảng viên: lớp dạy; sinh viên: lớp đang học) và /admin/timetable (lọc theo giảng viên/phòng/lớp).

### Cột mốc (cập nhật mục 12)
M2a Backend lớp học | M2c Chuyển shadcn/ui + sáng/tối | M2b Giao diện lớp học | M5a Học liệu và lớp học trực tuyến (trước phần còn lại của M5)
## Cập nhật M3 (điểm danh thủ công, buổi học, đơn xin vắng)

### Vòng đời buổi học
- scheduled -> open -> closed; scheduled -> cancelled. Mở buổi: giảng viên của lớp/Admin, lớp active, mỗi lớp một buổi open, trong cửa sổ [bắt đầu - SESSION_OPEN_BEFORE_MIN (30), kết thúc + SESSION_OPEN_AFTER_END_MIN (60)]; Admin mở ngoài cửa sổ phải có lý do. DEV_ALLOW_OPEN_ANYTIME chỉ cho demo (mặc định false).
- Tự đóng sau SESSION_AUTO_CLOSE_AFTER_END_MIN (120) kể từ giờ kết thúc. Mở lại chỉ Admin có lý do.

### Bản ghi điểm danh
- Khi mở buổi tạo bản ghi cho mọi sinh viên enrolled: absent/system (hoặc excused/leave nếu có đơn approved). Idempotent; không xóa bản ghi. display_status "pending" khi absent + system + buổi đang open.
- Mốc giờ (apply_presence, dùng chung cho thủ công và FaceID): <= bắt đầu + late_after_min: present; <= bắt đầu + absent_after_min: late; sau đó giữ nguyên (OUTSIDE_WINDOW). Không hạ cấp present/late; excused giữ nguyên.
- Sửa thủ công: note bắt buộc khi đổi trạng thái đã do người/FaceID đặt hoặc khi sửa buổi đã đóng; không bắt buộc khi chuyển từ mặc định hệ thống trong buổi đang open. expected_status lệch -> 409 STALE_STATE.
- Sau khi đóng: Admin luôn sửa được; giảng viên trong EDIT_AFTER_CLOSE_HOURS (24) và có note. Có attendance_history cho mọi thay đổi.

### Đơn xin vắng
- Gửi cho buổi scheduled hoặc buổi đã qua <= 7 ngày; lý do bắt buộc (<= 500 ký tự); một đơn pending cho mỗi (sinh viên, buổi); sinh viên hủy được đơn pending; chưa có đính kèm (M5a). Duyệt: giảng viên của lớp/Admin; approve chỉ đổi bản ghi đang absent/system -> excused/leave; hết cửa sổ sửa chỉ Admin duyệt.

### Chuyên cần
- attendance_score = 10 x tổng(trọng số) / số bản ghi thuộc các buổi closed không bị hủy; Decimal, làm tròn 1 chữ số HALF_UP; không có buổi closed -> null.
- Cờ cảnh báo khi số absent >= attendance_warning_absences; thông báo thật gửi ở M5 (thay cho "gửi 1 thông báo" trong mục 6.1 cũ).
- Xuất Excel: theo buổi và theo lớp (3 sheet), chống formula injection, không chứa lý do xin vắng.

## Quy ước thiết kế frontend (áp dụng cho các màn hình đã có ở M0–M3)

### Hệ thiết kế
- Dùng React + Vite + TypeScript, shadcn/ui và Tailwind CSS hiện hữu; không thêm UI framework hoặc dependency UI chỉ để đổi giao diện.
- Tokens CSS semantic tại `frontend/src/index.css` là nguồn màu duy nhất cho component: background, foreground, card, popover, primary, secondary, muted, accent, destructive, border, input, ring và status success/warning/info.
- Giao diện theo phong cách **Modern Academic SaaS**: rõ ràng, bền vững khi đọc lâu, hạn chế gradient/shadow; không dùng card, icon hoặc màu chỉ để trang trí.
- Không hard-code màu trạng thái vào màn hình. Enum backend luôn được đổi thành nhãn tiếng Việt trong UI bằng component/hàm dùng chung; trạng thái quan trọng phải có text và icon, không chỉ có màu.

### Màu và theme
- Light: background `#F8FAFC`, surface/card `#FFFFFF`, primary `#2563EB`, foreground `#0F172A`, muted foreground `#64748B`, border `#E2E8F0`, secondary `#EFF4FB`, accent `#DBEAFE`.
- Dark: background `#0B1220`, card `#151F30`, popover/elevated surface `#1B2940`, primary `#60A5FA`, foreground `#F1F5F9`, muted foreground `#A3B2C7`, border `#334155`, secondary `#243247`, accent `#223A58`.
- Lưu lựa chọn Sáng/Tối/Hệ thống bằng ThemeProvider hiện hữu. Không dùng đen tuyệt đối; Card/Popover/Dialog phải phân tầng rõ với background.
- Màu phải đạt WCAG 2.2 AA khi ghép text và nền; destructive/success/warning/info giữ semantic riêng và có foreground tương phản.

### Typography, spacing và layout
- Dùng font system hiện có; chỉ thay font sau khi có phê duyệt riêng và kiểm tra hỗ trợ tiếng Việt/tải trang.
- Page title: 24–30px; section title: 18–20px; card title: 16px; body: 14–16px; helper/label: 12–14px.
- Spacing theo thang 4px. Radius cơ sở 8px; dialog/popover/card lớn có thể 12px. Shadow tiết chế, ưu tiên border.
- Mỗi trang có title, mô tả/ngữ cảnh khi cần, và primary action rõ ràng. Không dùng nested card nếu chỉ nhằm tạo khoảng trắng.

### Responsive, accessibility và trạng thái
- Kiểm tra tối thiểu tại 375px, 640px, 768px, 1024px, 1440px. Sidebar desktop chuyển thành navigation drawer trên mobile; tabs được scroll có chủ đích thay vì ép hẹp text.
- Bảng phải có chiến lược mobile: ẩn cột phụ hoặc chuyển sang summary phù hợp; không tạo horizontal overflow ở page container.
- Mọi page có loading skeleton, empty state có hướng dẫn, và error state hiển thị thông báo backend cùng thao tác thử lại khi phù hợp.
- Button chỉ có icon phải có `aria-label` và Tooltip; focus-visible luôn thấy được; animation không thiết yếu tôn trọng `prefers-reduced-motion`.
- Không đổi API, role/permission, routing, business rule hoặc schema database khi triển khai quy ước này.

### Quyết định UX quản trị Khoa và thời khóa biểu
- Khoa là đơn vị danh mục được gán trực tiếp cho **sinh viên, giảng viên và môn học**. Lớp học phần suy ra Khoa từ môn học; không lưu `department_id` lặp trên lớp để tránh dữ liệu mâu thuẫn.
- Dữ liệu cũ không được tự gán Khoa bằng cách đoán theo mã lớp, tên môn hoặc bộ môn. Admin phải gán/tinh chỉnh rõ ràng trong các form quản trị.
- Admin có danh sách Khoa và có thể lọc Sinh viên, Giảng viên, Môn học và Thời khóa biểu theo Khoa. Trang hồ sơ Admin chỉ hiển thị thông tin cá nhân, trạng thái tài khoản, Khoa và các dữ liệu liên quan mà API đã trả về.
- Lịch cá nhân của Sinh viên/Giảng viên giữ dạng tuần. Lịch toàn trường của Admin mặc định là **Danh sách** để điều phối dữ liệu dày đặc; chế độ **Lưới tuần** là chế độ rà soát song song có cuộn ngang chủ đích, không dùng card lớn theo ngày.

### Quyết định triển khai M4/M5
- M4 dùng `MockFaceEngine` mặc định và **không sinh kết quả nhận diện giả**. Khi engine chưa sẵn sàng, điểm danh trực tiếp luôn nêu rõ đang dùng thao tác thủ công; không có nút giả lập trong UI.
- Ảnh khuôn mặt chỉ được lưu sau khi sinh viên đồng ý. Thu hồi đồng ý xóa ảnh đã lưu và embedding, đồng thời đánh dấu template đã thu hồi.
- M5 dùng thông báo trong ứng dụng (polling 30 giây), không dùng WebSocket. Thông báo chỉ phát sinh từ hành động thật: giao/chấm bài tập, thông báo lớp, duyệt/từ chối đơn xin vắng và chạm ngưỡng cảnh báo chuyên cần.
- Thông báo không thay thế nội dung nghiệp vụ gốc: sinh viên vẫn xem bài tập, đơn và chuyên cần trong đúng lớp học phần. Chat là P2 nên không nằm trong M5.

### Quyết định M6: cấu hình bài kiểm tra và toàn màn hình
- Ngân hàng câu hỏi: admin quản lý tất cả; giảng viên xem và sử dụng câu hỏi của môn mình đang được phân công giảng dạy, chỉ sửa hoặc xóa câu do mình tạo. Phân công hợp lệ là lớp chưa xóa ở trạng thái nháp hoặc đang hoạt động; lớp đã đóng không duy trì quyền truy cập.
- Giảng viên được cấu hình theo từng đề các nhóm thông tin/thời gian, câu hỏi/điểm, hiển thị kết quả và chế độ làm bài/hành vi theo phạm vi mục 8. Giữ giới hạn sửa đề sau khi đã có người bắt đầu theo mục 8.2.
- Thay yêu cầu luôn toàn màn hình tại mục 10.2 bằng lựa chọn của giảng viên cho từng đề; mặc định không yêu cầu toàn màn hình. Trước khi bắt đầu, giải thích yêu cầu nếu được bật; nếu thiết bị/trình duyệt không hỗ trợ, phải thông báo rõ, không âm thầm chặn sinh viên.
- Chỉ ghi nhận sự kiện thoát toàn màn hình theo cấu hình khi đề yêu cầu toàn màn hình. Ghi sự kiện và tự nộp theo ngưỡng là hai lựa chọn riêng; mặc định không tự nộp theo hành vi. Sự kiện chỉ là chỉ báo cần xem xét, không kết luận gian lận.
- M6.2 bước soạn thảo: quản lý đề nháp theo lớp, chọn câu hỏi cùng môn, điểm (tối đa 4 chữ số thập phân), thứ tự và cấu hình. Đề nháp tham chiếu câu hỏi trong ngân hàng: sửa câu gốc sẽ ảnh hưởng đề nháp; không xóa câu đang được đề tham chiếu. Chưa cung cấp công bố hoặc làm bài. Trước khi mở công bố, phải bảo đảm nội dung, đáp án và điểm của bài đang làm không bị thay đổi bởi sửa ngân hàng, đồng thời thực hiện đầy đủ quy tắc mục 8.2–8.3.
- Mặc định cấu hình xem kết quả là sau khi đề đóng; giảng viên có thể chọn sau khi nộp hoặc không hiển thị. Khi sinh viên bị rút khỏi lớp trong lúc thi, từ chối các thao tác tiếp theo do không còn ghi danh, giữ bài và nhật ký để giảng viên/Admin xem. Lưu điểm dạng thập phân chính xác, hiển thị hai chữ số thập phân; điểm tổng kết theo mục 6.4.
- M6.3/M6.4 hiện có snapshot đề, lượt làm, tự chấm trắc nghiệm phía server, tự nộp nền, API sinh viên và giao diện danh sách/làm bài. API danh sách chỉ truy vấn đề `published`; các API làm bài kiểm tra quyền sinh viên, ghi danh, thời gian và giới hạn lượt. Response sinh viên không chứa đáp án đúng, giải thích hoặc điểm.
- Router lượt làm đã được gắn vào ứng dụng thực tế sau khi có giao diện sinh viên. API công bố đề vẫn chưa tồn tại; không thể đưa đề nháp lên cho sinh viên từ UI hiện tại. Không tự sửa trạng thái trong database để demo. Vì vậy có thể kiểm thử giao diện rỗng và kiểm thử API bằng database test cô lập, nhưng chưa thể demo luồng web đầu-cuối với đề thật.
- Màn hình làm bài hỗ trợ câu trắc nghiệm/tự luận, điều hướng câu, lưu nháp debounce, đồng hồ dựa trên deadline server, xác nhận nộp và tiếp tục lượt đang làm. Nếu yêu cầu toàn màn hình, trình duyệt được yêu cầu vào chế độ này; nếu không hỗ trợ/bị từ chối, thông báo rõ và vẫn cho tiếp tục theo quyết định mục 10. Không tuyên bố đang ghi nhận sự kiện thoát toàn màn hình: API sự kiện chưa triển khai.
- Chưa hoàn tất M6: API sự kiện hành vi, quy tắc xem kết quả theo `show_result`, chấm tay tự luận, thống kê, công bố đề, thông báo công bố và tích hợp bảng điểm chưa được nối đầy đủ. Không coi M6 là hoàn thành hoặc mở phát hành kiểm tra cho đến khi các phần này được thực hiện và kiểm thử.

### Giai đoạn 4 — M8: hoàn thiện web và nghiệm thu
- Chủ dự án chốt M8, yêu cầu luồng test và ảnh minh chứng từng task. Không triển khai engine M9.
- Task 4.1: audit log có lọc ngày Việt Nam, quyền Admin, nhãn nghiệp vụ, chi tiết an toàn, trạng thái tải/rỗng/lỗi và mobile.
- Task 4.2: kiểm định cấu hình/tài khoản; Admin xem các thông số vận hành không nhạy cảm và trạng thái FaceID hiện có. Không tạo cơ chế sửa tham số nghiệp vụ chưa được đặc tả.
- Task 4.3: hoàn thiện thông báo phân trang và thao tác lỗi; retry tệp bài tập trên cùng ID đã tạo, không tạo bài trùng.
- Task 4.4: rà soát responsive, sáng/tối, bàn phím, nhãn, trạng thái lỗi trên các luồng chính ba vai trò; không thêm thư viện UI.
- Task 4.5: đo và tối ưu truy vấn bảng điểm, chia tải frontend theo trang; ghi số đo và môi trường, không tuyên bố hiệu năng khi chưa đo.
- Task 4.6: kiểm thử quyền, dữ liệu nhạy cảm, cấu hình triển khai và hồi quy trên MySQL.
- Task 4.7: tài liệu cài đặt/demo, bằng chứng, video demo web và giới hạn nghiệm thu; seed từ DB trống và các kiểm tra bắt buộc.

### Quyết định giai đoạn 3 — M7
- Phạm vi được chủ dự án chốt: quản lý thành phần điểm, tổng hợp backend, bảng điểm giảng viên/công bố/Excel, bảng điểm sinh viên và dashboard ba vai trò (task 3.1–3.6).
- Thành phần chưa có điểm tính là 0 theo trọng số đã cấu hình, vẫn hiển thị “Chưa có”; không chia lại trọng số. Tổng kết làm tròn một chữ số HALF_UP theo mục 6.4.
- Thành phần bài tập chọn một bài cụ thể qua ref_id; thành phần kiểm tra chọn một đề cụ thể cùng lớp. Chuyên cần và nhập tay không có ref_id.
- Cấu hình điểm và điểm nguồn được tổng hợp trực tiếp. Khi thay đổi cấu hình làm tổng trọng số khác 100%, bảng điểm tổng hợp tạm ẩn với sinh viên và chặn công bố; khi tổng trở lại 100%, trạng thái công bố có sẵn được áp dụng. Mọi thao tác sửa cấu hình/nhập tay ghi audit; sửa điểm nguồn tiếp tục ghi audit tại dịch vụ nguồn hiện hữu.
- Bảng điểm công bố cho phép xem điểm thành phần tổng hợp; không mở quyền xem đáp án/chi tiết bài kiểm tra bị ẩn bởi show_result. Giao diện nêu rõ sự khác biệt này.
- Sửa thành phần giữ nguyên loại và nguồn; có thể sửa tên/trọng số. Muốn thay loại/nguồn thì xóa thành phần và tạo lại, với cảnh báo mất điểm tay của thành phần bị xóa.

### Quyết định triển khai giai đoạn 2 (M6)
- Giai đoạn 2 hoàn thiện công bố đề, thông báo, làm bài, sự kiện, chấm tự luận, kết quả và thống kê của M6; tích hợp bảng điểm thuộc M7, chưa triển khai trong giai đoạn này.
- Đóng đề sớm cần hộp xác nhận và chốt tất cả lượt đang làm bằng các câu trả lời server đã nhận. Đổi giờ đóng điều chỉnh deadline bằng min(giờ bắt đầu + thời lượng ban đầu, giờ đóng mới); không hồi sinh lượt đã nộp hoặc đã quá hạn. Quy tắc này được chủ dự án chốt ngày 05/11/2026.
- Công bố đóng băng nội dung/đáp án/điểm; sửa ngân hàng không đổi đề đã công bố. Trước lượt đầu tiên có thể sửa đề đã công bố và tạo lại snapshot; từ lượt đầu tiên chỉ đổi giờ đóng hoặc đóng đề.
- Mỗi sự kiện có UUID để retry không tính hai lần; thời điểm do server ghi, không lưu nội dung clipboard. Sự kiện là chỉ báo cần xem xét, không kết luận gian lận. Không ghi sự kiện sau khi lượt đã chốt.
- Điểm tổng của lượt có tự luận chỉ hoàn tất khi mọi câu tự luận đã được chấm. Điểm được chọn theo highest/last chỉ hoàn tất khi tất cả lượt đã bắt đầu được chấm xong; thống kê nêu rõ số lượt chờ chấm.
- Các ghi chú M6.2–M6.4 ở trên mô tả trạng thái trước giai đoạn 2, được thay thế theo phạm vi triển khai và kết quả kiểm thử giai đoạn 2 trong tài liệu kiểm thử tổng hợp.

### Bổ sung F04: chuỗi nhận diện và retry khung hình
- Với engine sẵn sàng, `/sessions/{id}/recognize` yêu cầu thêm multipart `frame_id` dạng UUID. Mỗi lần chụp tạo một UUID; retry cùng lần chụp phải dùng lại cùng ID và nội dung. Mock vẫn trả `ready=false` và không ghi nhận diện/điểm danh.
- Backend ghi kết quả theo UNIQUE(session_id, frame_id) trong `recognition_frames` qua migration 0014. Retry cùng ID/nội dung trả kết quả đã xử lý, không gọi engine, tăng hit hoặc ghi log lần hai; cùng ID nhưng nội dung khác trả 409 FRAME_ID_REUSED. Chỉ lưu hash nội dung và kết quả, không lưu ảnh camera.
- Một khung hình chỉ duy trì chuỗi hit của những sinh viên enrolled được khớp hợp lệ trong khung đó. Không có mặt, unknown không có ID, ambiguous, low_quality, thiếu/dưới ngưỡng/không hữu hạn score hoặc margin, và sinh viên không xuất hiện trong khung đều ngắt chuỗi của sinh viên tương ứng. Reset hit không thay trạng thái chuyên cần đã ghi.
- Nhiều box cùng trỏ về một sinh viên trong một khung được coi là ambiguous, không cộng nhiều hit. Các sinh viên khác nhau có thể cùng nhận một hit trong khung. Khóa hàng buổi học để tuần tự hóa xử lý frame và retry giữa nhiều request/process.
- “Liên tiếp” áp dụng trên các frame mới được backend xử lý thành công theo thứ tự xử lý, không phải bảo đảm theo dõi liên tục ngoài camera. `frame_id` chống retry tính lặp, không phải liveness hoặc chống phát lại ảnh bằng ID mới. Ngưỡng nhận diện thật vẫn phải hiệu chỉnh thực nghiệm ở M9.

### Bổ sung F07: đồng ý khuôn mặt và phục hồi xóa dữ liệu
- Các thao tác đồng ý/đăng ký/thu hồi/reindex và đọc gallery nhận diện dùng khóa hàng sinh viên trong DB; đọc lại consent/template bằng locking read để không dùng snapshot cũ. Thao tác nhiều sinh viên khóa theo ID tăng dần.
- Thu hồi vô hiệu hóa tất cả consent còn hiệu lực, đặt template revoked và xóa embedding. Nếu một tệp không xóa được, vẫn lưu trạng thái ngừng dùng dữ liệu, trả FACE_DATA_DELETE_FAILED; không báo đã xóa hết.
- Hồ sơ khuôn mặt thêm cleanup_pending. Khi còn tệp cần xóa, UI cho thử xóa lại; chưa cho đồng ý lại hoặc đăng ký thêm. Xóa lại là idempotent, kể cả tệp đã mất ở lần trước.
- Đường dẫn của template revoked được giữ đến khi xóa thành công; ảnh ghi dở không còn bản ghi DB được phát hiện trong đúng thư mục riêng của sinh viên. Không quét đệ quy, không xóa đường dẫn nằm ngoài thư mục này. Không cần thay schema.
- Lỗi engine/ghi file/commit khi đăng ký phải rollback và thử dọn ảnh ghi dở; nếu chưa dọn được, hồ sơ nêu rõ cần xóa lại. Reindex không kích hoạt template khi consent đã hết hiệu lực.
- Chỉ dùng kết quả nhận diện mới cho ID có template active/embedding và consent còn hiệu lực. Kết quả retry frame đã xử lý vẫn là snapshot lịch sử theo F04, không chạy engine hay cộng hit mới. Không thay đổi điểm danh lịch sử khi thu hồi.
- Database và filesystem không có giao dịch nguyên tử chung. Cơ chế này hỗ trợ retry khi còn DB/thư mục riêng; không bảo đảm tự khôi phục sau mọi tình huống mất DB/ổ đĩa hoặc process bị kill. Không thêm tác vụ dọn nền trong F07.

### Bổ sung M9a: engine OpenCV (YuNet + SFace)
- Theo yêu cầu của chủ dự án, M9 dùng engine `FACE_ENGINE=opencv` (`app/face/opencv_engine.py`, OpenCV YuNet phát hiện + SFace nhận diện) thay cho InsightFace nêu ở mục 3. Hợp đồng mục 7 không đổi; `FACE_ENGINE` mặc định vẫn là `mock`; InsightFace vẫn có thể cắm sau.
- `is_ready` là false khi thiếu/hỏng trọng số hoặc `FACE_MATCH_THRESHOLD <= 0`; khi đó hành xử như mock (mục 7.1), không tạo kết quả giả.
- Embedding là 128 float32 chuẩn hóa L2, mã hóa Fernet khi có `FACE_EMBEDDING_KEY` (bắt buộc ở production với engine này). Điểm của sinh viên là trung bình hai cosine cao nhất với các mẫu của sinh viên; `margin` là chênh lệch với sinh viên tốt thứ hai (một ứng viên thì coi thứ hai là 0). Luật dùng kết quả ở mục 7.2 và F04/F07 không đổi và vẫn nằm ở `services/`.
- Mã lý do đăng ký bổ sung: `invalid_image`, `face_too_small`, `too_bright`, `low_contrast`, `tilted_head`, `near_edge`, `feature_failed`.
- Liveness vẫn ngoài phạm vi (mục 2, P2). Ngưỡng và chỉ số chất lượng là heuristic; phải hiệu chỉnh và đo bằng `backend/face_tools/evaluation` trước khi báo cáo độ chính xác. Trọng số không đóng gói; tải bằng `backend/face_tools/download_face_models.py`. Hướng dẫn: `docs/FACE-ENGINE-OPENCV.md`.
