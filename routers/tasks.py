from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Response, status

from database import tasks_db
from schemas import TaskCreate, TaskResponse, TaskUpdate


router = APIRouter(prefix="/tasks", tags=["tasks"])


def find_task(task_id: int) -> dict:
    for task in tasks_db:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Задача не найдена")


def get_quadrant(is_important: bool, is_urgent: bool) -> str:
    return {
        (True, True): "Q1",
        (True, False): "Q2",
        (False, True): "Q3",
        (False, False): "Q4",
    }[(is_important, is_urgent)]


@router.get("")
async def get_all_tasks() -> dict:
    return {"count": len(tasks_db), "tasks": tasks_db}


@router.get("/quadrant/{quadrant}")
async def get_tasks_by_quadrant(quadrant: str) -> dict:
    if quadrant not in ("Q1", "Q2", "Q3", "Q4"):
        raise HTTPException(status_code=400, detail="Use Q1, Q2, Q3, or Q4")
    filtered_tasks = [task for task in tasks_db if task["quadrant"] == quadrant]
    return {"quadrant": quadrant, "count": len(filtered_tasks), "tasks": filtered_tasks}


@router.get("/search")
async def search_tasks(q: str = Query(min_length=2)) -> dict:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Enter at least 2 characters")
    filtered_tasks = [
        task
        for task in tasks_db
        if query.casefold() in task["title"].casefold()
        or query.casefold() in (task["description"] or "").casefold()
    ]
    if not filtered_tasks:
        raise HTTPException(status_code=404, detail="No tasks found")
    return {"query": query, "count": len(filtered_tasks), "tasks": filtered_tasks}


@router.get("/status/{status}")
async def get_tasks_by_status(status: str) -> dict:
    if status not in ("completed", "pending"):
        raise HTTPException(status_code=404, detail="Use completed or pending")
    filtered_tasks = [task for task in tasks_db if task["completed"] == (status == "completed")]
    return {"status": status, "count": len(filtered_tasks), "tasks": filtered_tasks}


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(task_id: int) -> TaskResponse:
    return find_task(task_id)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate) -> TaskResponse:
    new_task = {
        "id": max((item["id"] for item in tasks_db), default=0) + 1,
        **task.model_dump(),
        "quadrant": get_quadrant(task.is_important, task.is_urgent),
        "completed": False,
        "created_at": datetime.now(),
    }
    tasks_db.append(new_task)
    return new_task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate) -> TaskResponse:
    task = find_task(task_id)
    update_data = task_update.model_dump(exclude_unset=True)
    if any(value is None for field, value in update_data.items() if field != "description"):
        raise HTTPException(status_code=422, detail="Null is not allowed for this field")
    task.update(update_data)
    if "is_important" in update_data or "is_urgent" in update_data:
        task["quadrant"] = get_quadrant(task["is_important"], task["is_urgent"])
    return task


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: int) -> TaskResponse:
    task = find_task(task_id)
    task["completed"] = True
    task["completed_at"] = datetime.now()
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int) -> Response:
    tasks_db.remove(find_task(task_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
