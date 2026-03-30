"""
scripts/seed_data.py
Populates the database with:
  - 5 sample apartments (101 – 105)
  - 1 admin user
  - 6 sample voters (pre-approved with known passwords)
  - 2 voting topics (one anonymous, one identified)

NOTE: Run ONCE on a fresh database.  Running again will skip duplicates gracefully.

Usage:
    python -m scripts.seed_data
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, SessionLocal
from backend.models.apartment import Apartment
from backend.models.user import User, UserStatus
from backend.models.topic import Topic, Option, VotingMode, TopicStatus
from backend.services.auth_service import hash_password
from backend.config import settings

# ─── Configuration ────────────────────────────────────────────────────────────

APARTMENTS = [
    {"apartment_number": "101", "max_allowed_voters": 3},
    {"apartment_number": "102", "max_allowed_voters": 3},
    {"apartment_number": "103", "max_allowed_voters": 3},
    {"apartment_number": "104", "max_allowed_voters": 3},
    {"apartment_number": "105", "max_allowed_voters": 3},
    {"apartment_number": "Admin", "max_allowed_voters": 1},
]

# Voters — known password "Test@1234" (for demo only)
DEMO_PASSWORD = "Test@1234"
VOTERS = [
    {"name": "Priya Sharma",   "apartment_number": "101", "phone_number": "+919000000001"},
    {"name": "Raj Patel",      "apartment_number": "101", "phone_number": "+919000000002"},
    {"name": "Anjali Singh",   "apartment_number": "102", "phone_number": "+919000000003"},
    {"name": "Vikram Nair",    "apartment_number": "103", "phone_number": "+919000000004"},
    {"name": "Deepa Menon",    "apartment_number": "104", "phone_number": "+919000000005"},
    {"name": "Arjun Reddy",    "apartment_number": "105", "phone_number": "+919000000006"},
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
        "options": ["Approve the 10% hike", "Reject the hike", "Defer decision by 3 months"],
    },
    {
        "title": "Election: Resident Welfare Association President",
        "description": (
            "Cast your vote for the next RWA president for the term 2026–2028."
        ),
        "mode": VotingMode.IDENTIFIED,
        "status": TopicStatus.DRAFT,
        "options": ["Candidate A — Sunita Agarwal", "Candidate B — Mohan Kumar",
                    "Candidate C — Kavitha Iyer"],
    },
]


# ─── Main seed logic ──────────────────────────────────────────────────────────

def seed():
    print("Initialising database …")
    init_db()

    db = SessionLocal()

    try:
        # ── Apartments ────────────────────────────────────────────────────────
        apt_map: dict[str, Apartment] = {}
        for apt_data in APARTMENTS:
            apt = db.query(Apartment).filter(
                Apartment.apartment_number == apt_data["apartment_number"]
            ).first()
            if not apt:
                apt = Apartment(**apt_data)
                db.add(apt)
                db.flush()
                print(f"  Created apartment: {apt_data['apartment_number']}")
            else:
                print(f"  Apartment already exists: {apt_data['apartment_number']}")
            apt_map[apt_data["apartment_number"]] = apt
        db.commit()

        # ── Admin ─────────────────────────────────────────────────────────────
        admin_apt = apt_map["Admin"]
        admin_user = db.query(User).filter(
            User.phone_number == ADMIN["phone_number"]
        ).first()
        if not admin_user:
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
            print(f"  Created admin: {ADMIN['name']} / password: {ADMIN['password']}")
        else:
            print(f"  Admin already exists: {ADMIN['name']}")

        # ── Voters ────────────────────────────────────────────────────────────
        for v in VOTERS:
            existing = db.query(User).filter(User.phone_number == v["phone_number"]).first()
            if not existing:
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
                print(f"  Created voter: {v['name']} ({v['phone_number']}) / password: {DEMO_PASSWORD}")
            else:
                print(f"  Voter already exists: {v['name']}")
        db.commit()

        # ── Topics ────────────────────────────────────────────────────────────
        for topic_data in TOPICS:
            existing = db.query(Topic).filter(Topic.title == topic_data["title"]).first()
            if not existing:
                topic = Topic(
                    title=topic_data["title"],
                    description=topic_data["description"],
                    mode=topic_data["mode"],
                    status=topic_data["status"],
                    created_by_id=admin_user.id,
                )
                db.add(topic)
                db.flush()
                for i, opt_text in enumerate(topic_data["options"]):
                    db.add(Option(topic_id=topic.id, text=opt_text, order=i))
                print(f"  Created topic: {topic_data['title']}")
            else:
                print(f"  Topic already exists: {topic_data['title']}")
        db.commit()

    finally:
        db.close()

    print("\n✅ Seed complete!")
    print("\n─── Demo Credentials ──────────────────────────────────────")
    print(f"  Admin   : phone={ADMIN['phone_number']}  password={ADMIN['password']}")
    print(f"  Voter 1 : phone=+919000000001          password={DEMO_PASSWORD}")
    print(f"  Voter 2 : phone=+919000000002          password={DEMO_PASSWORD}")
    print("────────────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    seed()
