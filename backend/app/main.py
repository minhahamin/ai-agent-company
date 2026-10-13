import os
import uuid
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from .schemas import TaskCreate, TaskResult, ResumeBody, AgentInfo
from .agents import ROLES
from . import runner
from .llm import get_mode
from . import llm as llm_state
from . import db as store
from .artifacts import build_zip

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
    return {"ok": True, "llm_mode": get_mode(), "model": llm_state.last_model or None, "db": "postgres" if store.USE_DB else "memory"}


@app.get("/api/agents", response_model=list[AgentInfo])
def list_agents():
    return [AgentInfo(**{k: r[k] for k in ("id", "name", "emoji", "description")}) for r in ROLES]


@app.post("/api/tasks", response_model=TaskResult)
def create_task(body: TaskCreate):
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(400, "goal is required")
    tid = uuid.uuid4().hex[:8]
    task = TaskResult(id=tid, goal=goal, status="running", interactive=body.interactive)
    TASKS[tid] = task
    store.save_task(task)
    runner.start(task, body.max_revisions)
    return task


@app.post("/api/tasks/{tid}/resume", response_model=TaskResult)
def resume_task(tid: str, body: ResumeBody):
    task = TASKS.get(tid)
    if task is None:
        raise HTTPException(404, "task not found (server restarted?)")
    if task.status != "waiting":
        raise HTTPException(409, "task is not waiting for input")
    runner.resume(task, body.action, body.feedback, body.roles)
    return task


def _view(task: TaskResult) -> TaskResult:
    """Tasks still marked running/waiting but unknown to this process were cut off by a restart."""
    if task.status in ("running", "waiting") and task.id not in TASKS:
        return task.model_copy(update={"status": "failed", "pending": None})
    return task


@app.get("/api/tasks/{tid}", response_model=TaskResult)
def get_task(tid: str):
    if tid in TASKS:
        return TASKS[tid]
    if store.USE_DB:
        found = store.load_task(tid)
        if found is not None:
            return _view(found)
    raise HTTPException(404, "task not found")


@app.get("/api/tasks", response_model=list[TaskResult])
def list_tasks():
    rows = store.load_all_tasks() if store.USE_DB else None
    if rows is None:
        return list(TASKS.values())
    return [TASKS.get(r.id) or _view(r) for r in rows]


@app.get("/api/tasks/{tid}/download")
def download_task(tid: str):
    task = get_task(tid)
    return Response(
        build_zip(task),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="task-{tid}.zip"'},
    )
