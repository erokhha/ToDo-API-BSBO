from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from models import Task
from schemas import TaskCreate, TaskResponse, TaskUpdate
from utils import as_utc, calculate_urgency, determine_quadrant


router = APIRouter(prefix="/tasks", tags=["tasks"])


async def find_task(task_id: int, db: AsyncSession) -> Task:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


def task_list(tasks: list[Task]) -> list[TaskResponse]:
    return [TaskResponse.from_task(task) for task in tasks]


@router.get("")
async def get_all_tasks(db: AsyncSession = Depends(get_async_session)) -> dict:
    tasks = (await db.execute(select(Task).order_by(Task.id))).scalars().all()
    return {"count": len(tasks), "tasks": task_list(tasks)}


@router.get("/today")
async def get_tasks_due_today(db: AsyncSession = Depends(get_async_session)) -> dict:
    start = datetime.combine(datetime.now(timezone.utc).date(), time.min, timezone.utc)
    end = start + timedelta(days=1)
    tasks = (await db.execute(select(Task).where(Task.completed.is_(False), Task.deadline_at >= start, Task.deadline_at < end).order_by(Task.deadline_at))).scalars().all()
    return {"count": len(tasks), "tasks": task_list(tasks)}


@router.get("/quadrant/{quadrant}")
async def get_tasks_by_quadrant(quadrant: str, db: AsyncSession = Depends(get_async_session)) -> dict:
    if quadrant not in ("Q1", "Q2", "Q3", "Q4"):
        raise HTTPException(status_code=400, detail="Use Q1, Q2, Q3, or Q4")
    tasks = (await db.execute(select(Task).where(Task.quadrant == quadrant).order_by(Task.id))).scalars().all()
    return {"quadrant": quadrant, "count": len(tasks), "tasks": task_list(tasks)}


@router.get("/search")
async def search_tasks(q: str = Query(min_length=2), db: AsyncSession = Depends(get_async_session)) -> dict:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Enter at least 2 characters")
    pattern = f"%{query}%"
    tasks = (await db.execute(select(Task).where(or_(Task.title.ilike(pattern), func.coalesce(Task.description, "").ilike(pattern))).order_by(Task.id))).scalars().all()
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found")
    return {"query": query, "count": len(tasks), "tasks": task_list(tasks)}


@router.get("/status/{task_status}")
async def get_tasks_by_status(task_status: str, db: AsyncSession = Depends(get_async_session)) -> dict:
    if task_status not in ("completed", "pending"):
        raise HTTPException(status_code=404, detail="Use completed or pending")
    tasks = (await db.execute(select(Task).where(Task.completed.is_(task_status == "completed")).order_by(Task.id))).scalars().all()
    return {"status": task_status, "count": len(tasks), "tasks": task_list(tasks)}


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(task_id: int, db: AsyncSession = Depends(get_async_session)) -> TaskResponse:
    return TaskResponse.from_task(await find_task(task_id, db))


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_async_session)) -> TaskResponse:
    urgent = calculate_urgency(task.deadline_at)
    new_task = Task(
        title=task.title,
        description=task.description,
        is_important=task.is_important,
        is_urgent=urgent,
        quadrant=determine_quadrant(task.is_important, urgent),
        deadline_at=as_utc(task.deadline_at) if task.deadline_at else None,
        completed=False,
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return TaskResponse.from_task(new_task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate, db: AsyncSession = Depends(get_async_session)) -> TaskResponse:
    task = await find_task(task_id, db)
    changes = task_update.model_dump(exclude_unset=True)
    if any(value is None for field, value in changes.items() if field not in ("description", "deadline_at")):
        raise HTTPException(status_code=422, detail="Null is not allowed for this field")
    if changes.get("deadline_at") is not None:
        changes["deadline_at"] = as_utc(changes["deadline_at"])
    for field, value in changes.items():
        setattr(task, field, value)
    if "completed" in changes:
        task.completed_at = datetime.now(timezone.utc) if task.completed else None
    if "deadline_at" in changes or "is_important" in changes:
        task.is_urgent = calculate_urgency(task.deadline_at)
        task.quadrant = determine_quadrant(task.is_important, task.is_urgent)
    await db.commit()
    await db.refresh(task)
    return TaskResponse.from_task(task)


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: int, db: AsyncSession = Depends(get_async_session)) -> TaskResponse:
    task = await find_task(task_id, db)
    if not task.completed:
        task.completed = True
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)
    return TaskResponse.from_task(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_async_session)) -> Response:
    await db.delete(await find_task(task_id, db))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
