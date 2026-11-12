"""
app/seed_data.py
Seed dữ liệu mẫu — chạy lặp lại được, từ chối khi APP_ENV=production.
M3a: Thêm attendance_records đa dạng, leave_requests, backfill buổi open.
"""

from __future__ import annotations

import logging
import os
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.attendance import (  # noqa: E402
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
    LeaveRequest,
    LeaveRequestStatus,
)
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus  # noqa: E402
from app.models.learning import (  # noqa: E402
    Announcement,
    Assignment,
    AssignmentStatus,
    Group,
    GroupMember,
    Notification,
    Submission,
)
from app.models.lecturer import Lecturer, LecturerType  # noqa: E402
from app.models.schedule import Schedule  # noqa: E402
from app.models.semester import Semester  # noqa: E402
from app.models.session import Session as SessionModel  # noqa: E402
from app.models.session import SessionStatus
from app.models.student import Student, StudentStatus  # noqa: E402
from app.models.subject import Subject  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.utils.clock import now_local  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def get_or_create_user(db: Session, username: str, email: str, role: UserRole, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            role=role,
            is_active=True,
            must_change_password=False,
            is_deleted=False,
            token_version=1,
        )
        db.add(user)
        db.flush()
    # Do not reset an existing user's password/status on a repeated demo seed.
    # Seed is not an account recovery tool; admin resets require explicit action.
    return user


def _make_vn_dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t).replace(tzinfo=VN_TZ)


def _ensure_attendance_record(
    db: Session,
    session_id: int,
    student_id: int,
    att_status: AttendanceStatus,
    att_source: AttendanceSource,
    first_seen_at: datetime | None = None,
    note: str | None = None,
) -> AttendanceRecord:
    rec = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.student_id == student_id,
    ).first()
    if not rec:
        rec = AttendanceRecord(
            session_id=session_id,
            student_id=student_id,
            status=att_status,
            source=att_source,
            first_seen_at=first_seen_at,
            hit_count=1 if first_seen_at else 0,
            note=note,
        )
        db.add(rec)
    else:
        # Cập nhật nếu cần (seed lại)
        rec.status = att_status
        rec.source = att_source
        if first_seen_at:
            rec.first_seen_at = first_seen_at
        rec.note = note
    return rec


def seed_data() -> None:
    # Bảo vệ: từ chối chạy khi production
    if settings.APP_ENV == "production":
        print("❌ LỖI: Không được phép chạy script seed trong môi trường Production!")
        sys.exit(1)

    if "--rich-demo" in sys.argv and (
        settings.APP_ENV != "test" or not settings.DB_NAME.startswith("lms_rich_demo_")
    ):
        raise SystemExit("--rich-demo chỉ chạy trên database riêng qua scripts/demo_runtime.py.")

    db = SessionLocal()
    try:
        logger.info("Bắt đầu khởi tạo dữ liệu mẫu (Seed) M3a...")

        demo_password = "Demo@123"
        other_password = os.environ.get("DEV_SEED_PASSWORD", "DevPass@123")

        # ── 1. Admin ──────────────────────────────────────────────────────────
        _admin_user = get_or_create_user(db, "admin", "admin@lms.local", UserRole.admin, demo_password)
        db.flush()

        # ── 2. Học kỳ ─────────────────────────────────────────────────────────
        semester = db.query(Semester).filter(Semester.name == "Học kỳ 1 - 2026-2027").first()
        if not semester:
            semester = Semester(
                name="Học kỳ 1 - 2026-2027",
                start_date=now_local().date() - timedelta(days=90),
                end_date=now_local().date() + timedelta(days=90),
                is_current=True,
            )
            db.add(semester)
            db.flush()

        # ── 3. Môn học (6 môn, tên tiếng Việt đầy đủ dấu) ─────────────────────
        subjects_data = [
            ("IT101", "Nhập môn Lập trình", 3),
            ("IT102", "Cấu trúc Dữ liệu và Giải thuật", 3),
            ("IT103", "Cơ sở Dữ liệu", 3),
            ("IT104", "Mạng máy tính", 3),
            ("IT105", "Trí tuệ Nhân tạo", 3),
            ("IT106", "Kỹ nghệ Phần mềm", 3),
        ]
        for code, name, credits_val in subjects_data:
            if not db.query(Subject).filter(Subject.code == code).first():
                db.add(Subject(code=code, name=name, credits=credits_val))
        db.flush()

        # ── 4. Giảng viên (5: 3 cơ hữu, 2 thỉnh giảng) ────────────────────────
        lecturers_data = [
            ("GV001", "Nguyễn Văn An", LecturerType.full_time, "Tiến sĩ"),
            ("GV002", "Trần Thị Bình", LecturerType.full_time, "Tiến sĩ"),
            ("GV003", "Lê Văn Cường", LecturerType.full_time, "Thạc sĩ"),
            ("GV004", "Phạm Thị Dung", LecturerType.visiting, "Thạc sĩ"),
            ("GV005", "Hoàng Văn Em", LecturerType.visiting, "Tiến sĩ"),
        ]
        for code, name, l_type, degree in lecturers_data:
            pwd = demo_password if code == "GV001" else other_password
            user = get_or_create_user(db, code.lower(), f"{code.lower()}@lms.local", UserRole.lecturer, pwd)
            if not db.query(Lecturer).filter(Lecturer.code == code).first():
                db.add(Lecturer(
                    user_id=user.id,
                    code=code,
                    full_name=name,
                    phone=f"090000{code[-3:]}",
                    degree=degree,
                    department="Khoa Công nghệ Thông tin",
                    type=l_type,
                    is_deleted=False,
                ))
        db.flush()

        # ── 5. Sinh viên (60 sinh viên, tên đầy đủ tiếng Việt) ─────────────────
        first_names = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Hồ"]
        middle_names = ["Văn", "Thị", "Đức", "Minh", "Quang", "Thành", "Hữu", "Ngọc", "Bảo", "Kim"]
        last_names = [
            "An", "Bình", "Cường", "Dũng", "Em", "Phong", "Giang", "Hà", "Inh", "Khoa",
            "Lâm", "Minh", "Nam", "Oanh", "Phúc", "Quân", "Rồng", "Sơn", "Tâm", "Uyên",
        ]
        for i in range(1, 61):
            code = f"SV{i:03d}"
            pwd = demo_password if i == 1 else other_password
            user = get_or_create_user(db, code.lower(), f"{code.lower()}@lms.local", UserRole.student, pwd)
            if not db.query(Student).filter(Student.student_code == code).first():
                fn = first_names[i % len(first_names)]
                mn = middle_names[(i * 3) % len(middle_names)]
                ln = last_names[(i * 7) % len(last_names)]
                db.add(Student(
                    user_id=user.id,
                    student_code=code,
                    full_name=f"{fn} {mn} {ln}",
                    admin_class=f"K6{5 + (i % 3)}-CNTT",
                    status=StudentStatus.studying,
                    is_deleted=False,
                ))
        db.flush()

        # ── 6. Lớp học, lịch, buổi học ─────────────────────────────────────────
        subjects = db.query(Subject).all()
        lecturers = db.query(Lecturer).all()
        students = db.query(Student).all()

        if db.query(Class).count() == 0:
            _seed_classes(db, semester, subjects, lecturers, students)
            db.flush()

        # ── 7. M3a: Backfill attendance cho buổi open có sẵn ───────────────────
        _backfill_open_sessions(db)

        # ── 8. M3a: Seed attendance đa dạng cho buổi closed ─────────────────────
        _seed_closed_attendance(db)

        # ── 9. M3a: Seed đơn xin vắng ────────────────────────────────────────────
        _seed_leave_requests(db)

        # ── 10. M5: bài tập, bài nộp, nhóm và thông báo ───────────────────────
        _seed_learning(db)

        _seed_materials(db)
        _seed_exams(db)
        _seed_gradebook(db)

        if "--rich-demo" in sys.argv:
            from app.services.demo_seed_service import seed_rich_demo

            seed_rich_demo(db, demo_password)

        db.commit()
        logger.info("✅ Seed M5 hoàn thành!")

        _print_accounts(demo_password)

    finally:
        db.close()


def _seed_classes(db: Session, semester: Semester, subjects, lecturers, students) -> None:
    """Tạo lớp học, lịch và buổi học."""
    today = now_local().date()

    classes_config = [
        # (code, subject_idx, lecturer_idx, weekday, start_time, end_time, room, stu_start, stu_end)
        ("IT101-01", 0, 0, 1, time(8, 0), time(10, 0), "A101", 0, 30),   # Thứ 3 (0=Mon)
        ("IT102-01", 1, 1, 3, time(13, 0), time(15, 0), "B202", 15, 45), # Thứ 5
        ("IT103-01", 2, 2, 2, time(8, 0), time(11, 0), "C301", 30, 60),  # Thứ 4
        ("IT104-01", 3, 0, 4, time(13, 0), time(16, 0), "D404", 0, 25),  # Thứ 6
    ]

    for code, sub_idx, lec_idx, weekday, start_t, end_t, room, stu_s, stu_e in classes_config:
        cls = Class(
            code=code,
            subject_id=subjects[sub_idx].id,
            semester_id=semester.id,
            lecturer_id=lecturers[lec_idx].id,
            max_students=50,
            status=ClassStatus.active,
            late_after_min=10,
            absent_after_min=30,
            weight_present=1.0,
            weight_late=0.5,
            weight_excused=1.0,
            attendance_warning_absences=3,
            is_deleted=False,
        )
        db.add(cls)
        db.flush()

        # Ghi danh sinh viên
        class_students = students[stu_s:stu_e]
        for stu in class_students:
            db.add(ClassStudent(
                class_id=cls.id,
                student_id=stu.id,
                status=ClassStudentStatus.enrolled,
            ))

        # Tạo lịch và buổi học
        sch = Schedule(
            class_id=cls.id,
            weekday=weekday,
            start_time=start_t,
            end_time=end_t,
            room=room,
            start_date=semester.start_date,
            end_date=semester.end_date,
        )
        db.add(sch)
        db.flush()

        # Tìm ngày đầu tiên khớp weekday kể từ semester.start_date
        current_date = semester.start_date
        days_ahead = (weekday - current_date.weekday()) % 7
        current_date += timedelta(days=days_ahead)

        session_no = 1
        while current_date <= semester.end_date:
            if current_date < today:
                sess_status = SessionStatus.closed
                opened_at = _make_vn_dt(current_date, start_t)
                closed_at = _make_vn_dt(current_date, end_t)
            elif current_date == today:
                sess_status = SessionStatus.open
                opened_at = _make_vn_dt(current_date, start_t)
                closed_at = None
            else:
                sess_status = SessionStatus.scheduled
                opened_at = None
                closed_at = None

            sess = SessionModel(
                class_id=cls.id,
                schedule_id=sch.id,
                session_no=session_no,
                date=current_date,
                start_time=start_t,
                end_time=end_t,
                room=room,
                status=sess_status,
                opened_at=opened_at,
                closed_at=closed_at,
            )
            db.add(sess)
            session_no += 1
            current_date += timedelta(days=7)

        db.flush()


def _backfill_open_sessions(db: Session) -> None:
    """Backfill bản ghi điểm danh cho các buổi open có sẵn (idempotent)."""
    from app.services.attendance_service import ensure_records

    open_sessions = db.query(SessionModel).filter(
        SessionModel.status == SessionStatus.open
    ).all()

    for sess in open_sessions:
        created = ensure_records(db, sess)
        if created:
            logger.info("Backfill %d bản ghi cho buổi %d (class %d)", created, sess.id, sess.class_id)
    db.flush()


def _seed_closed_attendance(db: Session) -> None:
    """
    Tạo attendance_records đa dạng cho các buổi closed.
    Kịch bản:
    - Hầu hết SV: hiện diện
    - SV vắng nhiều (>= 3): trigger cảnh báo
    - 1 SV không có buổi closed nào (ghi danh giữa kỳ)
    - 1 SV ghi danh giữa kỳ (chỉ có bản ghi từ buổi thứ 4 trở đi)
    """
    random.seed(42)  # Đảm bảo lặp lại được

    classes = db.query(Class).filter(
        Class.status == ClassStatus.active,
        Class.is_deleted == False,
    ).all()

    for cls in classes:
        closed_sessions = db.query(SessionModel).filter(
            SessionModel.class_id == cls.id,
            SessionModel.status == SessionStatus.closed,
        ).order_by(SessionModel.date.asc()).all()

        if not closed_sessions:
            continue

        enrolled_students = db.query(ClassStudent).filter(
            ClassStudent.class_id == cls.id,
        ).all()

        if len(enrolled_students) < 3:
            continue

        # Xác định SV đặc biệt (theo index)
        # SV cuối: ghi danh giữa kỳ (chỉ tính từ buổi thứ 4)
        late_enroll_idx = len(enrolled_students) - 1
        # SV áp chót: vắng nhiều (>= 3 buổi)
        absent_heavy_idx = len(enrolled_students) - 2
        # SV trước nữa: không có bất kỳ buổi closed (thực ra sẽ không tạo bản ghi)
        no_record_idx = len(enrolled_students) - 3

        for sess_no, sess in enumerate(closed_sessions):
            for stu_idx, cs in enumerate(enrolled_students):
                student_id = cs.student_id

                # SV không có bản ghi nào (mô phỏng ghi danh sau tất cả buổi closed)
                if stu_idx == no_record_idx:
                    continue

                # SV ghi danh giữa kỳ: chỉ từ buổi thứ 4
                if stu_idx == late_enroll_idx and sess_no < 3:
                    continue

                # Kiểm tra đã có bản ghi chưa
                existing = db.query(AttendanceRecord).filter(
                    AttendanceRecord.session_id == sess.id,
                    AttendanceRecord.student_id == student_id,
                ).first()
                if existing:
                    continue

                # Xác định trạng thái
                if stu_idx == absent_heavy_idx:
                    # SV vắng nhiều: absent ở hầu hết buổi
                    att_status = AttendanceStatus.absent if sess_no < 5 else AttendanceStatus.present
                    att_source = AttendanceSource.system
                    first_seen = None
                else:
                    # Random đa dạng
                    roll = random.random()
                    if roll < 0.70:
                        att_status = AttendanceStatus.present
                        att_source = AttendanceSource.manual
                        first_seen = datetime(
                            sess.date.year, sess.date.month, sess.date.day,
                            sess.start_time.hour, sess.start_time.minute,
                            tzinfo=VN_TZ,
                        ) + timedelta(minutes=random.randint(0, 8))
                    elif roll < 0.80:
                        att_status = AttendanceStatus.late
                        att_source = AttendanceSource.manual
                        first_seen = datetime(
                            sess.date.year, sess.date.month, sess.date.day,
                            sess.start_time.hour, sess.start_time.minute,
                            tzinfo=VN_TZ,
                        ) + timedelta(minutes=random.randint(11, 25))
                    elif roll < 0.90:
                        att_status = AttendanceStatus.absent
                        att_source = AttendanceSource.system
                        first_seen = None
                    else:
                        att_status = AttendanceStatus.excused
                        att_source = AttendanceSource.leave
                        first_seen = None

                _ensure_attendance_record(
                    db, sess.id, student_id,
                    att_status, att_source, first_seen,
                )

    db.flush()
    logger.info("✅ Seed attendance cho buổi closed hoàn thành.")


def _seed_leave_requests(db: Session) -> None:
    """Seed đơn xin vắng ở 3 trạng thái: pending, approved, rejected."""
    classes = db.query(Class).filter(
        Class.status == ClassStatus.active,
        Class.is_deleted == False,
    ).all()

    for cls in classes:
        enrolled = db.query(ClassStudent).filter(
            ClassStudent.class_id == cls.id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        ).limit(5).all()

        if not enrolled:
            continue

        # Lấy vài buổi scheduled hoặc closed trong 7 ngày
        today = now_local().date()
        recent_sessions = db.query(SessionModel).filter(
            SessionModel.class_id == cls.id,
            SessionModel.status.in_([SessionStatus.scheduled, SessionStatus.closed, SessionStatus.open]),
            SessionModel.date >= today - timedelta(days=7),
        ).limit(5).all()

        if not recent_sessions:
            continue

        # Reviewer là admin
        admin = db.query(User).filter(User.role == UserRole.admin).first()

        for i, (cs, sess) in enumerate(zip(enrolled[:3], recent_sessions[:3], strict=False)):
            student_id = cs.student_id

            # Kiểm tra đã có đơn pending chưa
            existing = db.query(LeaveRequest).filter(
                LeaveRequest.student_id == student_id,
                LeaveRequest.session_id == sess.id,
            ).first()
            if existing:
                continue

            reasons = [
                "Tôi bị ốm nặng, có giấy xác nhận của bác sĩ.",
                "Gia đình có việc đột xuất không thể tham dự.",
                "Tôi phải tham dự sự kiện sinh viên toàn trường.",
            ]
            statuses_map = [
                (LeaveRequestStatus.pending, None, None),
                (LeaveRequestStatus.approved, admin.id if admin else None, "Đồng ý, nghỉ có phép."),
                (LeaveRequestStatus.rejected, admin.id if admin else None, "Lý do chưa đủ thuyết phục."),
            ]

            lr_status, reviewed_by, review_note = statuses_map[i % 3]
            reviewed_at = now_local() if reviewed_by else None

            lr = LeaveRequest(
                student_id=student_id,
                session_id=sess.id,
                reason=reasons[i % 3],
                status=lr_status,
                reviewed_by=reviewed_by,
                reviewed_at=reviewed_at,
                review_note=review_note,
            )
            db.add(lr)

    db.flush()
    logger.info("✅ Seed leave_requests hoàn thành.")


def _seed_learning(db: Session) -> None:
    """Dữ liệu demo M5 chạy lặp lại được, chỉ phát sinh từ seed."""
    cls = db.query(Class).filter(
        Class.status == ClassStatus.active,
        Class.is_deleted == False,
    ).order_by(Class.id.asc()).first()
    if not cls or not cls.lecturer_id:
        return
    lecturer = db.get(Lecturer, cls.lecturer_id)
    if not lecturer:
        return

    now = now_local()
    specs = [
        ("Bài tập khởi động", "Nộp phần trả lời ngắn về nội dung đã học.", now + timedelta(days=7), False),
        ("Bài tập thực hành", "Hoàn thành phần thực hành và nộp kết quả.", now - timedelta(days=1), True),
    ]
    assignments = []
    for title, description, due_at, is_past in specs:
        assignment = db.query(Assignment).filter(
            Assignment.class_id == cls.id,
            Assignment.title == title,
        ).first()
        if not assignment:
            assignment = Assignment(
                class_id=cls.id,
                title=title,
                description=description,
                due_at=due_at.astimezone(UTC).replace(tzinfo=None),
                max_score=10,
                allow_late=True,
                status=AssignmentStatus.published,
            )
            db.add(assignment)
            db.flush()
        assignments.append((assignment, is_past))

    students = [
        student for student in db.query(Student)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .filter(
            ClassStudent.class_id == cls.id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
        .order_by(Student.id.asc()).limit(12).all()
    ]
    for index, (assignment, is_late) in enumerate(assignments):
        if not students:
            break
        student = students[min(index, len(students) - 1)]
        exists = db.query(Submission).filter(
            Submission.assignment_id == assignment.id,
            Submission.student_id == student.id,
        ).first()
        if not exists:
            score = None if is_late else 8.5
            db.add(Submission(
                assignment_id=assignment.id,
                student_id=student.id,
                text="Bài nộp mẫu được tạo bởi scripts/seed.py.",
                submitted_at=assignment.due_at + timedelta(hours=1) if is_late else now,
                is_late=is_late,
                score=score,
                feedback=None if is_late else "Hoàn thành đúng yêu cầu.",
                graded_by=None if is_late else lecturer.user_id,
                graded_at=None if is_late else now,
            ))

    if not db.query(Group).filter(Group.class_id == cls.id).first():
        groups = [Group(class_id=cls.id, name=f"Nhóm {index}") for index in range(1, 4)]
        db.add_all(groups)
        db.flush()
        for index, student in enumerate(students[:9]):
            db.add(GroupMember(group_id=groups[index % len(groups)].id, student_id=student.id))

    if not db.query(Announcement).filter(
        Announcement.class_id == cls.id,
        Announcement.title == "Chào mừng lớp học phần",
    ).first():
        db.add(Announcement(
            class_id=cls.id,
            author_id=lecturer.user_id,
            title="Chào mừng lớp học phần",
            content="Vui lòng kiểm tra lịch học và bài tập trước buổi học tiếp theo.",
            is_pinned=True,
        ))
    for student in students[:3]:
        exists = db.query(Notification).filter(
            Notification.user_id == student.user_id,
            Notification.type == "seed_welcome_m5",
        ).first()
        if not exists:
            db.add(Notification(
                user_id=student.user_id,
                type="seed_welcome_m5",
                title="Có bài tập mới",
                body="Bài tập khởi động đã được giao.",
                link=f"/student/classes/{cls.id}",
            ))
    db.flush()


def _seed_materials(db: Session) -> None:
    from app.models.material import Material
    from app.utils.uploads import store_upload

    cls = db.query(Class).filter(Class.is_deleted == False).order_by(Class.id).first()
    if not cls or not cls.lecturer_id:
        return
    lecturer = db.get(Lecturer, cls.lecturer_id)
    samples = [("Tài liệu hướng dẫn học tập", None),
               ("Tài liệu tham khảo Python", "https://docs.python.org/3/tutorial/")]
    for title, url in samples:
        if db.query(Material).filter(Material.class_id == cls.id, Material.title == title).first():
            continue
        path = None if url else store_upload("materials", cls.id, ".txt",
            "Tài liệu mẫu từ scripts/seed.py. Đọc yêu cầu bài tập và lịch học của lớp.".encode())
        db.add(Material(class_id=cls.id, author_id=lecturer.user_id, title=title,
                        description="Học liệu demo được tạo bởi scripts/seed.py.", url=url,
                        file_path=str(path) if path else None,
                        filename="huong-dan-hoc-tap.txt" if path else None))
    db.flush()


def _seed_exams(db: Session) -> None:
    from app.models.exam import Exam
    from app.models.question import Question
    from app.schemas.exam import ExamDraftIn
    from app.schemas.question import QuestionIn
    from app.services.exam_draft_service import create_draft
    from app.services.exam_lifecycle_service import publish_exam
    from app.services.question_service import create_questions

    cls = db.query(Class).filter(Class.is_deleted == False).order_by(Class.id).first()
    if not cls or not cls.lecturer_id:
        return
    user = db.get(User, db.get(Lecturer, cls.lecturer_id).user_id)
    question_ids = []
    samples = [
        ("single", "[M6 demo] HTTP dùng để làm gì?", [("Trao đổi dữ liệu web", True), ("Lưu mật khẩu rõ", False)]),
        ("multiple", "[M6 demo] Chọn các biện pháp bảo vệ tài khoản.", [("Mật khẩu mạnh", True), ("Bật xác thực bổ sung", True), ("Chia sẻ mật khẩu", False)]),
        ("true_false", "[M6 demo] Kiểm tra quyền phải thực hiện phía máy chủ.", [("Đúng", True), ("Sai", False)]),
        ("essay", "[M6 demo] Giải thích vì sao cần đóng băng nội dung đề đã công bố.", []),
    ]
    for kind, content, options in samples:
        question = db.query(Question).filter_by(subject_id=cls.subject_id, content=content).first()
        if not question:
            question = create_questions(db, user, cls.subject_id, [QuestionIn(type=kind, content=content,
                explanation="Câu hỏi demo được tạo bởi scripts/seed.py.",
                options=[{"content": text, "is_correct": correct} for text, correct in options])])[0]
        question_ids.append(question.id)
    title = "Kiểm tra trực tuyến mẫu · 4 dạng câu hỏi"
    if not db.query(Exam).filter_by(class_id=cls.id, title=title).first():
        now = now_local()
        data = ExamDraftIn(title=title, description="Đề demo từ scripts/seed.py. Câu tự luận cần giảng viên chấm.",
            duration_min=30, open_at=now - timedelta(hours=1), close_at=now + timedelta(days=7),
            shuffle_questions=False, shuffle_options=False, max_attempts=2, score_policy="highest",
            show_result="after_submit", require_fullscreen=False, record_events=True,
            violation_types=["tab_hidden"], max_violations=0, auto_submit_on_violation=False,
            questions=[{"question_id": qid, "points": "2.5"} for qid in question_ids])
        exam = create_draft(db, user, cls.id, data)
        publish_exam(db, user, exam.id)


def _seed_gradebook(db: Session) -> None:
    from app.models.exam import Exam
    from app.models.grade import GradeComponent

    cls = db.query(Class).filter(Class.is_deleted == False).order_by(Class.id).first()
    if not cls or db.query(GradeComponent).filter_by(class_id=cls.id).first():
        return
    assignment = db.query(Assignment).filter_by(class_id=cls.id, status=AssignmentStatus.published).order_by(Assignment.id).first()
    exam = db.query(Exam).filter_by(class_id=cls.id).order_by(Exam.id).first()
    if not assignment or not exam:
        return
    db.add_all([
        GradeComponent(class_id=cls.id, name="Chuyên cần", type="attendance", weight=10, ref_id=None),
        GradeComponent(class_id=cls.id, name="Bài tập", type="assignment", weight=30, ref_id=assignment.id),
        GradeComponent(class_id=cls.id, name="Kiểm tra", type="exam", weight=60, ref_id=exam.id),
        GradeComponent(class_id=cls.id, name="Điểm bổ sung", type="manual", weight=0, ref_id=None),
    ])
    db.flush()


def _print_accounts(demo_password: str) -> None:
    print("=" * 60)
    print("  THÔNG TIN TÀI KHOẢN MẪU ĐĂNG NHẬP HỆ THỐNG")
    print("=" * 60)
    print("  1. Quản trị viên (Admin)")
    print("     Username: admin")
    print(f"     Password: {demo_password}")
    print("  " + "-" * 56)
    print("  2. Giảng viên mẫu (Lecturer)")
    print("     Username: gv001")
    print(f"     Password: {demo_password}")
    print("  " + "-" * 56)
    print("  3. Sinh viên mẫu (Student)")
    print("     Username: sv001")
    print(f"     Password: {demo_password}")
    print("=" * 60)


if __name__ == "__main__":
    seed_data()
