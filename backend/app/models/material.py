"""Basic class materials approved for M5a."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Material(Base):
    __tablename__ = "materials"

    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
