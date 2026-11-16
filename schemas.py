from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskBase(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_important: bool
    is_urgent: bool


class TaskCreate(TaskBase):
    model_config = ConfigDict(extra="forbid")


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_important: bool | None = None
    is_urgent: bool | None = None
    completed: bool | None = None


class TaskResponse(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quadrant: str
    completed: bool
    created_at: datetime
