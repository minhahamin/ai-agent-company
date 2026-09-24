"""Task persistence: Postgres when DATABASE_URL is set, else in-memory.

Railway Postgres plugin injects DATABASE_URL automatically.
"""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy needs the postgresql:// scheme
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

USE_DB = bool(DATABASE_URL)

_engine = None
_SessionLocal = None

if USE_DB:
    from sqlalchemy import Column, String, Text, Boolean, JSON, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    Base = declarative_base()

    class TaskRow(Base):
        __tablename__ = "tasks"
        id = Column(String(32), primary_key=True)
        goal = Column(Text, nullable=False, default="")
        status = Column(String(16), nullable=False, default="running")
        events = Column(JSON, nullable=False, default=list)
        final_report = Column(Text, nullable=False, default="")
        approved = Column(Boolean, nullable=False, default=False)

    _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def save_task(task) -> None:
    """Upsert a TaskResult. No-op fallback to caller-side memory store."""
    if not USE_DB:
        return
    data = task.model_dump()
    with _SessionLocal() as s:
        row = s.get(TaskRow, data["id"])
        if row is None:
            row = TaskRow(id=data["id"])
            s.add(row)
        row.goal = data["goal"]
        row.status = data["status"]
        row.events = data["events"]
        row.final_report = data["final_report"]
        row.approved = data["approved"]
        s.commit()


def load_task(tid: str):
    if not USE_DB:
        return None
    from .schemas import TaskResult

    with _SessionLocal() as s:
        row = s.get(TaskRow, tid)
        if row is None:
            return None
        return TaskResult(
            id=row.id,
            goal=row.goal,
            status=row.status,
            events=row.events or [],
            final_report=row.final_report or "",
            approved=bool(row.approved),
        )


def load_all_tasks():
    if not USE_DB:
        return None
    from .schemas import TaskResult

    with _SessionLocal() as s:
        rows = s.query(TaskRow).order_by(TaskRow.id).all()
        return [
            TaskResult(
                id=r.id,
                goal=r.goal,
                status=r.status,
                events=r.events or [],
                final_report=r.final_report or "",
                approved=bool(r.approved),
            )
            for r in rows
        ]
