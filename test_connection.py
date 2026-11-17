import asyncio

from sqlalchemy import func, select, text

from database import AsyncSessionLocal, engine, init_db
from models import Task


async def test_connection() -> None:
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            print(f"SELECT 1: {result.scalar_one()}")

        await init_db()

        async with AsyncSessionLocal() as session:
            count = await session.scalar(select(func.count()).select_from(Task))
            print(f"Задач в базе: {count}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_connection())
