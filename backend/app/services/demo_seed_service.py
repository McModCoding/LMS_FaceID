"""Optional comprehensive demo fixtures, called only by scripts/seed.py --rich-demo.

Uses fictional people and the shared clock. Never creates biometric data, deletes
existing records or changes a database schema. Run on a dedicated demo database.
"""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.attendance import (
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
    LeaveRequest,
    LeaveRequestStatus,
)
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.department import Department
from app.models.exam import Exam, ExamQuestion
from app.models.grade import Grade, GradeComponent, GradePublication
from app.models.learning import (
    Announcement,
    Assignment,
    AssignmentStatus,
    Group,
    GroupMember,
    Notification,
    Submission,
)
from app.models.lecturer import Lecturer, LecturerType
from app.models.material import Material
from app.models.question import Question
from app.models.schedule import Schedule
from app.models.semester import Semester
from app.models.session import Session as Lesson
from app.models.session import SessionStatus
from app.models.student import Student, StudentStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.exam import ExamDraftIn
from app.schemas.exam_management import EssayGradeIn
from app.schemas.question import QuestionIn
from app.services import exam_attempt_service as attempts
from app.services import grade_service
from app.services.exam_draft_service import create_draft
from app.services.exam_lifecycle_service import close_exam, publish_exam
from app.services.exam_review_service import grade_essay
from app.services.notification_service import notify_enrolled_students
from app.services.question_service import create_questions
from app.utils.clock import now_local, override_clock
from app.utils.uploads import store_upload


def _utc(value):
    return value.astimezone(UTC).replace(tzinfo=None)


def _people(db, password):
    # One hash per fixture batch; all demo accounts have the documented password.
    password_hash = get_password_hash(password)
    for number in range(1, 121):
        username = f"sv{number:03d}"
        user = db.query(User).filter_by(username=username).first()
        if not user:
            user = User(username=username, email=f"{username}@example.test", role=UserRole.student,
                        password_hash=password_hash, is_active=True, must_change_password=False,
                        is_deleted=False, token_version=1)
            db.add(user)
            db.flush()
            db.add(Student(user_id=user.id, student_code=username.upper(),
                full_name=f"{['Nguyễn', 'Trần', 'Lê', 'Phạm'][number % 4]} "
                          f"{['Minh', 'Ngọc', 'Hoàng', 'Thu'][number % 4]} "
                          f"{['Anh', 'Hà', 'Phúc', 'Trang', 'Nam', 'Linh', 'Khoa'][number % 7]}",
                admin_class=f"16DHTH{1 + (number - 1) // 30:02d}", status=StudentStatus.studying,
                is_deleted=False))
        else:
            user.password_hash = password_hash
    for number in range(1, 9):
        username = f"gv{number:03d}"
        user = db.query(User).filter_by(username=username).first()
        if not user:
            user = User(username=username, email=f"{username}@example.test", role=UserRole.lecturer,
                        password_hash=password_hash, is_active=True, must_change_password=False,
                        is_deleted=False, token_version=1)
            db.add(user)
            db.flush()
            db.add(Lecturer(user_id=user.id, code=username.upper(),
                full_name={6: "Đỗ Thị Hạnh", 7: "Bùi Minh Khôi", 8: "Võ Ngọc Lan"}[number],
                type=LecturerType.visiting if number == 8 else LecturerType.full_time,
                degree="Thạc sĩ", department="Khoa Công nghệ Thông tin", is_deleted=False))
        else:
            user.password_hash = password_hash
    db.flush()


def _catalog(db, now):
    departments = []
    for code, name in [("DEMO-CNTT", "Công nghệ thông tin — dữ liệu mẫu"),
                       ("DEMO-KTPM", "Kỹ thuật phần mềm — dữ liệu mẫu")]:
        row = db.query(Department).filter_by(code=code).first()
        if not row:
            row = Department(code=code, name=name, is_active=True)
            db.add(row)
            db.flush()
        departments.append(row)
    students = db.query(Student).order_by(Student.student_code).all()
    lecturers = db.query(Lecturer).order_by(Lecturer.code).all()
    subjects = db.query(Subject).order_by(Subject.code).all()
    for index, row in enumerate(students):
        row.department_id = departments[(index // 60) % 2].id
    for index, row in enumerate(lecturers):
        row.department_id = departments[index % 2].id
    for index, row in enumerate(subjects):
        row.department_id = departments[index % 2].id
    current = db.query(Semester).filter_by(is_current=True).first()
    if not db.query(Semester).filter_by(name="Học kỳ trước — dữ liệu mẫu").first():
        db.add(Semester(name="Học kỳ trước — dữ liệu mẫu", start_date=now.date() - timedelta(days=270),
                        end_date=now.date() - timedelta(days=100), is_current=False))
    for index in range(8):
        code = f"DEMO-{index + 1:02d}"
        if db.query(Class).filter_by(code=code).first():
            continue
        cls = Class(code=code, subject_id=subjects[index % len(subjects)].id,
                    semester_id=current.id, lecturer_id=lecturers[(index + 3) % 8].id,
                    max_students=50, status=ClassStatus.draft if index == 6 else ClassStatus.active,
                    late_after_min=10, absent_after_min=30, weight_present=1,
                    weight_late=0.5, weight_excused=1, attendance_warning_absences=3, is_deleted=False)
        db.add(cls)
        db.flush()
        if index == 6:  # Intentionally empty draft for enrollment/configuration testing.
            continue
        cohort = [students[(index * 15 + offset) % len(students)] for offset in range(35)]
        db.add_all([ClassStudent(class_id=cls.id, student_id=s.id, status=ClassStudentStatus.enrolled)
                    for s in cohort])
        # Four evenings and four weekend daytime slots, separate from original schedules.
        weekday = index % 7
        start = time(19, 0) if index < 7 else time(16, 0)
        end = time(21, 0) if index < 7 else time(18, 0)
        schedule = Schedule(class_id=cls.id, weekday=weekday, start_time=start, end_time=end,
                            room=f"DEMO-{index + 1:02d}", start_date=current.start_date,
                            end_date=current.end_date)
        db.add(schedule)
        db.flush()
        day = now.date() - timedelta(days=(now.weekday() - weekday) % 7)
        for week in range(-6, 7):
            when = day + timedelta(weeks=week)
            finished = datetime.combine(when, end, now.tzinfo) < now
            lesson = Lesson(class_id=cls.id, schedule_id=schedule.id, session_no=week + 7,
                date=when, start_time=start, end_time=end, room=schedule.room,
                status=SessionStatus.closed if finished else SessionStatus.scheduled,
                opened_at=_utc(datetime.combine(when, start, now.tzinfo)) if finished else None,
                closed_at=_utc(datetime.combine(when, end, now.tzinfo)) if finished else None)
            if week == 6:
                lesson.status = SessionStatus.cancelled
            db.add(lesson)
    db.flush()


def _attendance(db, cls, students, now, teacher):
    lessons = db.query(Lesson).filter_by(class_id=cls.id).order_by(Lesson.date).all()
    for lesson in lessons:
        # The original seed opens today's lessons regardless of the time of day.
        if lesson.status == SessionStatus.open:
            if datetime.combine(lesson.date, lesson.end_time, now.tzinfo) < now:
                lesson.status, lesson.closed_at = SessionStatus.closed, _utc(datetime.combine(lesson.date, lesson.end_time, now.tzinfo))
            elif datetime.combine(lesson.date, lesson.start_time, now.tzinfo) > now + timedelta(minutes=30):
                lesson.status, lesson.opened_at = SessionStatus.scheduled, None
        if lesson.status != SessionStatus.closed:
            continue
        for index, student in enumerate(students):
            row = db.query(AttendanceRecord).filter_by(session_id=lesson.id, student_id=student.id).first()
            if not row:
                status = AttendanceStatus.absent if index == 0 else [AttendanceStatus.present,
                    AttendanceStatus.present, AttendanceStatus.late, AttendanceStatus.excused][(index + lesson.session_no) % 4]
                row = AttendanceRecord(session_id=lesson.id, student_id=student.id, status=status,
                    source=AttendanceSource.system if status == AttendanceStatus.absent else
                    AttendanceSource.leave if status == AttendanceStatus.excused else AttendanceSource.manual,
                    hit_count=0, modified_by=teacher.id if status in (AttendanceStatus.present, AttendanceStatus.late) else None)
                if status in (AttendanceStatus.present, AttendanceStatus.late):
                    row.first_seen_at = _utc(datetime.combine(lesson.date, lesson.start_time, now.tzinfo)
                                            + timedelta(minutes=15 if status == AttendanceStatus.late else 2))
                db.add(row)
            if row.status == AttendanceStatus.excused and not db.query(LeaveRequest).filter_by(
                    session_id=lesson.id, student_id=student.id).first():
                db.add(LeaveRequest(session_id=lesson.id, student_id=student.id,
                    reason="Đơn nghỉ mẫu: có lịch khám bệnh.", status=LeaveRequestStatus.approved,
                    reviewed_by=teacher.id, reviewed_at=_utc(datetime.combine(lesson.date, time(0), now.tzinfo)),
                    review_note="Đồng ý theo đơn mẫu."))
    db.flush()
    # Keep original approved requests and their existing attendance records consistent.
    for request in db.query(LeaveRequest).join(Lesson, Lesson.id == LeaveRequest.session_id).filter(
            Lesson.class_id == cls.id, LeaveRequest.status == LeaveRequestStatus.approved).all():
        row = db.query(AttendanceRecord).filter_by(session_id=request.session_id, student_id=request.student_id).first()
        if row and row.status == AttendanceStatus.absent and row.source == AttendanceSource.system:
            row.status, row.source = AttendanceStatus.excused, AttendanceSource.leave


def _learning(db, cls, students, teacher, now):
    for index, (suffix, days, late, draft) in enumerate([
        ("Ôn tập tuần này", 3, False, False), ("Thực hành còn nhận bài trễ", -1, True, False),
        ("Bài tập đã hết hạn", -3, False, False), ("Bài tập tuần tới", 10, False, False),
        ("Bản nháp chưa giao", 14, False, True), ("Bài tập tổng hợp", -7, True, False)]):
        title = f"{cls.code} · {suffix}"
        row = db.query(Assignment).filter_by(class_id=cls.id, title=title).first()
        if not row:
            row = Assignment(class_id=cls.id, title=title,
                description="Dữ liệu mẫu từ scripts/seed.py: trình bày cách làm, kết quả và tự đánh giá.",
                due_at=_utc(now + timedelta(days=days)), max_score=20 if index == 5 else 10,
                allow_late=late, status=AssignmentStatus.draft if draft else AssignmentStatus.published)
            db.add(row)
            db.flush()
            if not draft:
                notify_enrolled_students(db, cls.id, "assignment_published", "Bài tập mới", title,
                                         f"/student/classes/{cls.id}?tab=assignments")
        if draft:
            continue
        for number, student in enumerate(students[2:22]):  # SV001/SV002 remain usable for new submissions.
            if db.query(Submission).filter_by(assignment_id=row.id, student_id=student.id).first():
                continue
            is_late = late and number % 3 == 0
            submitted = row.due_at + timedelta(hours=2) if is_late else min(_utc(now - timedelta(hours=3)), row.due_at - timedelta(hours=12))
            score = None if number % 3 == 0 else round((number % 9 + 1) * row.max_score / 10, 1)
            file_path = None
            if number % 5 == 0:
                file_path = str(store_upload("submissions", row.id, ".txt",
                    f"Bài nộp mẫu của {student.student_code} cho {title}.".encode()))
            db.add(Submission(assignment_id=row.id, student_id=student.id, text="Bài làm mẫu: phân tích yêu cầu và kết quả thực hành.",
                file_path=file_path, submitted_at=submitted, is_late=is_late, score=score,
                feedback="Đã đáp ứng yêu cầu; cần giải thích rõ kết quả." if score is not None else None,
                graded_by=teacher.id if score is not None else None,
                graded_at=submitted + timedelta(hours=1) if score is not None else None))
    existing_members = {r.student_id for r in db.query(GroupMember).join(Group, Group.id == GroupMember.group_id).filter(Group.class_id == cls.id)}
    for index in range(1, 7):
        group = db.query(Group).filter_by(class_id=cls.id, name=f"Nhóm thực hành {index}").first()
        if not group:
            group = Group(class_id=cls.id, name=f"Nhóm thực hành {index}")
            db.add(group)
            db.flush()
        for student in students[(index - 1) * 5:index * 5]:
            if student.id not in existing_members:
                db.add(GroupMember(group_id=group.id, student_id=student.id))
                existing_members.add(student.id)
    for index in range(1, 5):
        title = f"{cls.code} · Thông báo học tập {index}"
        if not db.query(Announcement).filter_by(class_id=cls.id, title=title).first():
            db.add(Announcement(class_id=cls.id, author_id=teacher.id, title=title,
                content="Kiểm tra lịch học, học liệu và hạn nộp bài trước buổi tiếp theo.", is_pinned=index == 1))
            notify_enrolled_students(db, cls.id, "class_announcement", title,
                                     "Có thông báo học tập mới.", f"/student/classes/{cls.id}?tab=announcements")
    for index in range(1, 5):
        title = f"{cls.code} · Học liệu {index}"
        if not db.query(Material).filter_by(class_id=cls.id, title=title).first():
            path = store_upload("materials", cls.id, ".txt", f"Học liệu mẫu {index}: đọc đề, thực hành và tự đánh giá.".encode()) if index % 2 else None
            db.add(Material(class_id=cls.id, author_id=teacher.id, title=title,
                description="Học liệu mẫu phục vụ kiểm thử xem và tải.",
                url="https://docs.python.org/3/tutorial/" if path is None else None,
                file_path=str(path) if path else None, filename=f"hoc-lieu-{index}.txt" if path else None))
    db.commit()


def _exam(db, cls, teacher, students, now):
    subject = db.get(Subject, cls.subject_id)
    questions = []
    samples = [
        ("single", "Chọn phát biểu đúng về kiểm thử hệ thống", [("Cần kiểm cả trường hợp lỗi", True), ("Chỉ kiểm màn hình đẹp", False)]),
        ("multiple", "Chọn các dữ liệu cần bảo vệ", [("Mật khẩu", True), ("Ảnh khuôn mặt", True), ("Tên môn công khai", False)]),
        ("true_false", "Cần kiểm quyền truy cập ở máy chủ", [("Đúng", True), ("Sai", False)]),
        ("essay", "Mô tả một tình huống ứng dụng kiến thức môn học và cách kiểm chứng kết quả", []),
    ]
    for difficulty in ("easy", "medium", "hard"):
        for kind, content, options in samples:
            title = f"[{subject.code}/{difficulty}] {content}?"
            question = db.query(Question).filter_by(subject_id=subject.id, content=title).first()
            if not question:
                question = create_questions(db, teacher, subject.id, [QuestionIn(type=kind, content=title,
                    difficulty=difficulty, explanation="Câu hỏi mẫu kiểm thử nghiệp vụ LMS, không phải đề thi chính thức.",
                    options=[{"content": text, "is_correct": correct} for text, correct in options])])[0]
            if difficulty == "easy":
                questions.append(question)
    history = None
    for index, suffix in enumerate(["Đang mở — có thể làm ngay", "Sắp mở", "Nháp để soạn tiếp", "Đã đóng — có kết quả", "Đã đóng — ẩn kết quả"]):
        title = f"{cls.code} · {suffix}"
        exam = db.query(Exam).filter_by(class_id=cls.id, title=title).first()
        if exam:
            if index == 3:
                history = exam
            continue
        historical = index >= 3
        instant = now - timedelta(days=2) if historical else now
        with override_clock(instant):
            exam = create_draft(db, teacher, cls.id, ExamDraftIn(title=title,
                description="Đề mẫu có bốn dạng câu, dùng để kiểm thử làm bài, chấm và thống kê.",
                duration_min=30, open_at=instant + timedelta(days=2) if index == 1 else instant - timedelta(hours=1),
                close_at=instant + timedelta(days=7), max_attempts=2,
                score_policy="last" if cls.id % 2 else "highest",
                show_result="never" if index == 4 else "after_close" if historical else "after_submit",
                require_fullscreen=False, record_events=True, violation_types=["tab_hidden"],
                max_violations=0, auto_submit_on_violation=False,
                questions=[{"question_id": q.id, "points": "2.5"} for q in questions]))
            if index == 2:
                continue
            publish_exam(db, teacher, exam.id)
            if historical:
                snapshots = db.query(ExamQuestion).filter_by(exam_id=exam.id).order_by(ExamQuestion.order_no).all()
                for number, student in enumerate(students[:12]):
                    user = db.get(User, student.user_id)
                    for trial in range(2 if number in (2, 3) else 1):
                        attempt = attempts.begin_attempt(db, user, exam.id)
                        for row in snapshots:
                            snap = row.frozen_content
                            if snap["type"] == "essay":
                                attempts.save_answer(db, user, attempt.id, row.question_id, None,
                                    "Bài làm mẫu: xác định đầu vào, xử lý nghiệp vụ và kiểm tra kết quả.")
                            else:
                                correct = [o["id"] for o in snap["options"] if o["is_correct"]]
                                attempts.save_answer(db, user, attempt.id, row.question_id,
                                    correct if (number + trial) % 4 else [], None)
                        attempts.submit_attempt(db, user, attempt.id)
                        if index == 4 or number % 4 != 0:
                            grade_essay(db, teacher, attempt.id, questions[-1].id,
                                EssayGradeIn(score=Decimal("1.5") + Decimal(number % 3) / 2,
                                             feedback="Đã chấm bài mẫu, cần trình bày chi tiết hơn."))
                close_exam(db, teacher, exam.id)
                if index == 3:
                    history = exam
            elif index == 0 and len(students) > 1:
                # One resumable attempt; naturally becomes overdue after 30 minutes.
                user = db.get(User, students[1].user_id)
                attempts.begin_attempt(db, user, exam.id)
    return history


def seed_rich_demo(db: Session, password: str) -> None:
    now = now_local()
    _people(db, password)
    _catalog(db, now)
    db.commit()
    classes = db.query(Class).filter(Class.is_deleted.is_(False), Class.status == ClassStatus.active).order_by(Class.id).all()
    for cls in classes:
        teacher = db.get(User, db.get(Lecturer, cls.lecturer_id).user_id)
        students = db.query(Student).join(ClassStudent, ClassStudent.student_id == Student.id).filter(
            ClassStudent.class_id == cls.id, ClassStudent.status == ClassStudentStatus.enrolled).order_by(Student.student_code).all()
        _attendance(db, cls, students, now, teacher)
        _learning(db, cls, students, teacher, now)
        history = _exam(db, cls, teacher, students, now)
        # The small default seed references its unattempted introductory exam.
        # In the rich fixture, point that initial setup at the populated sources.
        original_exam = db.query(GradeComponent).filter_by(class_id=cls.id, type="exam").first()
        if original_exam and db.get(Exam, original_exam.ref_id).title == "Kiểm tra trực tuyến mẫu · 4 dạng câu hỏi":
            original_exam.ref_id, original_exam.weight = history.id, Decimal(50)
            initial_assignment = db.query(GradeComponent).filter_by(class_id=cls.id, type="assignment").one()
            initial_assignment.ref_id = db.query(Assignment).filter_by(class_id=cls.id,
                title=f"{cls.code} · Bài tập tổng hợp").one().id
            db.query(GradeComponent).filter_by(class_id=cls.id, type="manual").one().weight = Decimal(10)
        if not db.query(GradeComponent).filter_by(class_id=cls.id).first():
            assignment = db.query(Assignment).filter_by(class_id=cls.id, title=f"{cls.code} · Bài tập tổng hợp").one()
            db.add_all([
                GradeComponent(class_id=cls.id, name="Chuyên cần", type="attendance", weight=10),
                GradeComponent(class_id=cls.id, name="Thực hành", type="assignment", weight=30, ref_id=assignment.id),
                GradeComponent(class_id=cls.id, name="Kiểm tra", type="exam", weight=50, ref_id=history.id),
                GradeComponent(class_id=cls.id, name="Tham gia học tập", type="manual", weight=10)])
            db.flush()
        manual = db.query(GradeComponent).filter_by(class_id=cls.id, type="manual").first()
        for number, student in enumerate(students):
            if number % 5 and not db.query(Grade).filter_by(component_id=manual.id, student_id=student.id).first():
                db.add(Grade(component_id=manual.id, student_id=student.id,
                             score=Decimal(5 + number % 6), updated_by=teacher.id))
        db.commit()
        if cls.id % 2 == 0 and not db.query(GradePublication).filter_by(class_id=cls.id).first():
            grade_service.publish(db, teacher, cls.id)
        print(f"Demo: {cls.code} — {len(students)} sinh viên, học liệu/bài tập/kiểm tra/bảng điểm.", flush=True)
    # Preserve both editable and historical classes in the demo.
    closed = db.query(Class).filter_by(code="DEMO-08").first()
    if closed:
        teacher = db.get(User, db.get(Lecturer, closed.lecturer_id).user_id)
        published = db.query(Exam).filter_by(class_id=closed.id, status="published").all()
        if published:
            closed.status = ClassStatus.active
            db.flush()
        for exam in published:
            close_exam(db, teacher, exam.id)
        closed.status = ClassStatus.closed
        for lesson in db.query(Lesson).filter_by(class_id=closed.id, status=SessionStatus.scheduled):
            lesson.status = SessionStatus.cancelled
    # Mix read/unread notifications without inventing external messages.
    for row in db.query(Notification).filter(Notification.id % 3 == 0, Notification.is_read.is_(False)):
        row.is_read, row.read_at = True, _utc(now)
    db.commit()
