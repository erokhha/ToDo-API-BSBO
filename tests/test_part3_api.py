import json
import asyncio
import socket
import subprocess
import sys
import time
import unittest
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class Part3ApiTest(unittest.TestCase):
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
        for _ in range(50):
            try:
                cls.request("GET", "/openapi.json")
                return
            except URLError:
                time.sleep(0.1)
        cls.server.terminate()
        raise RuntimeError("API server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=5)

    @classmethod
    def request(cls, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(
            cls.base + path,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method,
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None

    def test_part3_workflow(self):
        tasks = "/api/v1/tasks"
        self.assertEqual(self.request("GET", tasks)[0], 200)
        self.assertEqual(self.request("GET", "/api/v1/stats")[0], 200)
        self.assertEqual(self.request("GET", "/tasks")[0], 404)

        valid = {
            "title": "Write report",
            "description": "Part 3",
            "is_important": True,
            "is_urgent": False,
        }
        before = self.request("GET", tasks)[1]["count"]
        for invalid in (
            {**valid, "title": ""},
            {**valid, "title": "A"},
            {**valid, "title": "A" * 101},
            {**valid, "is_important": [True]},
            {key: value for key, value in valid.items() if key != "title"},
            {**valid, "unexpected": 1},
        ):
            self.assertEqual(self.request("POST", tasks, invalid)[0], 422)
        self.assertEqual(self.request("GET", tasks)[1]["count"], before)

        status, created = self.request("POST", tasks, valid)
        self.assertEqual(status, 201)
        self.assertEqual(created["id"], 5)
        self.assertEqual(created["quadrant"], "Q2")
        self.assertFalse(created["completed"])
        self.assertIn("created_at", created)
        self.assertEqual(self.request("GET", f"{tasks}/5")[1], created)
        self.assertEqual(self.request("GET", tasks)[1]["count"], before + 1)

        status, without_description = self.request(
            "POST", tasks, {"title": "Another task", "is_important": False, "is_urgent": True}
        )
        self.assertEqual(status, 201)
        self.assertIsNone(without_description["description"])
        self.assertEqual(without_description["quadrant"], "Q3")

        status, updated = self.request("PUT", f"{tasks}/5", {"is_urgent": True})
        self.assertEqual(status, 200)
        self.assertEqual(updated["title"], "Write report")
        self.assertEqual(updated["quadrant"], "Q1")
        self.assertEqual(self.request("PUT", f"{tasks}/5", {"title": None})[0], 422)

        status, completed = self.request("PATCH", f"{tasks}/5/complete")
        self.assertEqual(status, 200)
        self.assertTrue(completed["completed"])
        self.assertEqual(self.request("GET", f"{tasks}/5")[1]["completed"], True)
        stats = self.request("GET", "/api/v1/stats")[1]
        self.assertEqual(stats["total_tasks"], before + 2)
        self.assertEqual(stats["by_quadrant"]["Q1"], 2)
        self.assertEqual(stats["by_status"]["completed"], 2)

        self.assertEqual(self.request("DELETE", f"{tasks}/6"), (204, None))
        self.assertEqual(self.request("GET", f"{tasks}/6")[0], 404)
        self.assertEqual(self.request("GET", "/api/v1/stats")[1]["total_tasks"], before + 1)
        for method, path, body in (
            ("GET", f"{tasks}/999", None),
            ("PUT", f"{tasks}/999", {"title": "Missing task"}),
            ("PATCH", f"{tasks}/999/complete", None),
            ("DELETE", f"{tasks}/999", None),
        ):
            self.assertEqual(self.request(method, path, body)[0], 404)

    def test_completion_timestamp_is_stored(self):
        from database import tasks_db
        from routers.tasks import complete_task

        task = next(item for item in tasks_db if item["id"] == 3)
        original_status = task["completed"]
        original_time = task.get("completed_at")
        try:
            asyncio.run(complete_task(3))
            self.assertTrue(task["completed"])
            self.assertIsInstance(task["completed_at"], datetime)
        finally:
            task["completed"] = original_status
            if original_time is None:
                task.pop("completed_at", None)
            else:
                task["completed_at"] = original_time


if __name__ == "__main__":
    unittest.main()
