import io
import unicodedata
from datetime import date, datetime

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill


def sanitize_formula(val: str | None) -> str:
    """Chống Formula Injection: Nếu giá trị bắt đầu bằng =, +, -, @ thì thêm dấu ' ở đầu."""
    if not val:
        return ""
    s = str(val).strip()
    if s and s[0] in ("=", "+", "-", "@"):
        return "'" + s
    return s


def normalize_text(val: str | None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return unicodedata.normalize("NFC", s)


def parse_date_val(val: str | None) -> str | None:
    if not val:
        return None
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s


def generate_student_import_template() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Danh sách sinh viên"

    headers = [
        "MSSV (*)",
        "Họ và tên (*)",
        "Lớp hành chính",
        "Ngày sinh (DD/MM/YYYY)",
        "Giới tính",
        "Số điện thoại",
        "Email",
        "Mã khoa (*)",
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    sample = ["2026000001", "Nguyễn Văn A", "CNTT K65", "15/05/2003", "Nam", "0901234567", "nguyenvana@gmail.com", "CNTT"]
    ws.append(sample)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def parse_student_import_excel(file_bytes: bytes) -> tuple[list[dict], list[dict], list[dict]]:
    # Giới hạn dung lượng 5MB
    if len(file_bytes) > 5 * 1024 * 1024:
        return [], [], [{"row": 1, "reason": "Dung lượng file vượt quá giới hạn cho phép (tối đa 5MB)."}]

    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), data_only=True, read_only=True)
        ws = wb.active
    except Exception as e:
        return [], [], [{"row": 1, "reason": f"Không thể đọc file Excel (chỉ hỗ trợ định dạng .xlsx hợp lệ): {e!s}"}]

    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) <= 1:
        return [], [], [{"row": 1, "reason": "File Excel rỗng hoặc không có dữ liệu."}]

    # Giới hạn 500 dòng dữ liệu
    data_rows = rows[1:]
    if len(data_rows) > 500:
        return [], [], [{"row": 1, "reason": "File vượt quá số dòng cho phép (tối đa 500 dòng dữ liệu)."}]

    header_row = [str(cell).strip().lower() if cell is not None else "" for cell in rows[0]]

    col_map = {}
    for idx, h in enumerate(header_row):
        h_norm = unicodedata.normalize("NFC", h)
        if "mã khoa" in h_norm or "ma khoa" in h_norm or "department_code" in h_norm:
            col_map["department_code"] = idx
        elif "khoa" in h_norm or "department" in h_norm:
            # Tên khoa không phải mã khoa hoặc họ tên sinh viên.
            continue
        elif "mssv" in h_norm or "mã sinh viên" in h_norm or "student_code" in h_norm:
            col_map["student_code"] = idx
        elif "họ" in h_norm or "full_name" in h_norm or "tên" in h_norm:
            col_map["full_name"] = idx
        elif "lớp" in h_norm or "admin_class" in h_norm:
            col_map["admin_class"] = idx
        elif "ngày sinh" in h_norm or "dob" in h_norm:
            col_map["dob"] = idx
        elif "giới tính" in h_norm or "gender" in h_norm:
            col_map["gender"] = idx
        elif "điện thoại" in h_norm or "sđt" in h_norm or "phone" in h_norm:
            col_map["phone"] = idx
        elif "email" in h_norm:
            col_map["email"] = idx

    # Chỉ dùng thứ tự cũ nếu không nhận diện được bất kỳ tiêu đề nào;
    # nếu không, việc đoán vị trí có thể đọc nhầm một cột khác.
    legacy_positions = not col_map
    if legacy_positions and len(header_row) > 0:
        col_map["student_code"] = 0
    if legacy_positions and len(header_row) > 1:
        col_map["full_name"] = 1
    if legacy_positions and len(header_row) > 2:
        col_map["admin_class"] = 2
    if legacy_positions and len(header_row) > 3:
        col_map["dob"] = 3
    if legacy_positions and len(header_row) > 4:
        col_map["gender"] = 4
    if legacy_positions and len(header_row) > 5:
        col_map["phone"] = 5
    if legacy_positions and len(header_row) > 6:
        col_map["email"] = 6

    valid_rows = []
    warning_rows = []
    error_rows = []
    seen_codes = set()

    for r_idx, curr_row in enumerate(data_rows, start=2):
        if not any(curr_row):
            continue

        def get_val(key: str, r=curr_row):
            idx = col_map.get(key)
            if idx is not None and idx < len(r) and r[idx] is not None:
                return normalize_text(str(r[idx]))
            return None

        student_code = get_val("student_code")
        full_name = get_val("full_name")
        admin_class = get_val("admin_class")
        dob_raw = None
        idx_dob = col_map.get("dob")
        if idx_dob is not None and idx_dob < len(curr_row) and curr_row[idx_dob] is not None:
            dob_raw = parse_date_val(curr_row[idx_dob])

        gender = get_val("gender")
        phone = get_val("phone")
        email = get_val("email")

        if not student_code:
            error_rows.append({
                "row": r_idx,
                "student_code": None,
                "full_name": full_name,
                "reason": f"Dòng {r_idx}: Thiếu mã số sinh viên (MSSV).",
            })
            continue

        if not full_name:
            error_rows.append({
                "row": r_idx,
                "student_code": student_code,
                "full_name": None,
                "reason": f"Dòng {r_idx}: Thiếu họ và tên sinh viên.",
            })
            continue

        if student_code in seen_codes:
            error_rows.append({
                "row": r_idx,
                "student_code": student_code,
                "full_name": full_name,
                "reason": f"Dòng {r_idx}: MSSV {student_code} bị trùng lặp với dòng trước trong file Excel.",
            })
            continue

        seen_codes.add(student_code)

        valid_rows.append({
            "row": r_idx,
            "student_code": student_code,
            "full_name": full_name,
            "admin_class": admin_class,
            "dob": dob_raw,
            "gender": gender,
            "phone": phone,
            "email": email,
            "department_code": get_val("department_code"),
        })

    return valid_rows, warning_rows, error_rows


def generate_student_import_result_excel(students_data: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kết quả tạo tài khoản"

    headers = ["MSSV", "Họ và tên", "Email", "Mật khẩu tạm"]
    ws.append(headers)

    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for st in students_data:
        ws.append([
            sanitize_formula(st.get("student_code")),
            sanitize_formula(st.get("full_name")),
            sanitize_formula(st.get("email")),
            sanitize_formula(st.get("temp_password")),
        ])

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_student_export_excel(students_list: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Danh sách sinh viên"

    headers = ["STT", "MSSV", "Họ và tên", "Lớp hành chính", "Ngày sinh", "Giới tính", "Số điện thoại", "Email", "Trạng thái"]
    ws.append(headers)

    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for idx, st in enumerate(students_list, 1):
        dob_str = str(st.dob) if getattr(st, "dob", None) else ""
        status_val = st.status.value if hasattr(st.status, "value") else str(st.status)
        ws.append([
            idx,
            sanitize_formula(st.student_code),
            sanitize_formula(st.full_name),
            sanitize_formula(st.admin_class),
            dob_str,
            sanitize_formula(st.gender),
            sanitize_formula(st.phone),
            sanitize_formula(st.email),
            status_val,
        ])

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
