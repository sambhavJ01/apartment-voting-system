"""
Locust load test — Apartment Voting System.

Simulates three user types:
  VoterUser      — typical voter: login → browse topics → vote (with OTP)
  ReadOnlyViewer — resident who only reads active topics and results
  AdminUser      — admin polling the dashboard and listing users

Prerequisites:
  1. Backend running:  uvicorn backend.main:app --port 8000
  2. OTP_PROVIDER=console  (OTP printed to server stdout, included in API response)
  3. Database seeded:   python -m scripts.seed_data

Run:
  locust -f tests/locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10

Target acceptance criteria (from requirements):
  - p95 response time < 2 000 ms for all endpoints
  - Zero HTTP 5xx errors
  - No duplicate votes (enforced by DB UNIQUE constraint)
"""
import random
import string
from locust import HttpUser, SequentialTaskSet, between, task, events

# ─── Credentials from seed_data.py ───────────────────────────────────────────
VOTER_CREDENTIALS = [
    {"phone_number": "+919000000001", "password": "Test@1234"},
    {"phone_number": "+919000000002", "password": "Test@1234"},
    {"phone_number": "+919000000003", "password": "Test@1234"},
    {"phone_number": "+919000000004", "password": "Test@1234"},
    {"phone_number": "+919000000005", "password": "Test@1234"},
    {"phone_number": "+919000000006", "password": "Test@1234"},
]

ADMIN_CREDS = {"phone_number": "+919000000000", "password": "Admin@1234"}


# ─── Voter flow (sequential) ──────────────────────────────────────────────────

class VoterTaskSet(SequentialTaskSet):
    """
    Simulates a full resident voter session:
      1. Login → JWT token
      2. List active topics
      3. Initiate vote (sends OTP; debug_otp returned in console mode)
      4. Cast vote with OTP
      5. View results
    """

    def on_start(self):
        creds = random.choice(VOTER_CREDENTIALS)
        resp = self.client.post(
            "/auth/login",
            json=creds,
            name="/auth/login",
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get("access_token", "")
            self.headers = {"Authorization": f"Bearer {self.token}"}
            self.voted_topics: set[int] = set()
        else:
            self.token = ""
            self.headers = {}
            self.voted_topics = set()

    @task
    def list_topics(self):
        resp = self.client.get("/vote/topics", headers=self.headers, name="/vote/topics")
        if resp.status_code == 200:
            self.active_topics = resp.json()
        else:
            self.active_topics = []

    @task
    def vote_on_topic(self):
        if not getattr(self, "active_topics", None):
            return

        # Pick a topic the simulated user hasn't voted on yet in this run
        eligible = [
            t for t in self.active_topics
            if not t.get("has_voted") and t["id"] not in self.voted_topics
        ]
        if not eligible:
            return

        topic = random.choice(eligible)
        options = topic.get("options", [])
        if not options:
            return
        option = random.choice(options)

        # Phase 1: initiate (triggers OTP, returns debug_otp in console mode)
        resp = self.client.post(
            "/vote/initiate",
            json={"topic_id": topic["id"], "option_id": option["id"]},
            headers=self.headers,
            name="/vote/initiate",
        )
        if resp.status_code not in (200, 201):
            return

        debug_otp = resp.json().get("debug_otp")
        if not debug_otp:
            # In real WhatsApp mode, the OTP arrives externally; skip for load test
            return

        # Phase 2: cast vote with the debug OTP
        cast_resp = self.client.post(
            "/vote/cast",
            json={
                "topic_id": topic["id"],
                "option_id": option["id"],
                "otp": debug_otp,
            },
            headers=self.headers,
            name="/vote/cast",
        )
        if cast_resp.status_code == 200:
            self.voted_topics.add(topic["id"])

    @task
    def view_results(self):
        if not getattr(self, "active_topics", None):
            return
        topic = random.choice(self.active_topics)
        self.client.get(
            f"/vote/topics/{topic['id']}/results",
            headers=self.headers,
            name="/vote/topics/{id}/results",
        )


# ─── Read-only viewer ─────────────────────────────────────────────────────────

class ReadOnlyTaskSet(SequentialTaskSet):
    """Lightweight user who only browses topics and results."""

    def on_start(self):
        creds = random.choice(VOTER_CREDENTIALS)
        resp = self.client.post("/auth/login", json=creds, name="/auth/login [ro]")
        if resp.status_code == 200:
            self.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
            self.topic_ids = []
        else:
            self.headers = {}
            self.topic_ids = []

    @task(3)
    def list_topics(self):
        resp = self.client.get("/vote/topics", headers=self.headers, name="/vote/topics [ro]")
        if resp.status_code == 200:
            self.topic_ids = [t["id"] for t in resp.json()]

    @task(1)
    def view_results(self):
        if not self.topic_ids:
            return
        tid = random.choice(self.topic_ids)
        self.client.get(
            f"/vote/topics/{tid}/results",
            headers=self.headers,
            name="/vote/topics/{id}/results [ro]",
        )


# ─── Admin ────────────────────────────────────────────────────────────────────

class AdminTaskSet(SequentialTaskSet):
    """Admin polling dashboard and user lists."""

    def on_start(self):
        resp = self.client.post("/auth/login", json=ADMIN_CREDS, name="/auth/login [admin]")
        if resp.status_code == 200:
            self.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        else:
            self.headers = {}

    @task(2)
    def dashboard(self):
        self.client.get("/admin/dashboard", headers=self.headers, name="/admin/dashboard")

    @task(1)
    def list_users(self):
        self.client.get("/admin/users", headers=self.headers, name="/admin/users")

    @task(1)
    def list_topics(self):
        self.client.get("/admin/topics", headers=self.headers, name="/admin/topics")

    @task(1)
    def metrics(self):
        self.client.get("/metrics", name="/metrics")


# ─── User classes ─────────────────────────────────────────────────────────────

class VoterUser(HttpUser):
    """Simulates ~80% of load — real voters casting votes."""
    tasks = [VoterTaskSet]
    weight = 8
    wait_time = between(1, 3)   # realistic think-time between actions


class ReadOnlyUser(HttpUser):
    """Simulates ~15% of load — passive residents checking results."""
    tasks = [ReadOnlyTaskSet]
    weight = 2
    wait_time = between(2, 5)


class AdminUser(HttpUser):
    """Simulates ~5% of load — admin operational monitoring."""
    tasks = [AdminTaskSet]
    weight = 1
    wait_time = between(5, 15)
