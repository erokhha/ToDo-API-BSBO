import json
import os
import socket
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import psycopg2
from dotenv import load_dotenv
from sqlalchemy.engine import make_url


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Part5ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as address:
            address.bind(("127.0.0.1", 0))
            cls.port = address.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(cls.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(80):
            try:
                cls.request("GET", "/openapi.json")
                break
            except URLError:
                time.sleep(0.1)
        else:
            cls.server.terminate()
            raise RuntimeError("API server did not start")
        suffix = uuid4().hex[:10]
        cls.email = f"part5_{suffix}@example.com"
        cls.password = "Part5Password!"
        code, user = cls.request(
            "POST",
            "/api/v2/auth/register",
            {"nickname": f"part5_{suffix}", "email": cls.email, "password": cls.password},
        )
        if code != 201:
            cls.server.terminate()
            raise RuntimeError(f"Test registration failed: {code}")
        cls.user_id = user["id"]
        _, token = cls.request("POST", "/api/v2/auth/login", {"username": cls.email, "password": cls.password}, form=True)
        cls.token = token["access_token"]

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=5)
        url = make_url(os.environ["DATABASE_URL"])
        with psycopg2.connect(host=url.host, port=url.port, user=url.username, password=url.password, dbname=url.database) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE id = %s", (cls.user_id,))

    @classmethod
    def request(cls, method, path, body=None, form=False):
        data = urlencode(body).encode() if form else json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
        if getattr(cls, "token", None):
            headers["Authorization"] = f"Bearer {cls.token}"
        request = Request(
            cls.base + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            try:
                return response.status, json.loads(raw) if raw else None
            except json.JSONDecodeError:
                return response.status, raw.decode()

    def test_deadline_workflow(self):
        base = "/api/v2/tasks"
        created_ids = []
        now = datetime.now(timezone.utc)
        future = (now + timedelta(days=5)).isoformat()
        soon = (now + timedelta(days=2)).isoformat()
        overdue = (now - timedelta(days=1)).isoformat()
        today = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
        try:
            self.assertEqual(self.request("GET", "/api/v2/health")[0], 200)
            self.assertEqual(self.request("GET", "/api/v1/tasks")[0], 404)
            before = self.request("GET", "/api/v2/stats")[1]["total_tasks"]
            timing_before = self.request("GET", "/api/v2/stats/timing")[1]
            self.assertEqual(self.request("POST", base, {"title": "x", "is_important": True})[0], 422)
            self.assertEqual(self.request("POST", base, {"title": "Valid task", "is_important": True, "is_urgent": True})[0], 422)

            for name, deadline, important, urgent, quadrant in (
                ("Part5 future test", future, True, False, "Q2"),
                ("Part5 soon test", soon, True, True, "Q1"),
                ("Part5 no date test", None, False, False, "Q4"),
            ):
                code, task = self.request("POST", base, {"title": name, "is_important": important, "deadline_at": deadline})
                self.assertEqual(code, 201)
                created_ids.append(task["id"])
                self.assertEqual(task["is_urgent"], urgent)
                self.assertEqual(task["quadrant"], quadrant)
                self.assertEqual(task["deadline_at"] is None, deadline is None)
                self.assertIn("days_until_deadline", task)
                self.assertIn("status_message", task)
            self.assertEqual(self.request("GET", base)[1]["count"], before + 3)
            self.assertIsNone(self.request("GET", f"{base}/{created_ids[2]}")[1]["days_until_deadline"])
            timing = self.request("GET", "/api/v2/stats/timing")[1]
            self.assertEqual(timing["on_plan_pending"], timing_before["on_plan_pending"] + 2)

            code, past_task = self.request("POST", base, {"title": "Part5 overdue test", "is_important": False, "deadline_at": overdue})
            self.assertEqual(code, 201)
            created_ids.append(past_task["id"])
            self.assertTrue(past_task["is_urgent"])
            self.assertLess(past_task["days_until_deadline"], 0)
            self.assertEqual(past_task["status_message"], "Задача просрочена")
            self.assertEqual(self.request("GET", "/api/v2/stats/timing")[1]["overtime_pending"], timing_before["overtime_pending"] + 1)

            code, due_today = self.request("POST", base, {"title": "Part5 today test", "is_important": False, "deadline_at": today})
            self.assertEqual(code, 201)
            created_ids.append(due_today["id"])
            self.assertIn(due_today["id"], [task["id"] for task in self.request("GET", f"{base}/today")[1]["tasks"]])

            first = created_ids[0]
            self.assertEqual(self.request("GET", f"{base}/{first}")[1]["title"], "Part5 future test")
            found = self.request("GET", f"{base}/search?q=Part5")[1]["tasks"]
            self.assertTrue(set(created_ids).issubset({task["id"] for task in found}))
            self.assertEqual(self.request("GET", f"{base}/quadrant/Q1")[0], 200)
            self.assertEqual(self.request("GET", f"{base}/status/pending")[0], 200)
            self.assertEqual(self.request("GET", f"{base}/today")[0], 200)
            self.assertEqual(self.request("GET", "/api/v2/stats")[0], 200)
            self.assertEqual(self.request("GET", "/api/v2/stats/timing")[0], 200)
            self.assertEqual(self.request("GET", f"{base}/search?q=notpresentpart5")[0], 404)
            self.assertEqual(self.request("GET", f"{base}/status/invalid")[0], 404)

            code, updated = self.request("PUT", f"{base}/{first}", {"deadline_at": soon})
            self.assertEqual(code, 200)
            self.assertTrue(updated["is_urgent"])
            self.assertEqual(updated["quadrant"], "Q1")
            self.assertEqual(self.request("PUT", f"{base}/{first}", {"title": None})[0], 422)
            code, completed = self.request("PATCH", f"{base}/{first}/complete")
            self.assertEqual(code, 200)
            self.assertTrue(completed["completed"])
            self.assertIsNotNone(completed["completed_at"])
            self.assertEqual(self.request("GET", "/api/v2/stats/timing")[1]["completed_on_time"], timing_before["completed_on_time"] + 1)
            self.assertEqual(self.request("GET", f"{base}/999999999")[0], 404)
            self.assertEqual(self.request("PUT", f"{base}/999999999", {"title": "Missing task"})[0], 404)
            self.assertEqual(self.request("PATCH", f"{base}/999999999/complete")[0], 404)
            self.assertEqual(self.request("DELETE", f"{base}/999999999")[0], 404)
            self.assertEqual(self.request("GET", f"{base}/quadrant/Q5")[0], 400)
            code, naive_task = self.request("POST", base, {"title": "Part5 naive date", "is_important": True, "deadline_at": (now + timedelta(days=5)).replace(tzinfo=None).isoformat()})
            self.assertEqual(code, 201)
            created_ids.append(naive_task["id"])
            self.assertTrue(naive_task["deadline_at"].endswith("Z"))
        finally:
            for task_id in created_ids:
                self.request("DELETE", f"{base}/{task_id}")
            self.assertEqual(self.request("GET", "/api/v2/stats")[1]["total_tasks"], before)


class Part5SchedulerTest(unittest.IsolatedAsyncioTestCase):
    async def test_late_completion_statistics(self):
        from database import AsyncSessionLocal, engine, init_db
        from models import Task
        from models import UserRole
        from routers.stats import get_timing_stats

        await init_db()
        now = datetime.now(timezone.utc)
        task = Task(title="Part5 late completion test", is_important=False, is_urgent=True, quadrant="Q3", completed=True, completed_at=now, deadline_at=now - timedelta(days=1))
        async with AsyncSessionLocal() as db:
            before = await get_timing_stats(db, SimpleNamespace(id=0, role=UserRole.ADMIN))
            db.add(task)
            await db.commit()
            task_id = task.id
        try:
            async with AsyncSessionLocal() as db:
                after = await get_timing_stats(db, SimpleNamespace(id=0, role=UserRole.ADMIN))
            self.assertEqual(after.completed_late, before.completed_late + 1)
        finally:
            async with AsyncSessionLocal() as db:
                await db.delete(await db.get(Task, task_id))
                await db.commit()
            await engine.dispose()

    async def test_calculation_boundaries(self):
        from utils import calculate_days_until_deadline, calculate_urgency, determine_quadrant

        now = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
        self.assertFalse(calculate_urgency(None, now))
        self.assertTrue(calculate_urgency(now + timedelta(days=3), now))
        self.assertFalse(calculate_urgency(now + timedelta(days=3, seconds=1), now))
        self.assertEqual(calculate_days_until_deadline(now + timedelta(hours=1), now), 0)
        self.assertEqual(calculate_days_until_deadline(now - timedelta(days=1), now), -1)
        self.assertIsNone(calculate_days_until_deadline(None, now))
        self.assertEqual([determine_quadrant(a, b) for a, b in ((True, True), (True, False), (False, True), (False, False))], ["Q1", "Q2", "Q3", "Q4"])

    async def test_scheduler_updates_pending_rows_only(self):
        from database import AsyncSessionLocal, engine, init_db
        from models import Task
        from scheduler import update_task_urgency

        await init_db()
        task = Task(title="Part5 scheduler test", is_important=True, is_urgent=False, quadrant="Q2", completed=False, deadline_at=datetime.now(timezone.utc) + timedelta(days=2))
        async with AsyncSessionLocal() as db:
            db.add(task)
            await db.commit()
            task_id = task.id
        try:
            self.assertGreaterEqual(await update_task_urgency(), 1)
            async with AsyncSessionLocal() as db:
                saved = await db.get(Task, task_id)
                self.assertTrue(saved.is_urgent)
                self.assertEqual(saved.quadrant, "Q1")
                saved.completed = True
                saved.is_urgent = False
                saved.quadrant = "Q2"
                await db.commit()
            await update_task_urgency()
            async with AsyncSessionLocal() as db:
                saved = await db.get(Task, task_id)
                self.assertFalse(saved.is_urgent)
                self.assertEqual(saved.quadrant, "Q2")
        finally:
            async with AsyncSessionLocal() as db:
                saved = await db.get(Task, task_id)
                await db.delete(saved)
                await db.commit()
            await engine.dispose()


if __name__ == "__main__":
    unittest.main()
