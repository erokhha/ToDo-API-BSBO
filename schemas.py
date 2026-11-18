from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from utils import as_utc, calculate_days_until_deadline


class TaskBase(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_important: bool
    deadline_at: datetime | None = None


class TaskCreate(TaskBase):
    model_config = ConfigDict(extra="forbid")


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_important: bool | None = None
    deadline_at: datetime | None = None
    completed: bool | None = None


class TaskResponse(TaskBase):
    id: int
    user_id: int | None
    is_urgent: bool
    quadrant: str
    completed: bool
    created_at: datetime
    completed_at: datetime | None
    days_until_deadline: int | None
    status_message: str

    @classmethod
    def from_task(cls, task):
        days = calculate_days_until_deadline(task.deadline_at)
        overdue = bool(task.deadline_at and not task.completed and as_utc(task.deadline_at) < datetime.now(timezone.utc))
        return cls(
            id=task.id,
            user_id=task.user_id,
            title=task.title,
            description=task.description,
            is_important=task.is_important,
            is_urgent=task.is_urgent,
            quadrant=task.quadrant,
            completed=task.completed,
            created_at=task.created_at,
            completed_at=task.completed_at,
            deadline_at=task.deadline_at,
            days_until_deadline=days,
            status_message="Задача просрочена" if overdue else "Все идет по плану!",
        )


class TimingStatsResponse(BaseModel):
    completed_on_time: int
    completed_late: int
    on_plan_pending: int
    overtime_pending: int
