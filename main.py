from fastapi import FastAPI

from routers import stats, tasks


app = FastAPI(
    title="ToDo лист API",
    description="API для управления задачами с использованием матрицы Эйзенхауэра",
    version="1.0.0",
    contact={"name": "Ерохина Светлана"},
)

app.include_router(stats.router)
app.include_router(tasks.router)


@app.get("/")
async def welcome() -> dict:
    return {
        "message": "Hello!",
        "title": app.title,
        "description": app.description,
        "version": app.version,
        "contact": app.contact,
    }
