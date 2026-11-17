from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from models import Task
from schemas import TimingStatsResponse


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_tasks_stats(db: AsyncSession = Depends(get_async_session)) -> dict:
    total = (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    quadrants = dict((await db.execute(select(Task.quadrant, func.count()).group_by(Task.quadrant))).all())
    completed = (await db.execute(select(func.count()).select_from(Task).where(Task.completed.is_(True)))).scalar_one()
    return {
        "total_tasks": total,
        "by_quadrant": {quadrant: quadrants.get(quadrant, 0) for quadrant in ("Q1", "Q2", "Q3", "Q4")},
        "by_status": {"completed": completed, "pending": total - completed},
    }


@router.get("/timing", response_model=TimingStatsResponse)
async def get_timing_stats(db: AsyncSession = Depends(get_async_session)) -> TimingStatsResponse:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(
            func.count().filter(Task.completed.is_(True), Task.completed_at <= Task.deadline_at),
            func.count().filter(Task.completed.is_(True), or_(Task.completed_at.is_(None), Task.completed_at > Task.deadline_at)),
            func.count().filter(Task.completed.is_(False), Task.deadline_at >= now),
            func.count().filter(Task.completed.is_(False), Task.deadline_at < now),
        ).where(Task.deadline_at.is_not(None))
    )
    on_time, late, on_plan, overdue = result.one()
    return TimingStatsResponse(
        completed_on_time=on_time,
        completed_late=late,
        on_plan_pending=on_plan,
        overtime_pending=overdue,
    )
