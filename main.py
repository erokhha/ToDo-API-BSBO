from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, get_async_session, init_db
from routers import stats, tasks
from scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = start_scheduler()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await engine.dispose()


app = FastAPI(
    title="ToDo лист API",
    description="API для управления задачами с использованием матрицы Эйзенхауэра",
    version="2.0.0",
    contact={"name": "Ерохина Светлана"},
    lifespan=lifespan,
)

app.include_router(stats.router, prefix="/api/v2")
app.include_router(tasks.router, prefix="/api/v2")


@app.get("/")
async def welcome() -> dict:
    return {
        "message": "Hello!",
        "title": app.title,
        "description": app.description,
        "version": app.version,
        "contact": app.contact,
    }


@app.get("/api/v2/health")
async def health(db: AsyncSession = Depends(get_async_session)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
