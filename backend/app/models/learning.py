"""Các model của M4/M5: FaceID mock, bài tập, thông báo và nhóm."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.class_ import Class
    from app.models.student import Student
    from app.models.user import User


class FaceTemplateStatus(str, enum.Enum):
    pending_embedding = "pending_embedding"
    active = "active"
    revoked = "revoked"


class RecognitionStatus(str, enum.Enum):
    matched = "matched"
    unknown = "unknown"
    ambiguous = "ambiguous"
    no_face = "no_face"
    low_quality = "low_quality"


class AssignmentStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class FaceConsent(Base):
    __tablename__ = "face_consents"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text_version: Mapped[str] = mapped_column(String(50), nullable=False)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    student: Mapped[Student] = relationship("Student", backref="face_consents")


class FaceTemplate(Base):
    __tablename__ = "face_templates"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[FaceTemplateStatus] = mapped_column(
        Enum(FaceTemplateStatus),
        nullable=False,
        default=FaceTemplateStatus.pending_embedding,
        index=True,
    )

    student: Mapped[Student] = relationship("Student", backref="face_templates")


class RecognitionLog(Base):
    __tablename__ = "recognition_logs"

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[RecognitionStatus] = mapped_column(Enum(RecognitionStatus), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_name: Mapped[str] = mapped_column(String(100), nullable=False)
    frame_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecognitionFrame(Base):
    __tablename__ = "recognition_frames"
    __table_args__ = (UniqueConstraint("session_id", "frame_id", name="uq_recognition_frame"),)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frame_id: Mapped[str] = mapped_column(String(36), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)


class Announcement(Base):
    __tablename__ = "announcements"

    class_id: Mapped[int | None] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    class_: Mapped[Class | None] = relationship("Class", backref="announcements")
    author: Mapped[User] = relationship("User", backref="announcements")


class Notification(Base):
    __tablename__ = "notifications"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", backref="notifications")


class Assignment(Base):
    __tablename__ = "assignments"

    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=10)
    allow_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attachment_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus), nullable=False, default=AssignmentStatus.draft, index=True
    )

    class_: Mapped[Class] = relationship("Class", backref="assignments")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_submission_assignment_student"),
    )

    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignment: Mapped[Assignment] = relationship("Assignment", backref="submissions")
    student: Mapped[Student] = relationship("Student", backref="submissions")
    grader: Mapped[User | None] = relationship("User", foreign_keys=[graded_by])


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("class_id", "name", name="uq_group_class_name"),)

    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    class_: Mapped[Class] = relationship("Class", backref="groups")


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "student_id", name="uq_group_member"),)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )

    group: Mapped[Group] = relationship("Group", backref="members")
    student: Mapped[Student] = relationship("Student", backref="group_memberships")
