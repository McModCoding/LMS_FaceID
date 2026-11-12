from pydantic import BaseModel


class WorkItem(BaseModel):
    title: str
    context: str
    link: str
    class_id: int | None = None


class WorkGroup(BaseModel):
    title: str
    count: int
    items: list[WorkItem]


class AttendanceBar(BaseModel):
    label: str
    total: int
    present: int


class NextSession(BaseModel):
    class_id: int
    class_code: str
    subject_name: str
    date: str
    start_time: str
    end_time: str
    room: str | None
    link: str


class DashboardClass(BaseModel):
    id: int
    code: str
    subject_name: str
    semester_name: str
    status: str


class DashboardOut(BaseModel):
    administrative: dict[str, int]
    date: str
    role: str
    class_count: int
    groups: list[WorkGroup]
    attendance: list[AttendanceBar]
    attendance_definition: str
    next_session: NextSession | None
    classes: list[DashboardClass]
