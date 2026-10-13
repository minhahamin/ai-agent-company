"""Background execution of the company graph, with pauses for the user.

The graph runs in a thread and writes progress into the TaskResult as it goes;
the frontend polls GET /api/tasks/{id}. Interactive tasks stop at a gate
(status "waiting") until resume() is called.
"""
import threading

from langgraph.types import Command

from . import db as store
from .agents import ROLES
from .graph import get_graph, initial_state
from .schemas import AgentEvent, TaskResult

NAMES = {r["id"]: r["name"] for r in ROLES}


def _sync(task: TaskResult, state: dict) -> None:
    task.events = [
        AgentEvent(
            agent=e["agent"],
            name=NAMES.get(e["agent"], e["agent"]),
            status="done",
            output=e["output"],
            step=e.get("step", i + 1),
        )
        for i, e in enumerate(state.get("log", []))
    ]
    task.final_report = state.get("report", "") or task.final_report
    task.approved = bool(state.get("approved", False))
    store.save_task(task)


def _drive(task: TaskResult, graph_input) -> None:
    app = get_graph()
    cfg = {"configurable": {"thread_id": task.id}}
    try:
        for chunk in app.stream(graph_input, cfg, stream_mode="values"):
            _sync(task, chunk)
        snap = app.get_state(cfg)
        _sync(task, snap.values)
        interrupts = [i for t in snap.tasks for i in t.interrupts]
        if snap.next and interrupts:
            task.pending = dict(interrupts[0].value)
            task.status = "waiting"
        else:
            task.pending = None
            task.status = "done"
    except Exception as e:  # surfaced to the UI via status/report
        task.pending = None
        task.status = "failed"
        task.final_report = f"실패: {e}"
    store.save_task(task)


def _spawn(task: TaskResult, graph_input) -> None:
    threading.Thread(target=_drive, args=(task, graph_input), daemon=True).start()


def start(task: TaskResult, max_revisions: int) -> None:
    _spawn(task, initial_state(task.goal, max_revisions, task.interactive))


def resume(task: TaskResult, action: str, feedback: str, roles) -> None:
    task.status = "running"  # claimed before the thread starts, so a double click can't resume twice
    task.pending = None
    _spawn(task, Command(resume={"action": action, "feedback": feedback, "roles": roles}))
