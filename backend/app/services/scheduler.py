"""
services/scheduler.py
APScheduler: tự động đóng buổi học quá hạn mỗi phút.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _auto_close_job() -> None:
    """Job chạy mỗi phút: tự đóng buổi open quá SESSION_AUTO_CLOSE_AFTER_END_MIN."""
    db = SessionLocal()
    try:
        from app.services.session_lifecycle_service import auto_close_overdue
        count = auto_close_overdue(db)
        if count:
            logger.info("[scheduler] Đã tự đóng %d buổi học.", count)
    except Exception as exc:
        logger.exception("[scheduler] Lỗi auto_close: %s", exc)
    finally:
        db.close()


def _auto_submit_exams_job() -> None:
    db = SessionLocal()
    try:
        from app.services.exam_attempt_service import auto_submit_overdue

        count = auto_submit_overdue(db)
        if count:
            logger.info("[scheduler] Đã tự nộp %d lượt kiểm tra.", count)
    except Exception:
        logger.exception("[scheduler] Lỗi tự nộp bài kiểm tra")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
    _scheduler.add_job(_auto_close_job, "interval", minutes=1, id="auto_close_sessions")
    _scheduler.add_job(_auto_submit_exams_job, "interval", seconds=30, id="auto_submit_exams")
    _scheduler.start()
    logger.info("[scheduler] APScheduler khởi động — tự đóng buổi mỗi phút.")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] APScheduler đã dừng.")
