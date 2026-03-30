"""
scripts/init_db.py
Initialise the database — creates all tables (safe to run multiple times).

Usage:
    python -m scripts.init_db
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db

if __name__ == "__main__":
    print("Creating database tables …")
    init_db()
    print("Done. Database is ready at voting_system.db")
