"""
enrollment_service.py
Ghi danh sinh viên vào lớp, rút, import từ Excel.

Kiểm tra sức chứa dùng SELECT ... FOR UPDATE trên bản ghi lớp
để tránh race condition khi hai request thêm cùng lúc.
"""

from __future__ import annotations

import io

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.student import Student, StudentStatus
from app.schemas.class_ import ClassStudentListResponse, ClassStudentOut
from app.services.audit_service import log_action
from app.services.conflict_service import check_conflicts_for_enrollment


def _get_class_with_lock(db: Session, class_id: int) -> Class:
    """
    SELECT ... FOR UPDATE trên bản ghi lớp để tránh race condition khi kiểm tra sức chứa.
    """
    cls = (
        db.query(Class)
        .filter(Class.id == class_id, Class.is_deleted == False)
        .with_for_update()
        .first()
    )
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học."},
        )
    return cls


def _get_enrolled_count(db: Session, class_id: int) -> int:
    return (
        db.query(func.count(ClassStudent.id))
        .filter(ClassStudent.class_id == class_id, ClassStudent.status == ClassStudentStatus.enrolled)
        .scalar()
        or 0
    )


def _get_enrollable_student(db: Session, student_id: int) -> Student:
    """Trả về sinh viên còn hiệu lực và đang học để ghi danh."""
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.is_deleted == False)
        .first()
    )
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": f"Không tìm thấy sinh viên id={student_id}."},
        )
    if student.status != StudentStatus.studying:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "STUDENT_NOT_STUDYING",
                "message": f"Sinh viên {student.student_code} không ở trạng thái đang học.",
            },
        )
    return student


def _raise_schedule_conflict(conflict_map: dict) -> None:
    """Chuẩn hóa phản hồi xung đột lịch cho ghi danh thủ công và import."""
    if not conflict_map:
        return

    all_conflicts = []
    for student_id, conflicts in conflict_map.items():
        for conflict in conflicts:
            all_conflicts.append({
                "student_id": student_id,
                "conflict_type": conflict.conflict_type,
                "class_id": conflict.class_id,
                "class_code": conflict.class_code,
                "date": str(conflict.date),
                "start_time": str(conflict.start_time),
                "end_time": str(conflict.end_time),
                "message": conflict.message,
            })
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "SCHEDULE_CONFLICT",
            "message": "Một số sinh viên có lịch học trùng với lớp này.",
            "details": {"conflicts": all_conflicts},
        },
    )


def get_class_students(
    db: Session,
    class_id: int,
    page: int = 1,
    page_size: int = 50,
    status_filter: ClassStudentStatus | None = None,
    q: str | None = None,
) -> ClassStudentListResponse:
    from app.models.class_ import Class
    if not db.query(Class).filter(Class.id == class_id, Class.is_deleted == False).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học."},
        )

    query = (
        db.query(ClassStudent, Student)
        .join(Student, ClassStudent.student_id == Student.id)
        .filter(ClassStudent.class_id == class_id)
    )
    if status_filter:
        query = query.filter(ClassStudent.status == status_filter)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (Student.student_code.ilike(pattern)) | (Student.full_name.ilike(pattern))
        )

    total = query.count()
    rows = (
        query.order_by(Student.student_code.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        ClassStudentOut(
            id=cs.id,
            student_id=cs.student_id,
            student_code=st.student_code,
            full_name=st.full_name,
            status=cs.status.value,
            enrolled_at=cs.created_at,
        )
        for cs, st in rows
    ]
    return ClassStudentListResponse(items=items, total=total, page=page, page_size=page_size)


def enroll_students(
    db: Session,
    class_id: int,
    student_ids: list[int],
    actor_id: int,
    ip: str | None = None,
) -> list[ClassStudentOut]:
    """
    Thêm một hoặc nhiều sinh viên vào lớp.
    Dùng FOR UPDATE để đảm bảo không vượt max_students khi đồng thời.
    """
    cls = _get_class_with_lock(db, class_id)
    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng."},
        )

    results = []
    newly_enrolled: list[int] = []

    for student_id in student_ids:
        student = _get_enrollable_student(db, student_id)

        # Tìm bản ghi ghi danh hiện có
        existing = (
            db.query(ClassStudent)
            .filter(ClassStudent.class_id == class_id, ClassStudent.student_id == student_id)
            .first()
        )

        if existing and existing.status == ClassStudentStatus.enrolled:
            # Đã ghi danh rồi — bỏ qua
            results.append(ClassStudentOut(
                id=existing.id,
                student_id=student.id,
                student_code=student.student_code,
                full_name=student.full_name,
                status=existing.status.value,
                enrolled_at=existing.created_at,
            ))
            continue

        # Kiểm tra sức chứa (đọc lại trong cùng giao dịch có lock)
        current_count = _get_enrolled_count(db, class_id)
        if current_count >= cls.max_students:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "CLASS_FULL",
                    "message": f"Lớp đã đủ {cls.max_students} sinh viên.",
                },
            )

        if existing and existing.status == ClassStudentStatus.dropped:
            # Kích hoạt lại
            existing.status = ClassStudentStatus.enrolled
            db.flush()
            newly_enrolled.append(student_id)
            results.append(ClassStudentOut(
                id=existing.id,
                student_id=student.id,
                student_code=student.student_code,
                full_name=student.full_name,
                status=ClassStudentStatus.enrolled.value,
                enrolled_at=existing.created_at,
            ))
        else:
            # Tạo mới
            cs = ClassStudent(
                class_id=class_id,
                student_id=student_id,
                status=ClassStudentStatus.enrolled,
            )
            db.add(cs)
            db.flush()
            newly_enrolled.append(student_id)
            results.append(ClassStudentOut(
                id=cs.id,
                student_id=student.id,
                student_code=student.student_code,
                full_name=student.full_name,
                status=ClassStudentStatus.enrolled.value,
                enrolled_at=cs.created_at,
            ))

    # Kiểm tra xung đột lịch cho sinh viên mới thêm
    if newly_enrolled:
        conflict_map = check_conflicts_for_enrollment(db, class_id=class_id, student_ids=newly_enrolled)
        _raise_schedule_conflict(conflict_map)

    if newly_enrolled:
        log_action(
            db=db,
            user_id=actor_id,
            action="ENROLL_STUDENTS",
            entity="class_students",
            entity_id=str(class_id),
            detail={
                "class_id": class_id,
                "class_code": cls.code,
                "student_ids": newly_enrolled,
                "count": len(newly_enrolled),
            },
            ip=ip,
        )
    db.commit()
    return results


def drop_student(
    db: Session,
    class_id: int,
    student_id: int,
    actor_id: int,
    ip: str | None = None,
) -> None:
    cls = _get_class_with_lock(db, class_id)
    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng."},
        )

    cs = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == class_id,
            ClassStudent.student_id == student_id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
        .first()
    )
    if not cs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ENROLLMENT_NOT_FOUND", "message": "Sinh viên không thuộc lớp này hoặc đã bị rút."},
        )

    student = db.query(Student).filter(Student.id == student_id).first()
    cs.status = ClassStudentStatus.dropped

    log_action(
        db=db,
        user_id=actor_id,
        action="DROP_STUDENT",
        entity="class_students",
        entity_id=str(class_id),
        detail={
            "class_id": class_id,
            "class_code": cls.code,
            "student_id": student_id,
            "student_code": student.student_code if student else None,
        },
        ip=ip,
    )
    db.commit()


# ----------------------------------------------------------------- Import Excel
def preview_import_enrollment(
    db: Session,
    class_id: int,
    file_bytes: bytes,
) -> dict:
    """
    Đọc file Excel có cột 'mssv' hoặc 'student_code'.
    Trả bản xem trước: hợp lệ, cảnh báo, lỗi.
    Xung đột lịch của từng sinh viên được đưa vào dòng lỗi.
    """
    from app.models.class_ import Class
    cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted == False).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học."},
        )

    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE", "message": f"Không thể đọc file Excel: {e}"},
        ) from e

    # Tìm cột mã số sinh viên
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE", "message": "File Excel trống hoặc không có dòng tiêu đề."},
        )

    header = [str(h).strip().lower() if h else "" for h in header_row]
    accepted_headers = {"mssv", "student_code"}
    if not accepted_headers.intersection(header):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE", "message": "File Excel phải có cột 'mssv' hoặc 'student_code'."},
        )
    student_code_col = header.index("mssv") if "mssv" in header else header.index("student_code")

    valid_rows: list[dict] = []
    warning_rows: list[dict] = []
    error_rows: list[dict] = []

    # Lấy danh sách sinh viên đã enrolled
    already_enrolled = set(
        r[0] for r in db.query(ClassStudent.student_id)
        .filter(ClassStudent.class_id == class_id, ClassStudent.status == ClassStudentStatus.enrolled)
        .all()
    )

    # Đọc từng dòng
    candidate_ids: list[int] = []
    seen_student_ids: set[int] = set()
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        mssv_raw = row[student_code_col] if len(row) > student_code_col else None
        if mssv_raw is None or not str(mssv_raw).strip():
            error_rows.append({"row": row_idx, "student_code": None, "reason": "Ô MSSV trống."})
            continue
        mssv = str(mssv_raw).strip()

        student = db.query(Student).filter(Student.student_code == mssv, Student.is_deleted == False).first()
        if not student:
            error_rows.append({"row": row_idx, "student_code": mssv, "reason": f"MSSV {mssv} không tồn tại trong hệ thống."})
            continue
        if student.status != StudentStatus.studying:
            error_rows.append({
                "row": row_idx,
                "student_code": mssv,
                "full_name": student.full_name,
                "reason": f"Sinh viên {mssv} không ở trạng thái đang học.",
            })
            continue
        if student.id in already_enrolled:
            warning_rows.append({
                "row": row_idx,
                "student_code": mssv,
                "full_name": student.full_name,
                "student_id": student.id,
                "reason": f"Sinh viên {mssv} đã ghi danh vào lớp này (sẽ bỏ qua).",
            })
            continue
        if student.id in seen_student_ids:
            warning_rows.append({
                "row": row_idx,
                "student_code": mssv,
                "full_name": student.full_name,
                "student_id": student.id,
                "reason": f"MSSV {mssv} lặp lại trong file (sẽ bỏ qua).",
            })
            continue

        valid_rows.append({
            "row": row_idx,
            "student_code": mssv,
            "full_name": student.full_name,
            "student_id": student.id,
        })
        candidate_ids.append(student.id)
        seen_student_ids.add(student.id)

    # Kiểm tra xung đột lịch cho các sinh viên hợp lệ
    if candidate_ids:
        conflict_map = check_conflicts_for_enrollment(db, class_id=class_id, student_ids=candidate_ids)
        still_valid = []
        for row in valid_rows:
            sid = row["student_id"]
            if sid in conflict_map:
                conflict_msgs = "; ".join(c.message for c in conflict_map[sid])
                error_rows.append({
                    "row": row["row"],
                    "student_code": row["student_code"],
                    "full_name": row["full_name"],
                    "student_id": sid,
                    "reason": f"Xung đột lịch: {conflict_msgs}",
                })
            else:
                still_valid.append(row)
        valid_rows = still_valid

    # Preview phải phản ánh sức chứa hiện tại để người dùng không nhận kết quả
    # "hợp lệ" rồi mới thất bại toàn bộ ở bước xác nhận.
    available_slots = max(cls.max_students - len(already_enrolled), 0)
    if len(valid_rows) > available_slots:
        over_capacity_rows = valid_rows[available_slots:]
        valid_rows = valid_rows[:available_slots]
        for row in over_capacity_rows:
            error_rows.append({
                **row,
                "reason": "Lớp đã đủ sĩ số hoặc không còn chỗ trống.",
            })

    return {
        "valid_rows": valid_rows,
        "warning_rows": warning_rows,
        "error_rows": error_rows,
        "total_rows": len(valid_rows) + len(warning_rows) + len(error_rows),
        "valid_count": len(valid_rows),
        "warning_count": len(warning_rows),
        "error_count": len(error_rows),
    }


def confirm_import_enrollment(
    db: Session,
    class_id: int,
    valid_rows: list[dict],
    actor_id: int,
    ip: str | None = None,
) -> dict:
    """
    Xác nhận import: ghi danh tất cả sinh viên trong valid_rows.
    Dùng lock để kiểm tra sức chứa.
    """
    cls = _get_class_with_lock(db, class_id)
    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng."},
        )

    # valid_rows là dữ liệu quay lại từ client, chỉ dùng student_id làm tham chiếu
    # và kiểm tra lại toàn bộ điều kiện nghiệp vụ trong transaction có khóa lớp.
    requested_ids: list[int] = []
    seen_ids: set[int] = set()
    for row in valid_rows:
        student_id = row.get("student_id")
        if not isinstance(student_id, int) or isinstance(student_id, bool) or student_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_IMPORT_ROW", "message": "Dòng import không có student_id hợp lệ."},
            )
        if student_id not in seen_ids:
            requested_ids.append(student_id)
            seen_ids.add(student_id)

    enrollments_to_activate: list[ClassStudent] = []
    enrollments_to_create: list[tuple[int, Student]] = []
    skipped = len(valid_rows) - len(requested_ids)
    student_ids_to_enroll: list[int] = []

    for student_id in requested_ids:
        student = _get_enrollable_student(db, student_id)
        existing = (
            db.query(ClassStudent)
            .filter(ClassStudent.class_id == class_id, ClassStudent.student_id == student_id)
            .first()
        )
        if existing and existing.status == ClassStudentStatus.enrolled:
            skipped += 1
        elif existing:
            enrollments_to_activate.append(existing)
            student_ids_to_enroll.append(student.id)
        else:
            enrollments_to_create.append((student.id, student))
            student_ids_to_enroll.append(student.id)

    current_count = _get_enrolled_count(db, class_id)
    if current_count + len(student_ids_to_enroll) > cls.max_students:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_FULL", "message": f"Lớp chỉ còn {cls.max_students - current_count} chỗ trống."},
        )

    conflict_map = check_conflicts_for_enrollment(
        db, class_id=class_id, student_ids=student_ids_to_enroll
    )
    _raise_schedule_conflict(conflict_map)

    for enrollment in enrollments_to_activate:
        enrollment.status = ClassStudentStatus.enrolled
    for student_id, _student in enrollments_to_create:
        db.add(ClassStudent(
            class_id=class_id,
            student_id=student_id,
            status=ClassStudentStatus.enrolled,
        ))
    if student_ids_to_enroll:
        db.flush()

    created = len(student_ids_to_enroll)

    log_action(
        db=db,
        user_id=actor_id,
        action="IMPORT_ENROLLMENT",
        entity="class_students",
        entity_id=str(class_id),
        detail={
            "class_id": class_id,
            "class_code": cls.code,
            "created": created,
            "skipped": skipped,
        },
        ip=ip,
    )
    db.commit()
    return {"created": created, "skipped": skipped}
