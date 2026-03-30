from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    if settings.DATABASE_URL.startswith("sqlite"):
        # QueuePool — allows multiple concurrent connections within each gunicorn worker.
        # StaticPool (the old default) serialises all requests to a single connection,
        # causing severe bottlenecks under concurrent load.
        # SQLite WAL mode lets multiple readers proceed in parallel; writers are
        # serialised by SQLite itself — no ORM change needed.
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            pool_size=10,         # idle connections kept per worker process
            max_overflow=20,      # burst: up to 30 concurrent connections per worker
            pool_timeout=10,      # wait max 10 s for a free connection
            pool_pre_ping=True,   # discard stale connections silently
            pool_recycle=1800,    # recycle after 30 min to avoid sqlite file-handle leaks
        )

        @event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")    # concurrent readers
            cursor.execute("PRAGMA foreign_keys=ON")     # enforce FK constraints
            cursor.execute("PRAGMA busy_timeout=5000")   # wait up to 5 s on write-lock
            cursor.execute("PRAGMA synchronous=NORMAL")  # safe + fast under WAL
            cursor.execute("PRAGMA cache_size=-8000")    # 8 MB page cache per connection
            cursor.close()

    else:
        # PostgreSQL / MySQL — connection pool tuned for ~4-8 gunicorn workers
        engine = create_engine(
            settings.DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_timeout=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create all tables. Import models first so they register with Base."""
    from backend.models import apartment, user, otp, topic, vote, audit  # noqa: F401
    Base.metadata.create_all(bind=engine)
