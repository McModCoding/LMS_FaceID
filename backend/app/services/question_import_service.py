from io import BytesIO
from zipfile import ZipFile

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from pydantic import ValidationError

from app.schemas.question import QuestionIn

HEADERS = ["Loai", "Noi dung", "Do kho", "Giai thich", "A", "B", "C", "D", "E", "F", "Dap an dung"]
MAX_ROWS = 500
MAX_BYTES = 5 * 1024 * 1024


def template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Cau hoi"
    sheet.append(HEADERS)
    sheet.freeze_panes = "A2"
    instructions = workbook.create_sheet("Huong dan")
    instructions.append(["Loai: single, multiple, true_false, essay"])
    instructions.append(["Do kho: easy, medium, hard"])
    instructions.append(["Dap an dung: nhap A hoac A,C. Cau tu luan de trong cac dap an."])
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def preview(content: bytes, filename: str) -> dict:
    if not filename.lower().endswith(".xlsx") or len(content) > MAX_BYTES:
        raise HTTPException(400, detail={"code": "INVALID_FILE", "message": "Chọn tệp .xlsx không quá 5 MB."})
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(entry.file_size for entry in entries) > 30 * 1024 * 1024:
                raise ValueError("expanded file too large")
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=False)
        sheet = workbook.active
        first = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
        if list(first[:len(HEADERS)]) != HEADERS:
            raise ValueError("headers")
        if sheet.max_row > MAX_ROWS + 1:
            raise HTTPException(400, detail={"code": "TOO_MANY_ROWS", "message": "Tối đa 500 dòng dữ liệu mỗi lần nhập."})
        valid, errors = [], []
        for row_number, cells in enumerate(sheet.iter_rows(min_row=2, max_col=len(HEADERS)), 2):
            values = [cell.value for cell in cells]
            if not any(value is not None and str(value).strip() for value in values):
                continue
            try:
                if any(cell.data_type == "f" for cell in cells):
                    raise ValueError("Không chấp nhận công thức Excel")
                values = [str(value).strip() if value is not None else "" for value in values]
                keys = [key.strip().upper() for key in values[10].split(",") if key.strip()]
                if len(keys) != len(set(keys)) or any(key not in "ABCDEF" or len(key) != 1 for key in keys):
                    raise ValueError("Đáp án đúng phải là A–F, cách nhau bằng dấu phẩy")
                options = [{"content": value, "is_correct": chr(65 + i) in keys}
                           for i, value in enumerate(values[4:10]) if value]
                available = {chr(65 + i) for i, value in enumerate(values[4:10]) if value}
                if not set(keys).issubset(available):
                    raise ValueError("Đáp án đúng phải tương ứng với lựa chọn có nội dung")
                item = QuestionIn.model_validate({"type": values[0], "content": values[1],
                    "difficulty": values[2], "explanation": values[3] or None, "options": options})
                valid.append({"row": row_number, "item": item.model_dump(mode="json")})
            except (ValueError, ValidationError) as exc:
                message = str(exc) if not isinstance(exc, ValidationError) else "; ".join(
                    str(error["msg"]) for error in exc.errors())
                errors.append({"row": row_number, "message": message})
        return {"valid": valid, "errors": errors}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, detail={"code": "INVALID_FILE", "message": "Tệp không đúng mẫu hoặc không đọc được."}) from exc
