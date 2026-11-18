import json
import os
import socket
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import psycopg2
from dotenv import load_dotenv
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class Part6AuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as address:
            address.bind(("127.0.0.1", 0))
            cls.port = address.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
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
    def request(cls, method, path, body=None, token=None, form=False):
        if form:
            data = urlencode(body).encode()
            content_type = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode() if body is not None else None
            content_type = "application/json"
        headers = {"Content-Type": content_type}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(cls.base + path, data=data, headers=headers, method=method)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None

    @staticmethod
    def database():
        url = make_url(os.environ["DATABASE_URL"])
        return psycopg2.connect(
            host=url.host,
            port=url.port,
            user=url.username,
            password=url.password,
            dbname=url.database,
        )

    def test_auth_and_ownership_workflow(self):
        suffix = uuid4().hex[:10]
        password = "TestPassword6!"
        new_password = "NewPassword6!"
        users = []
        auth = "/api/v2/auth"
        tasks = "/api/v2/tasks"
        try:
            with self.database() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT id, title FROM tasks WHERE id BETWEEN 1 AND 8 ORDER BY id")
                    original = cursor.fetchall()
            self.assertEqual(len(original), 8)

            for name in ("alpha", "beta", "admin"):
                body = {
                    "nickname": f"{name}_{suffix}",
                    "email": f"{name}_{suffix}@example.com",
                    "password": password,
                }
                code, user = self.request("POST", f"{auth}/register", body)
                self.assertEqual(code, 201)
                users.append((body, user))
                self.assertEqual(user["role"], "user")
                self.assertNotIn("password", user)
                self.assertNotIn("hashed_password", user)

            self.assertEqual(self.request("POST", f"{auth}/register", {**users[0][0], "nickname": f"other_{suffix}"})[0], 400)
            self.assertEqual(self.request("POST", f"{auth}/register", {**users[0][0], "email": f"other_{suffix}@example.com"})[0], 400)
            self.assertEqual(self.request("POST", f"{auth}/register", {"nickname": "x", "email": "bad", "password": "short"})[0], 422)

            with self.database() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE users SET role = 'admin' WHERE id = %s", (users[2][1]["id"],))
                    cursor.execute("SELECT hashed_password FROM users WHERE id = %s", (users[0][1]["id"],))
                    self.assertNotEqual(cursor.fetchone()[0], password)

            tokens = []
            for body, user in users:
                code, payload = self.request("POST", f"{auth}/login", {"username": body["email"], "password": password}, form=True)
                self.assertEqual(code, 200)
                self.assertEqual(payload["token_type"], "bearer")
                tokens.append(payload["access_token"])
                self.assertEqual(self.request("GET", f"{auth}/me", token=tokens[-1])[1]["id"], user["id"])
            self.assertEqual(self.request("POST", f"{auth}/login", {"username": users[0][0]["email"], "password": "wrong"}, form=True)[0], 401)
            self.assertEqual(self.request("GET", f"{auth}/me")[0], 401)
            self.assertEqual(self.request("GET", f"{auth}/me", token="invalid.token.value")[0], 401)
            self.assertEqual(self.request("GET", tasks)[0], 401)
            self.assertEqual(self.request("GET", "/api/v2/stats")[0], 401)

            from jose import jwt
            from auth_utils import create_access_token

            expired = create_access_token(users[0][1]["id"], timedelta(seconds=-1))
            self.assertEqual(self.request("GET", f"{auth}/me", token=expired)[0], 401)
            forged = jwt.encode({"sub": str(users[0][1]["id"]), "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-secret", algorithm="HS256")
            self.assertEqual(self.request("GET", f"{auth}/me", token=forged)[0], 401)

            today = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
            tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
            code, first = self.request("POST", tasks, {"title": f"Alpha {suffix}", "is_important": True, "deadline_at": today}, tokens[0])
            self.assertEqual(code, 201)
            code, second = self.request("POST", tasks, {"title": f"Beta {suffix}", "is_important": False, "deadline_at": tomorrow}, tokens[1])
            self.assertEqual(code, 201)
            self.assertEqual(first["user_id"], users[0][1]["id"])
            self.assertEqual(second["user_id"], users[1][1]["id"])

            for index, own, foreign in ((0, first, second), (1, second, first)):
                token = tokens[index]
                self.assertEqual([task["id"] for task in self.request("GET", tasks, token=token)[1]["tasks"]], [own["id"]])
                self.assertEqual([task["id"] for task in self.request("GET", f"{tasks}/search?q={suffix}", token=token)[1]["tasks"]], [own["id"]])
                self.assertEqual(self.request("GET", f"{tasks}/quadrant/{own['quadrant']}", token=token)[1]["count"], 1)
                self.assertEqual(self.request("GET", f"{tasks}/status/pending", token=token)[1]["count"], 1)
                self.assertEqual(self.request("GET", "/api/v2/stats", token=token)[1]["total_tasks"], 1)
                self.assertEqual(self.request("GET", "/api/v2/stats/timing", token=token)[1]["on_plan_pending"], 1)
                self.assertEqual(self.request("GET", f"{tasks}/{foreign['id']}", token=token)[0], 403)
                self.assertEqual(self.request("PUT", f"{tasks}/{foreign['id']}", {"title": "Forbidden update"}, token)[0], 403)
                self.assertEqual(self.request("PATCH", f"{tasks}/{foreign['id']}/complete", token=token)[0], 403)
                self.assertEqual(self.request("DELETE", f"{tasks}/{foreign['id']}", token=token)[0], 403)
            self.assertEqual([task["id"] for task in self.request("GET", f"{tasks}/today", token=tokens[0])[1]["tasks"]], [first["id"]])
            self.assertEqual(self.request("GET", f"{tasks}/today", token=tokens[1])[1]["count"], 0)
            self.assertEqual(self.request("GET", f"{tasks}/999999999", token=tokens[0])[0], 404)
            self.assertEqual(self.request("GET", f"{tasks}/{second['id']}", token=tokens[1])[1]["title"], second["title"])

            admin_tasks = self.request("GET", tasks, token=tokens[2])[1]["tasks"]
            self.assertTrue({first["id"], second["id"]}.issubset({task["id"] for task in admin_tasks}))
            self.assertEqual(self.request("GET", f"{tasks}/{first['id']}", token=tokens[2])[0], 200)
            self.assertTrue({first["id"], second["id"]}.issubset({task["id"] for task in self.request("GET", f"{tasks}/search?q={suffix}", token=tokens[2])[1]["tasks"]}))
            self.assertTrue({first["id"], second["id"]}.issubset({task["id"] for task in self.request("GET", f"{tasks}/status/pending", token=tokens[2])[1]["tasks"]}))
            self.assertIn(first["id"], [task["id"] for task in self.request("GET", f"{tasks}/today", token=tokens[2])[1]["tasks"]])
            self.assertGreaterEqual(self.request("GET", "/api/v2/stats", token=tokens[2])[1]["total_tasks"], 2)
            self.assertGreaterEqual(self.request("GET", "/api/v2/stats/timing", token=tokens[2])[1]["on_plan_pending"], 2)
            self.assertEqual(self.request("PUT", f"{tasks}/{second['id']}", {"is_important": True}, tokens[2])[0], 200)
            self.assertEqual(self.request("GET", f"{tasks}/{second['id']}", token=tokens[1])[1]["is_important"], True)
            self.assertIn(second["id"], [task["id"] for task in self.request("GET", f"{tasks}/quadrant/Q1", token=tokens[2])[1]["tasks"]])
            self.assertEqual(self.request("GET", "/api/v2/admin/users", token=tokens[0])[0], 403)
            code, roster = self.request("GET", "/api/v2/admin/users", token=tokens[2])
            self.assertEqual(code, 200)
            counts = {user["id"]: user["task_count"] for user in roster}
            self.assertEqual(counts[users[0][1]["id"]], 1)
            self.assertEqual(counts[users[1][1]["id"]], 1)

            self.assertEqual(self.request("PATCH", f"{auth}/change-password", {"old_password": "wrong", "new_password": new_password}, tokens[0])[0], 401)
            self.assertEqual(self.request("PATCH", f"{auth}/change-password", {"old_password": password, "new_password": "short"}, tokens[0])[0], 422)
            self.assertEqual(self.request("PATCH", f"{auth}/change-password", {"old_password": password, "new_password": new_password})[0], 401)
            self.assertEqual(self.request("PATCH", f"{auth}/change-password", {"old_password": password, "new_password": new_password}, tokens[0])[0], 200)
            self.assertEqual(self.request("POST", f"{auth}/login", {"username": users[0][0]["email"], "password": password}, form=True)[0], 401)
            self.assertEqual(self.request("POST", f"{auth}/login", {"username": users[0][0]["email"], "password": new_password}, form=True)[0], 200)

            with self.database() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT id, title FROM tasks WHERE id BETWEEN 1 AND 8 ORDER BY id")
                    self.assertEqual(cursor.fetchall(), original)
                    cursor.execute("SELECT user_id FROM tasks WHERE id IN (%s, %s) ORDER BY id", (first["id"], second["id"]))
                    self.assertEqual([row[0] for row in cursor.fetchall()], [users[0][1]["id"], users[1][1]["id"]])
                    cursor.execute("SELECT 1 FROM pg_constraint WHERE conrelid = 'tasks'::regclass AND confrelid = 'users'::regclass AND contype = 'f'")
                    self.assertIsNotNone(cursor.fetchone())
            self.assertEqual(self.request("PATCH", f"{tasks}/{second['id']}/complete", token=tokens[2])[1]["completed"], True)
            self.assertEqual(self.request("DELETE", f"{tasks}/{second['id']}", token=tokens[2])[0], 204)
            self.assertEqual(self.request("GET", f"{tasks}/{second['id']}", token=tokens[1])[0], 404)
        finally:
            if users:
                with self.database() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM users WHERE id = ANY(%s)", ([user["id"] for _, user in users],))


if __name__ == "__main__":
    unittest.main()
