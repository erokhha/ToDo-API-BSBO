from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models import UserRole


class UserCreate(BaseModel):
    nickname: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    email: str
    role: UserRole


class UserWithTaskCount(UserResponse):
    task_count: int


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)
