from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from dependencies import get_current_admin
from models import Task, User
from schemas_auth import UserWithTaskCount


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserWithTaskCount])
async def get_admin_users(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_async_session),
) -> list[UserWithTaskCount]:
    rows = (
        await db.execute(
            select(User, func.count(Task.id))
            .outerjoin(Task, Task.user_id == User.id)
            .group_by(User.id)
            .order_by(User.id)
        )
    ).all()
    return [
        UserWithTaskCount(
            id=user.id,
            nickname=user.nickname,
            email=user.email,
            role=user.role,
            task_count=count,
        )
        for user, count in rows
    ]
