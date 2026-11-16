from fastapi import APIRouter

from .tasks import tasks_db


router = APIRouter(prefix="/tasks", tags=["stats"])


@router.get("/stats")
async def get_tasks_stats() -> dict:
    return {
        "total_tasks": len(tasks_db),
        "by_quadrant": {
            quadrant: sum(task["quadrant"] == quadrant for task in tasks_db)
            for quadrant in ("Q1", "Q2", "Q3", "Q4")
        },
        "by_status": {
            "completed": sum(task["completed"] for task in tasks_db),
            "pending": sum(not task["completed"] for task in tasks_db),
        },
    }
