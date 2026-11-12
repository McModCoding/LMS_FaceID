# Danh gia ban ung vien nop khoa luan - LMS FaceID (Nam + Thanh)

## Pham vi co trong ma nguon

- LMS React/TypeScript, FastAPI, MySQL 8, migrations Alembic, vai tro admin / giang vien / sinh vien, quan ly lop, hoc lieu, bai tap, bai kiem tra, diem, thong bao va diem danh.
- FaceID: YuNet (phat hien) + SFace (embedding/nhan dien), luong dong y, dang ky anh, reindex, nhan dien va luu ket qua diem danh; bo cong cu danh gia thuc nghiem tu goi `lms-faceid-integrated.zip` da duoc giu lai.
- Khong co route cong khai `POST /api/v1/auth/register` hoac trang sinh vien tu dang ky. Tai khoan do admin quan ly.

## Cac sua doi o goi nay

1. Khai bao `pydantic[email]` de co `email-validator` (chong loi backend khong import duoc).
2. Co dinh `passlib==1.7.4` va `bcrypt==4.0.1`, bo sung smoke-test bam/xac minh mat khau.
3. Docker backend chay mot Uvicorn worker khong `--reload`, co `healthcheck`. Frontend doi backend healthy va Vite proxy `/api` toi backend.
4. Dockerfile backend sao chep source `app` truoc khi pip editable install, frontend dung `npm ci --legacy-peer-deps` theo lockfile.
5. Script seed an toan: tu choi neu DB da co user. `get_or_create_user` khong ghi de mat khau va trang thai cua tai khoan ton tai.
6. Bo script Windows tu tao `.env` mot lan, cai dat, kiem tra HTTP, seed an toan, kiem tra tai khoan, xuat log, dung/chay lai; khong xoa MySQL volume.
7. Dung ten project Compose on dinh `lms_faceid_capstone_v33` de doi thu muc V3.3 khong tao DB moi. **Khong tu dong tai su dung DB V1/V2 cu**; can luu y khi nang cap.
8. Cau hinh demo moi chon `FACE_ENGINE=opencv`, sinh khoa Fernet, ngưong 0.363/0.05 CHI MANG TINH THU NGHIEM.

## Phan da kiem tra trong moi truong tao goi

- Kiem tra cu phap Python bang `compileall` va `ast.parse`.
- Chay 42 bai unit test rieng ve OpenCVFaceEngine/face evaluation voi detector-recognizer gia tren ma nguon hien tai.
- Kiem tra syntax TypeScript/TSX bang TypeScript parser va doc cau hinh YAML/ZIP.

## Phan chua du bang chung de ket luan hoan thanh

- **Chua chay Docker/MySQL that trong moi truong nay** (khong co Docker daemon), chua chay integration tests tren MySQL hay migrations voi CSDL that.
- **Chua tai va chay model ONNX that**, chua do FAR, FRR, Precision, Recall, F1, thoi gian suy luan tren bo anh co nhan.
- **Chua thu nghiem dau-cuoi tren Windows cua nguoi dung**: API, dang nhap ba role, gui anh, diem danh, query DB.
- **Canvas LMS**: adapter dong bo Canvas khong duoc chuyen vao backend nay. Khong duoc trinh bay la da hoan tat neu de tai/ke hoach bat buoc co Canvas.
- **Khong co anti-spoofing/liveness**; khong khang dinh he thong ngan gian lan bang anh/video.

## Danh sach can co truoc khi nop/bao ve

- [ ] Setup tu may moi hoac moi truong sach, chup `docker compose ps` va HTTP 200 `/health`, `/api/docs`.
- [ ] Seed tren DB demo trong, dang nhap thanh cong admin/gv001/sv001; Admin tao user moi va kiem tra MySQL.
- [ ] Kiem tra student consent, dang ky anh, thu hoi du lieu, reindex.
- [ ] Demo diem danh khuon mat that va sua diem danh thu cong khi nhan dien sai.
- [ ] Doi chieu bang SQL/log: moi record dung student_id/class_id/session_id, khong nhan trung do retry.
- [ ] Tap validation/test doc lap, bao cao F1 detection, FAR/FRR, confusion, latency (so lieu do duoc, khong bịa).
- [ ] Luu code, model SHA-256, config/ngưong, anh ket qua va tai lieu kien truc/API/quyen rieng tu.
- [ ] Xac nhan voi giang vien huong dan yeu cau Canvas LMS; neu bat buoc thi phai trien khai them.

**Ket luan:** Ung vien demo tot hon ban goc ve dong goi/sua loi startup, nhung khong the goi la 'da nghiem thu hoan chinh 100%' khi cac muc tren chua duoc kiem chung.
