import os
import uuid
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import TaskCreate, TaskResult, AgentEvent, AgentInfo
from .agents import ROLES
from .graph import run_company
from .llm import get_mode
from . import db as store

app = FastAPI(title="AI Agent Company", version="0.1.0")

frontend = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend, "http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TASKS: dict[str, TaskResult] = {}


@app.get("/api/health")
def health():
    return {"ok": True, "llm_mode": get_mode(), "db": "postgres" if store.USE_DB else "memory"}


@app.get("/api/agents", response_model=list[AgentInfo])
def list_agents():
    return [AgentInfo(**{k: r[k] for k in ("id", "name", "emoji", "description")}) for r in ROLES]


@app.post("/api/tasks", response_model=TaskResult)
def create_task(body: TaskCreate):
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(400, "goal is required")
    tid = uuid.uuid4().hex[:8]
    task = TaskResult(id=tid, goal=goal, status="running")
    TASKS[tid] = task
    store.save_task(task)
    try:
        final = run_company(goal, max_revisions=body.max_revisions)
    except Exception as e:
        task.status = "failed"
        task.final_report = f"실패: {e}"
        TASKS[tid] = task
        store.save_task(task)
        raise HTTPException(500, str(e))
    name_map = {r["id"]: r["name"] for r in ROLES}
    events = [
        AgentEvent(
            agent=e["agent"],
            name=name_map.get(e["agent"], e["agent"]),
            status="done",
            output=e["output"],
            step=e.get("step", i + 1),
        )
        for i, e in enumerate(final.get("log", []))
    ]
    task.status = "done"
    task.events = events
    task.final_report = final.get("report", "")
    task.approved = bool(final.get("approved", False))
    TASKS[tid] = task
    store.save_task(task)
    return task


@app.get("/api/tasks/{tid}", response_model=TaskResult)
def get_task(tid: str):
    if store.USE_DB:
        found = store.load_task(tid)
        if found is not None:
            return found
    if tid not in TASKS:
        raise HTTPException(404, "task not found")
    return TASKS[tid]


@app.get("/api/tasks", response_model=list[TaskResult])
def list_tasks():
    if store.USE_DB:
        rows = store.load_all_tasks()
        if rows is not None:
            return rows
    return list(TASKS.values())
