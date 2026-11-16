from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from schemas import TaskCreate


router = APIRouter(prefix="/tasks", tags=["tasks"])

tasks_db = [
    {
        "id": 1,
        "title": "Сдать проект по FastAPI",
        "description": "Завершить разработку API и написать документацию",
        "is_important": True,
        "is_urgent": True,
        "quadrant": "Q1",
        "completed": False,
        "created_at": datetime.now(),
    },
    {
        "id": 2,
        "title": "Изучить SQLAlchemy",
        "description": "Прочитать документацию и попробовать примеры",
        "is_important": True,
        "is_urgent": False,
        "quadrant": "Q2",
        "completed": False,
        "created_at": datetime.now(),
    },
    {
        "id": 3,
        "title": "Сходить на лекцию",
        "description": "Лекция по интероперабельности",
        "is_important": False,
        "is_urgent": True,
        "quadrant": "Q3",
        "completed": False,
        "created_at": datetime.now(),
    },
    {
        "id": 4,
        "title": "Посмотреть сериал",
        "description": "Новый сезон любимого сериала",
        "is_important": False,
        "is_urgent": False,
        "quadrant": "Q4",
        "completed": True,
        "created_at": datetime.now(),
    },
]


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


@router.get("/{task_id}")
async def get_task_by_id(task_id: int) -> dict:
    for task in tasks_db:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@router.post("", status_code=201)
async def create_task(task: TaskCreate) -> dict:
    quadrant = {
        (True, True): "Q1",
        (True, False): "Q2",
        (False, True): "Q3",
        (False, False): "Q4",
    }[(task.is_important, task.is_urgent)]
    new_task = {
        "id": max(item["id"] for item in tasks_db) + 1,
        "title": task.title,
        "description": task.description,
        "is_important": task.is_important,
        "is_urgent": task.is_urgent,
        "quadrant": quadrant,
        "completed": False,
        "created_at": datetime.now(),
    }
    tasks_db.append(new_task)
    return new_task
