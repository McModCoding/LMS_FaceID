"""Role-scoped work lists built from persisted learning data."""
import re
from datetime import UTC

from sqlalchemy import and_, or_

from app.models.attendance import AttendanceRecord, LeaveRequest, LeaveRequestStatus
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.exam import Exam, ExamStatus
from app.models.exam_attempt import AttemptStatus, ExamAttempt
from app.models.learning import Assignment, AssignmentStatus, Notification, Submission
from app.models.lecturer import Lecturer
from app.models.session import Session as Lesson
from app.models.session import SessionStatus
from app.models.student import Student
from app.models.user import UserRole
from app.utils.clock import now_local


def dashboard(db, user):
    now = now_local()
    utc = now.astimezone(UTC).replace(tzinfo=None)
    role = user.role.value
    query = db.query(Class).filter(Class.is_deleted.is_(False))
    student = None
    if user.role == UserRole.student:
        student = db.query(Student).filter_by(user_id=user.id, is_deleted=False).first()
        query = query.join(ClassStudent, ClassStudent.class_id == Class.id).filter(
            ClassStudent.student_id == (student.id if student else -1), ClassStudent.status == ClassStudentStatus.enrolled)
    elif user.role == UserRole.lecturer:
        query = query.join(Lecturer, Lecturer.id == Class.lecturer_id).filter(Lecturer.user_id == user.id, Lecturer.is_deleted.is_(False))
    classes = query.order_by(Class.code).all()
    # Closed classes remain in historical charts, but cannot offer editable work.
    ids = [c.id for c in classes if c.status != ClassStatus.closed]
    groups = []
    def group(title, items):
        groups.append({"title": title, "count": len(items), "items": items})
    def item(cls, title, tab):
        return {"title": title, "context": cls.code, "class_id": cls.id, "link": f"/{role}/classes/{cls.id}?tab={tab}"}
    by_id = {c.id: c for c in classes}
    sessions = db.query(Lesson).filter(Lesson.class_id.in_(ids), Lesson.date == now.date(), Lesson.status != SessionStatus.cancelled).order_by(Lesson.start_time).all()
    group("Lịch hôm nay", [item(by_id[s.class_id], f"Buổi {s.session_no} · {s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}", "schedules") for s in sessions])
    if student:
        assignments = db.query(Assignment).filter(Assignment.class_id.in_(ids), Assignment.status == AssignmentStatus.published).order_by(Assignment.due_at).all()
        submitted = {r.assignment_id for r in db.query(Submission).filter(Submission.student_id == student.id).all()}
        assignments.sort(key=lambda a: (a.due_at < utc, a.due_at))
        group("Bài tập cần nộp", [item(by_id[a.class_id], a.title + (" · Quá hạn, còn nhận bài trễ" if a.due_at < utc else " · Hạn " + a.due_at.replace(tzinfo=UTC).astimezone(now.tzinfo).strftime('%d/%m %H:%M')), "assignments") for a in assignments if a.id not in submitted and (a.due_at >= utc or a.allow_late)])
        exams = db.query(Exam).filter(Exam.class_id.in_(ids), Exam.status == ExamStatus.published, Exam.close_at > utc).order_by(Exam.open_at).all()
        attempts = db.query(ExamAttempt).filter(ExamAttempt.student_id == student.id).all()
        exam_items = []
        for exam in exams:
            own = [a for a in attempts if a.exam_id == exam.id]
            active = next((a for a in own if a.status == AttemptStatus.in_progress and a.deadline_at >= utc), None)
            if active:
                exam_items.append({"title": exam.title + " · Tiếp tục lượt đang làm", "context": by_id[exam.class_id].code, "class_id": exam.class_id, "link": f"/student/exams/{active.id}"})
            elif len(own) < exam.max_attempts:
                exam_items.append(item(by_id[exam.class_id], exam.title + (" · Chưa mở" if exam.open_at > utc else " · Đang mở"), "exams"))
        exam_items.sort(key=lambda x: not x["link"].startswith("/student/exams/"))
        group("Kiểm tra cần theo dõi", exam_items)
        notices = db.query(Notification).filter_by(user_id=user.id, is_read=False).order_by(Notification.id.desc()).all()
        notice_items = []
        for notice in notices:
            match = re.match(r"^/student/classes/(\d+)(?:[/?#]|$)", notice.link or "")
            class_id = int(match.group(1)) if match else None
            notice_items.append({"title": notice.title, "context": notice.body,
                "class_id": class_id if class_id in by_id else None,
                "link": notice.link or "/student/classes"})
        group("Phản hồi và thông báo chưa đọc", notice_items)
    else:
        pending = db.query(Submission, Assignment).join(Assignment, Assignment.id == Submission.assignment_id).filter(Assignment.class_id.in_(ids), Submission.score.is_(None)).all()
        group("Bài tập chờ chấm", [item(by_id[a.class_id], a.title + f" · SV #{s.student_id}", "assignments") for s, a in pending])
        essays = db.query(ExamAttempt, Exam).join(Exam, Exam.id == ExamAttempt.exam_id).filter(Exam.class_id.in_(ids), ExamAttempt.status.in_([AttemptStatus.submitted, AttemptStatus.auto_submitted])).all()
        group("Kiểm tra chờ chấm tự luận", [item(by_id[e.class_id], e.title + f" · Lượt #{a.id}", "exams") for a, e in essays])
        leaves = db.query(LeaveRequest, Lesson).join(Lesson, Lesson.id == LeaveRequest.session_id).filter(Lesson.class_id.in_(ids), LeaveRequest.status == LeaveRequestStatus.pending).all()
        group("Đơn xin vắng chờ duyệt", [item(by_id[s.class_id], f"Đơn #{r.id} · Buổi {s.session_no}", "leave") for r, s in leaves])
    warnings = []
    chart = []
    for cls in classes:
        records = db.query(AttendanceRecord).join(Lesson, Lesson.id == AttendanceRecord.session_id).filter(Lesson.class_id == cls.id, Lesson.status == SessionStatus.closed)
        if student:
            records = records.filter(AttendanceRecord.student_id == student.id)
        records = records.all()
        counts = {}
        for record in records:
            if record.status.value == "absent":
                counts[record.student_id] = counts.get(record.student_id, 0) + 1
        flagged = sum(n >= cls.attendance_warning_absences for n in counts.values())
        if flagged:
            warnings.append(item(cls, f"{flagged} sinh viên chạm ngưỡng vắng {cls.attendance_warning_absences} buổi", "attendance" if student else "report"))
        chart.append({"label": cls.code, "total": len(records), "present": sum(r.status.value in ("present", "late") for r in records)})
    group("Cảnh báo chuyên cần", warnings)
    upcoming = db.query(Lesson).filter(
        Lesson.class_id.in_(ids), Lesson.status.in_([SessionStatus.scheduled, SessionStatus.open]),
        or_(Lesson.date > now.date(), and_(Lesson.date == now.date(), Lesson.end_time >= now.time().replace(tzinfo=None))),
    ).order_by(Lesson.date, Lesson.start_time, Lesson.id).first()
    next_session = None
    if upcoming:
        cls = by_id[upcoming.class_id]
        next_session = {"class_id": cls.id, "class_code": cls.code, "subject_name": cls.subject.name,
            "date": upcoming.date.isoformat(), "start_time": upcoming.start_time.isoformat(),
            "end_time": upcoming.end_time.isoformat(), "room": upcoming.room,
            "link": f"/{role}/classes/{cls.id}?tab=schedules"}
    class_summaries = [{"id": cls.id, "code": cls.code, "subject_name": cls.subject.name,
        "semester_name": cls.semester.name, "status": cls.status.value} for cls in classes[:3]]
    administrative = {"Sinh viên": db.query(Student).filter_by(is_deleted=False).count(),
        "Giảng viên": db.query(Lecturer).filter_by(is_deleted=False).count(), "Lớp học phần": len(classes)} if user.role == UserRole.admin else {}
    return {"date": now.date().isoformat(), "role": role, "class_count": len(classes), "groups": groups, "administrative": administrative, "next_session": next_session, "classes": class_summaries,
        "attendance": chart, "attendance_definition": "Tỷ lệ có mặt = số bản ghi present hoặc late / tổng bản ghi thuộc buổi đã đóng; không có dữ liệu khi mẫu số bằng 0."}
