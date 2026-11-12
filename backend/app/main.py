from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    attendance,
    audit_logs,
    auth,
    classes,
    dashboard,
    departments,
    exam_attempts,
    exam_drafts,
    exam_management,
    face,
    grades,
    learning,
    leave_requests,
    lecturers,
    materials,
    questions,
    semesters,
    sessions,
    students,
    subjects,
    system_info,
    timetable,
    users,
)
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động background scheduler
    start_scheduler()
    yield
    # Dừng scheduler khi ứng dụng tắt
    stop_scheduler()


app = FastAPI(
    title="LMS FaceID API",
    version="0.3.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(grades.router, prefix="/api/v1")
app.include_router(system_info.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(semesters.router, prefix="/api/v1")
app.include_router(subjects.router, prefix="/api/v1")
app.include_router(lecturers.router, prefix="/api/v1")
app.include_router(students.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(audit_logs.router, prefix="/api/v1")
app.include_router(departments.router, prefix="/api/v1")
# M2a
app.include_router(classes.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(timetable.router, prefix="/api/v1")
# M3a
app.include_router(attendance.router, prefix="/api/v1")
app.include_router(leave_requests.router, prefix="/api/v1")
# M4
app.include_router(face.router, prefix="/api/v1")
# M5
app.include_router(learning.router, prefix="/api/v1")
app.include_router(materials.router, prefix="/api/v1")
# M6.1
app.include_router(questions.router, prefix="/api/v1")
app.include_router(exam_drafts.router, prefix="/api/v1")
app.include_router(exam_management.router, prefix="/api/v1")
# M6.4 student exam list and attempt-taking endpoints. No publication endpoint is exposed.
app.include_router(exam_attempts.router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return {"status": "ok", "version": "0.3.0"}
