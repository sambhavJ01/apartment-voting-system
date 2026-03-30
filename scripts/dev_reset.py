"""
scripts/dev_reset.py
────────────────────────────────────────────────────────────────────────────────
Full development database reset.

  1. Drops all tables (or deletes the SQLite file)
  2. Recreates all tables (including new ones like topic_observers)
  3. Seeds fresh demo data — apartments, admin, 6 voters, 2 topics

Usage:
    python -m scripts.dev_reset          # wipe & reseed
    python -m scripts.dev_reset --keep   # keep schema, only truncate data

After running:
  Admin   : +919000000000  /  Admin@1234
  Voters  : +91900000000{1-6}  /  Test@1234
  Topic 1 : "Society Maintenance Hike Decision" (anonymous, ACTIVE)
  Topic 2 : "RWA President Election" (identified, DRAFT)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all models so SQLAlchemy is aware of every table
from backend.database import Base, SessionLocal, engine, init_db  # noqa: E402
import backend.models.apartment  # noqa: F401
import backend.models.user       # noqa: F401
import backend.models.otp        # noqa: F401  (OTPLog)
import backend.models.topic      # noqa: F401
import backend.models.vote       # noqa: F401
import backend.models.audit      # noqa: F401

from backend.models.apartment import Apartment
from backend.models.topic import Option, Topic, TopicStatus, VotingMode
from backend.models.user import User, UserStatus
from backend.services.auth_service import hash_password


# ─── Demo data ────────────────────────────────────────────────────────────────

APARTMENTS = [
    {"apartment_number": "101", "max_allowed_voters": 3},
    {"apartment_number": "102", "max_allowed_voters": 3},
    {"apartment_number": "103", "max_allowed_voters": 3},
    {"apartment_number": "104", "max_allowed_voters": 3},
    {"apartment_number": "105", "max_allowed_voters": 3},
    {"apartment_number": "Admin", "max_allowed_voters": 1},
]

DEMO_PASSWORD = "Test@1234"

VOTERS = [
    {"name": "Priya Sharma",  "apartment_number": "101", "phone_number": "+919000000001"},
    {"name": "Raj Patel",     "apartment_number": "101", "phone_number": "+919000000002"},
    {"name": "Anjali Singh",  "apartment_number": "102", "phone_number": "+919000000003"},
    {"name": "Vikram Nair",   "apartment_number": "103", "phone_number": "+919000000004"},
    {"name": "Deepa Menon",   "apartment_number": "104", "phone_number": "+919000000005"},
    {"name": "Arjun Reddy",   "apartment_number": "105", "phone_number": "+919000000006"},
]

ADMIN = {
    "name": "Society Admin",
    "apartment_number": "Admin",
    "phone_number": "+919000000000",
    "password": "Admin@1234",
}

TOPICS = [
    {
        "title": "Society Maintenance Hike Decision",
        "description": (
            "Members are requested to vote on the proposed 10% increase "
            "in monthly maintenance charges to fund elevator upgrades and CCTV installation."
        ),
        "mode": VotingMode.ANONYMOUS,
        "status": TopicStatus.ACTIVE,
        "options": [
            "Approve the 10% hike",
            "Reject the hike",
            "Defer decision by 3 months",
        ],
    },
    {
        "title": "RWA President Election 2026–2028",
        "description": "Cast your vote for the next Resident Welfare Association president.",
        "mode": VotingMode.IDENTIFIED,
        "status": TopicStatus.DRAFT,
        "options": [
            "Candidate A — Sunita Agarwal",
            "Candidate B — Mohan Kumar",
            "Candidate C — Kavitha Iyer",
        ],
    },
]


# ─── Reset helpers ────────────────────────────────────────────────────────────

def _drop_all():
    """Drop every table in reverse-dependency order."""
    print("  Dropping all tables …")
    Base.metadata.drop_all(bind=engine)
    print("  Tables dropped.")


def _create_all():
    """Create tables from current models."""
    print("  Creating tables …")
    Base.metadata.create_all(bind=engine)
    print("  Tables created.")


def _seed(db) -> None:
    # ── Apartments ──────────────────────────────────────────────────────────
    print("\n  Seeding apartments …")
    apt_map: dict[str, Apartment] = {}
    for data in APARTMENTS:
        apt = Apartment(**data)
        db.add(apt)
        db.flush()
        apt_map[data["apartment_number"]] = apt
        print(f"    ✔ Apt {data['apartment_number']}")
    db.commit()

    # ── Admin ────────────────────────────────────────────────────────────────
    print("\n  Seeding admin …")
    admin_apt = apt_map[ADMIN["apartment_number"]]
    admin_user = User(
        name=ADMIN["name"],
        apartment_id=admin_apt.id,
        phone_number=ADMIN["phone_number"],
        password_hash=hash_password(ADMIN["password"]),
        status=UserStatus.APPROVED,
        is_active=True,
        is_admin=True,
    )
    db.add(admin_user)
    db.commit()
    print(f"    ✔ {ADMIN['name']}  phone={ADMIN['phone_number']}  password={ADMIN['password']}")

    # ── Voters ───────────────────────────────────────────────────────────────
    print("\n  Seeding voters …")
    for v in VOTERS:
        apt = apt_map[v["apartment_number"]]
        user = User(
            name=v["name"],
            apartment_id=apt.id,
            phone_number=v["phone_number"],
            password_hash=hash_password(DEMO_PASSWORD),
            status=UserStatus.APPROVED,
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        print(f"    ✔ {v['name']:<20} {v['phone_number']}  password={DEMO_PASSWORD}")
    db.commit()

    # ── Topics ───────────────────────────────────────────────────────────────
    print("\n  Seeding topics …")
    for t in TOPICS:
        topic = Topic(
            title=t["title"],
            description=t["description"],
            mode=t["mode"],
            status=t["status"],
            created_by_id=admin_user.id,
        )
        db.add(topic)
        db.flush()
        for i, text in enumerate(t["options"]):
            db.add(Option(topic_id=topic.id, text=text, order=i))
        mode_label = "anonymous" if t["mode"] == VotingMode.ANONYMOUS else "identified"
        print(f"    ✔ [{topic.status.value.upper():6}] {t['title']}  ({mode_label})")
    db.commit()


# ─── Entry point ──────────────────────────────────────────────────────────────

def reset(keep_schema: bool = False) -> None:
    print("\n╔══════════════════════════════════════════╗")
    print("║   Dev DB Reset — Apartment Voting System ║")
    print("╚══════════════════════════════════════════╝\n")

    if keep_schema:
        print("Mode: truncate data only (keep schema)\n")
        db = SessionLocal()
        try:
            # Delete in FK-safe order
            from backend.models.vote import Vote, VoteTracking
            from backend.models.otp import OTPLog
            from backend.models.audit import AuditLog
            from backend.models.topic import topic_observers
            db.execute(topic_observers.delete())
            db.query(Vote).delete()
            db.query(VoteTracking).delete()
            db.query(OTPLog).delete()
            db.query(AuditLog).delete()
            db.query(Option).delete()
            db.query(Topic).delete()
            db.query(User).delete()
            db.query(Apartment).delete()
            db.commit()
            print("  All rows deleted.")
            _seed(db)
        finally:
            db.close()
    else:
        print("Mode: drop & recreate all tables\n")
        _drop_all()
        _create_all()
        db = SessionLocal()
        try:
            _seed(db)
        finally:
            db.close()

    print("\n──────────────────────────────────────────────────────────────")
    print("✅ Reset complete!  Fresh test data is ready.\n")
    print("  Credentials")
    print(f"  Admin  : {ADMIN['phone_number']}  /  {ADMIN['password']}")
    for i, v in enumerate(VOTERS, 1):
        print(f"  Voter{i} : {v['phone_number']}  /  {DEMO_PASSWORD}  ({v['name']})")
    print("──────────────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset dev database")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep schema, only truncate and re-seed data (faster)",
    )
    args = parser.parse_args()
    reset(keep_schema=args.keep)
