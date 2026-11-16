from pydantic import BaseModel, ConfigDict, Field, StrictBool


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    is_important: StrictBool
    is_urgent: StrictBool
