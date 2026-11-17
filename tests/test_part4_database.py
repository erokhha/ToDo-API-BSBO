import asyncio
import subprocess
import sys
import unittest
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, get_async_session, init_db
from models import Task


ROOT = Path(__file__).resolve().parents[1]


class Part4DatabaseTest(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await engine.dispose()

    async def test_connection_and_existing_rows(self):
        async with engine.connect() as connection:
            self.assertEqual((await connection.execute(text("SELECT 1"))).scalar_one(), 1)

        async with engine.connect() as connection:
            before = (await connection.execute(select(Task.id).order_by(Task.id))).scalars().all()

        self.assertTrue(set(range(1, 9)).issubset(before))
        await init_db()

        session_source = get_async_session()
        session = await anext(session_source)
        try:
            self.assertIsInstance(session, AsyncSession)
            after = (await session.execute(select(Task.id).order_by(Task.id))).scalars().all()
            self.assertEqual(after, before)
        finally:
            await session_source.aclose()

    async def test_model_mapping(self):
        expected = {
            "id",
            "title",
            "description",
            "is_important",
            "is_urgent",
            "quadrant",
            "completed",
            "created_at",
            "completed_at",
            "deadline_at",
        }
        self.assertEqual(set(inspect(Task).columns.keys()), expected)
        self.assertTrue(Task.__table__.c.created_at.type.timezone)
        self.assertTrue(Task.__table__.c.completed_at.type.timezone)
        self.assertTrue(Task.__table__.c.deadline_at.type.timezone)

        session_source = get_async_session()
        session = await anext(session_source)
        try:
            task = (await session.execute(select(Task).order_by(Task.id))).scalars().first()
            self.assertIsNotNone(task)
            self.assertEqual(set(task.to_dict()), expected)
        finally:
            await session_source.aclose()

    async def test_connection_script(self):
        async with engine.connect() as connection:
            before = (await connection.execute(select(Task.id))).scalars().all()

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(ROOT / "test_connection.py"),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        self.assertEqual(process.returncode, 0, stderr.decode())
        output = stdout.decode()
        self.assertIn("SELECT 1: 1", output)
        self.assertIn(f"Задач в базе: {len(before)}", output)


if __name__ == "__main__":
    unittest.main()
