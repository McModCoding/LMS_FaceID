import logging
from datetime import date, datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import generate_temp_password, get_password_hash
from app.models.department import Department
from app.models.student import Student, StudentStatus
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentUpdate
from app.services.audit_service import log_action
from app.utils.excel import (
    generate_student_export_excel,
    generate_student_import_result_excel,
    parse_student_import_excel,
)

logger = logging.getLogger(__name__)


def get_students_paginated(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    status_filter: StudentStatus | None = None,
    department_id: int | None = None,
) -> tuple[list[dict], int]:
    query = db.query(Student, User).join(User, Student.user_id == User.id).filter(Student.is_deleted == False)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Student.student_code.ilike(search_pattern),
                Student.full_name.ilike(search_pattern),
                Student.admin_class.ilike(search_pattern),
                User.email.ilike(search_pattern),
            )
        )

    if status_filter:
        query = query.filter(Student.status == status_filter)
    if department_id == 0:
        query = query.filter(Student.department_id.is_(None))
    elif department_id:
        query = query.filter(Student.department_id == department_id)

    total = query.count()
    results = query.order_by(Student.student_code.asc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for st, usr in results:
        items.append({
            "id": st.id,
            "user_id": st.user_id,
            "student_code": st.student_code,
            "full_name": st.full_name,
            "email": usr.email,
            "department_id": st.department_id,
            "department_name": st.department.name if st.department else None,
            "admin_class": st.admin_class,
            "dob": st.dob,
            "gender": st.gender,
            "phone": st.phone,
            "status": st.status,
            "is_deleted": st.is_deleted,
            "user_is_active": usr.is_active,
            "created_at": st.created_at,
        })

    return items, total


def get_student_by_id(db: Session, student_id: int) -> dict:
    result = (
        db.query(Student, User)
        .join(User, Student.user_id == User.id)
        .filter(Student.id == student_id, Student.is_deleted == False)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Không tìm thấy sinh viên."},
        )
    st, usr = result
    return {
        "id": st.id,
        "user_id": st.user_id,
        "student_code": st.student_code,
        "full_name": st.full_name,
        "email": usr.email,
        "department_id": st.department_id,
        "department_name": st.department.name if st.department else None,
        "admin_class": st.admin_class,
        "dob": st.dob,
        "gender": st.gender,
        "phone": st.phone,
        "status": st.status,
        "is_deleted": st.is_deleted,
        "user_is_active": usr.is_active,
        "created_at": st.created_at,
    }


def get_my_student(db: Session, user: User) -> dict:
    if user.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên mới xem được hồ sơ này."},
        )
    student = db.query(Student).filter(
        Student.user_id == user.id, Student.is_deleted == False
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Không tìm thấy hồ sơ sinh viên."},
        )
    return get_student_by_id(db, student.id)


def create_student(
    db: Session,
    data: StudentCreate,
    admin_id: int | None = None,
    ip: str | None = None,
) -> tuple[dict, str]:
    username = data.student_code.lower().strip()

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "STUDENT_CODE_EXISTS", "message": f"MSSV/tài khoản sinh viên {data.student_code} đã tồn tại."},
        )

    existing_email = db.query(User).filter(User.email == data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMAIL_EXISTS", "message": f"Email {data.email} đã được sử dụng."},
        )

    temp_password = generate_temp_password(10)
    password_hash = get_password_hash(temp_password)

    user = User(
        username=username,
        email=data.email,
        password_hash=password_hash,
        role=UserRole.student,
        is_active=True,
        must_change_password=True,
        is_deleted=False,
    )
    db.add(user)
    db.flush()

    st = Student(
        user_id=user.id,
        student_code=data.student_code.strip(),
        full_name=data.full_name.strip(),
        admin_class=data.admin_class,
        dob=data.dob,
        gender=data.gender,
        phone=data.phone,
        email=data.email,
        department_id=data.department_id,
        status=data.status,
        is_deleted=False,
    )
    db.add(st)
    db.flush()

    log_action(
        db=db,
        user_id=admin_id,
        action="CREATE_STUDENT",
        entity="students",
        entity_id=str(st.id),
        detail={
            "student_code": st.student_code,
            "full_name": st.full_name,
            "admin_class": st.admin_class,
            "department_id": st.department_id,
            "summary": f"Thêm mới sinh viên {st.student_code} - {st.full_name}",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(st)

    st_data = {
        "id": st.id,
        "user_id": st.user_id,
        "student_code": st.student_code,
        "full_name": st.full_name,
        "email": user.email,
        "department_id": st.department_id,
        "department_name": st.department.name if st.department else None,
        "admin_class": st.admin_class,
        "dob": st.dob,
        "gender": st.gender,
        "phone": st.phone,
        "status": st.status,
        "is_deleted": st.is_deleted,
        "user_is_active": user.is_active,
        "created_at": st.created_at,
    }
    return st_data, temp_password


def update_student(
    db: Session,
    student_id: int,
    data: StudentUpdate,
    admin_id: int | None = None,
    ip: str | None = None,
) -> dict:
    result = (
        db.query(Student, User)
        .join(User, Student.user_id == User.id)
        .filter(Student.id == student_id, Student.is_deleted == False)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Không tìm thấy sinh viên."},
        )
    st, usr = result
    changes: dict = {}

    if data.email is not None and data.email != usr.email:
        existing_email = db.query(User).filter(User.email == data.email, User.id != usr.id).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "EMAIL_EXISTS", "message": f"Email {data.email} đã được sử dụng."},
            )
        changes["email"] = {"old": usr.email, "new": data.email}
        usr.email = data.email
        st.email = data.email

    if data.is_active is not None and data.is_active != usr.is_active:
        changes["is_active"] = {"old": usr.is_active, "new": data.is_active}
        usr.is_active = data.is_active

    if data.full_name is not None and data.full_name != st.full_name:
        changes["full_name"] = {"old": st.full_name, "new": data.full_name}
        st.full_name = data.full_name
    if data.admin_class is not None and data.admin_class != st.admin_class:
        changes["admin_class"] = {"old": st.admin_class, "new": data.admin_class}
        st.admin_class = data.admin_class
    if data.department_id is not None and data.department_id != st.department_id:
        if not db.query(Department).filter(Department.id == data.department_id, Department.is_active == True).first():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "DEPARTMENT_NOT_FOUND", "message": "Khoa được chọn không tồn tại hoặc đã ngừng sử dụng."})
        changes["department_id"] = {"old": st.department_id, "new": data.department_id}
        st.department_id = data.department_id
    if data.dob is not None and data.dob != st.dob:
        changes["dob"] = {"old": str(st.dob), "new": str(data.dob)}
        st.dob = data.dob
    if data.gender is not None and data.gender != st.gender:
        changes["gender"] = {"old": st.gender, "new": data.gender}
        st.gender = data.gender
    if data.phone is not None and data.phone != st.phone:
        changes["phone"] = {"old": st.phone, "new": data.phone}
        st.phone = data.phone
    if data.status is not None and data.status != st.status:
        changes["status"] = {"old": str(st.status), "new": str(data.status)}
        st.status = data.status

    log_action(
        db=db,
        user_id=admin_id,
        action="UPDATE_STUDENT",
        entity="students",
        entity_id=str(st.id),
        detail={
            "student_code": st.student_code,
            "changes": changes,
            "summary": f"Cập nhật hồ sơ sinh viên {st.student_code} ({len(changes)} trường thay đổi)",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(st)
    db.refresh(usr)

    return {
        "id": st.id,
        "user_id": st.user_id,
        "student_code": st.student_code,
        "full_name": st.full_name,
        "email": usr.email,
        "department_id": st.department_id,
        "department_name": st.department.name if st.department else None,
        "admin_class": st.admin_class,
        "dob": st.dob,
        "gender": st.gender,
        "phone": st.phone,
        "status": st.status,
        "is_deleted": st.is_deleted,
        "user_is_active": usr.is_active,
        "created_at": st.created_at,
    }


def delete_student(
    db: Session,
    student_id: int,
    admin_id: int | None = None,
    ip: str | None = None,
):
    result = (
        db.query(Student, User)
        .join(User, Student.user_id == User.id)
        .filter(Student.id == student_id, Student.is_deleted == False)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Không tìm thấy sinh viên."},
        )
    st, usr = result
    st.is_deleted = True
    usr.is_deleted = True
    usr.is_active = False

    log_action(
        db=db,
        user_id=admin_id,
        action="DELETE_STUDENT",
        entity="students",
        entity_id=str(st.id),
        detail={
            "student_code": st.student_code,
            "full_name": st.full_name,
            "summary": f"Xóa mềm sinh viên {st.student_code} - {st.full_name}",
        },
        ip=ip,
    )
    db.commit()


def _import_department_error(code: str, department: Department | None) -> str | None:
    if not code:
        return "Thiếu mã khoa. Hãy nhập mã khoa trong danh mục Khoa."
    if department is None:
        return f"Mã khoa {code} không tồn tại trong danh mục Khoa."
    if not department.is_active:
        return f"Khoa {code} đã ngừng sử dụng."
    return None


def preview_import_students(db: Session, file_bytes: bytes) -> dict:
    parsed_valid, parsed_warnings, parsed_errors = parse_student_import_excel(file_bytes)

    valid_rows = []
    warning_rows = list(parsed_warnings)
    error_rows = list(parsed_errors)

    # Check DB uniqueness for student_code and email
    # Xác nhận bỏ qua cả hồ sơ đã xóa mềm, nên xem trước phải báo nhất quán.
    existing_codes = {code for (code,) in db.query(Student.student_code).all()}
    existing_usernames = {username.lower() for (username,) in db.query(User.username).all()}
    existing_emails = set(
        email for (email,) in db.query(User.email).filter(User.is_deleted == False).all() if email
    )
    departments = {department.code.strip().upper(): department for department in db.query(Department).all()}

    for row in parsed_valid:
        code = row["student_code"]
        email = row.get("email")
        department_code = (row.get("department_code") or "").strip().upper()
        department = departments.get(department_code)

        is_duplicate_code = code in existing_codes
        is_duplicate_email = email in existing_emails if email else False

        if is_duplicate_code:
            warning_rows.append({
                "row": row["row"],
                "student_code": code,
                "full_name": row["full_name"],
                "admin_class": row.get("admin_class"),
                "email": email,
                "reason": f"MSSV {code} đã tồn tại trong hệ thống (sẽ bỏ qua, KHÔNG đổi mật khẩu).",
            })
            continue

        if code.lower() in existing_usernames:
            error_rows.append({
                **row,
                "reason": "Tên đăng nhập theo MSSV đã được sử dụng. Hãy kiểm tra tài khoản hoặc sửa MSSV.",
            })
            continue

        department_error = _import_department_error(department_code, department)
        if department_error:
            error_rows.append({**row, "department_code": department_code, "reason": department_error})
            continue

        row["department_code"] = department.code
        row["department_name"] = department.name
        if is_duplicate_email:
            warning_rows.append({
                "row": row["row"],
                "student_code": code,
                "full_name": row["full_name"],
                "admin_class": row.get("admin_class"),
                "email": email,
                "reason": f"Email {email} đã được sử dụng bởi tài khoản khác (cảnh báo).",
            })
            valid_rows.append(row)
        else:
            valid_rows.append(row)

    total_rows = len({row["row"] for row in valid_rows + warning_rows + error_rows})
    return {
        "valid_rows": valid_rows,
        "warning_rows": warning_rows,
        "error_rows": error_rows,
        "total_rows": total_rows,
        "valid_count": len(valid_rows),
        "warning_count": len(warning_rows),
        "error_count": len(error_rows),
    }


def confirm_import_students(db: Session, valid_rows: list[dict], admin_id: int, ip: str | None = None) -> tuple[list[dict], bytes]:
    created_students = []
    skipped_count = 0

    try:
        # Không tin mã/id/tên khoa do client gửi: kiểm tra lại khi xác nhận.
        # Khóa các khoa liên quan để tránh bị ngừng sử dụng giữa lúc import.
        existing_codes = {code for (code,) in db.query(Student.student_code).all()}
        new_rows = [row for row in valid_rows if str(row.get("student_code", "")).strip() not in existing_codes]
        codes = {str(row.get("department_code") or "").strip().upper() for row in new_rows}
        departments = {
            department.code.strip().upper(): department
            for department in db.query(Department).filter(func.upper(Department.code).in_(codes)).with_for_update().all()
        }
        for row in new_rows:
            code = str(row.get("department_code") or "").strip().upper()
            error = _import_department_error(code, departments.get(code))
            if error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": "INVALID_DEPARTMENT", "message": f"Dòng {row.get('row', '?')}: {error}"},
                )

        for row in valid_rows:
            student_code = str(row["student_code"]).strip()
            username = student_code.lower()
            full_name = str(row["full_name"]).strip()
            admin_class = row.get("admin_class")
            dob_val = row.get("dob")
            gender = row.get("gender")
            phone = row.get("phone")
            email = row.get("email") or f"{username}@student.lms.edu.vn"

            # Check existing code or username in DB
            existing_st = db.query(Student).filter(Student.student_code == student_code).first()
            if existing_st:
                skipped_count += 1
                continue

            # Recheck at confirmation: another account may have been created
            # since preview. Include inactive/deleted accounts because the
            # username remains reserved by the database unique constraint.
            if db.query(User.id).filter(User.username == username).first() is not None:
                reason = "Tên đăng nhập theo MSSV đã được sử dụng. Hãy kiểm tra tài khoản hoặc sửa MSSV."
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "IMPORT_USERNAME_CONFLICT",
                        "message": f"Dòng {row.get('row', '?')}: {reason} Chưa nhập dữ liệu của lượt này.",
                        "details": {"rows": [{"row": row.get("row"), "student_code": student_code, "reason": reason}]},
                    },
                )

            temp_password = generate_temp_password(10)
            password_hash = get_password_hash(temp_password)

            # Ensure unique email for User model if duplicate
            user_email = email
            existing_user_email = db.query(User).filter(User.email == user_email).first()
            if existing_user_email:
                user_email = f"{username}@student.lms.edu.vn"
                if db.query(User).filter(User.email == user_email).first():
                    user_email = f"{username}_{int(datetime.now().timestamp())}@student.lms.edu.vn"

            user = User(
                username=username,
                email=user_email,
                password_hash=password_hash,
                role=UserRole.student,
                is_active=True,
                must_change_password=True,
                is_deleted=False,
            )
            db.add(user)
            db.flush()

            dob_date = None
            if dob_val:
                try:
                    if isinstance(dob_val, date):
                        dob_date = dob_val
                    else:
                        dob_date = datetime.strptime(str(dob_val)[:10], "%Y-%m-%d").date()
                except Exception:
                    dob_date = None

            st = Student(
                user_id=user.id,
                student_code=student_code,
                full_name=full_name,
                admin_class=admin_class,
                dob=dob_date,
                gender=gender,
                phone=phone,
                email=email,
                department_id=departments[str(row["department_code"]).strip().upper()].id,
                status=StudentStatus.studying,
                is_deleted=False,
            )
            db.add(st)

            created_students.append({
                "student_code": student_code,
                "full_name": full_name,
                "email": email,
                "temp_password": temp_password,
            })

        log_action(
            db=db,
            user_id=admin_id,
            action="IMPORT_STUDENTS",
            entity="students",
            entity_id=None,
            detail={
                "created": len(created_students),
                "skipped": skipped_count,
                "errors": 0,
                "summary": f"Import sinh viên: tạo {len(created_students)}, bỏ qua {skipped_count}, lỗi 0",
            },
            ip=ip,
        )
        # Build the one-time credential file before committing. If generation
        # fails, accounts and the success audit must roll back together.
        excel_bytes = generate_student_import_result_excel(created_students)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "IMPORT_CONFLICT",
                "message": "Dữ liệu bị trùng hoặc đã thay đổi khi nhập. Chưa nhập dữ liệu của lượt này; hãy xem trước lại và kiểm tra MSSV, tài khoản, email, mã khoa.",
            },
        ) from None
    except Exception as exc:
        db.rollback()
        reference = uuid4().hex
        # Do not log the exception text/traceback: SQLAlchemy exceptions may
        # contain SQL parameters, including generated password hashes.
        logger.error("Student import failed reference=%s exception_type=%s", reference, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "IMPORT_FAILED",
                "message": f"Không thể nhập dữ liệu. Chưa nhập dữ liệu của lượt này; hãy thử lại hoặc liên hệ quản trị viên với mã tra cứu {reference}.",
                "details": {"reference": reference},
            },
        ) from None

    return created_students, excel_bytes


def export_students_service(db: Session) -> bytes:
    students = (
        db.query(Student)
        .filter(Student.is_deleted == False)
        .order_by(Student.student_code.asc())
        .all()
    )
    return generate_student_export_excel(students)
