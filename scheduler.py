from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from database import AsyncSessionLocal
from models import Task
from utils import calculate_urgency, determine_quadrant


async def update_task_urgency() -> int:
    changed = 0
    async with AsyncSessionLocal() as db:
        tasks = (await db.execute(select(Task).where(Task.completed.is_(False)))).scalars().all()
        for task in tasks:
            urgent = calculate_urgency(task.deadline_at)
            quadrant = determine_quadrant(task.is_important, urgent)
            if task.is_urgent != urgent or task.quadrant != quadrant:
                task.is_urgent = urgent
                task.quadrant = quadrant
                changed += 1
        if changed:
            await db.commit()
    return changed


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(update_task_urgency, "cron", hour=9, minute=0, id="refresh_task_urgency", max_instances=1, coalesce=True)
    scheduler.start()
    return scheduler
