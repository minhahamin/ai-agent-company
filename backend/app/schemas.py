from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel


class TaskCreate(BaseModel):
    goal: str
    max_revisions: int = 1
    interactive: bool = False


class ResumeBody(BaseModel):
    action: Literal["approve", "revise", "finish"] = "approve"
    feedback: str = ""
    roles: Optional[List[str]] = None


class AgentEvent(BaseModel):
    agent: str
    name: str
    status: Literal["running", "done", "failed"] = "done"
    output: str
    step: int = 0


class TaskResult(BaseModel):
    id: str
    goal: str
    status: Literal["running", "waiting", "done", "failed"] = "done"
    events: List[AgentEvent] = []
    final_report: str = ""
    approved: bool = False
    interactive: bool = False
    # Set while status == "waiting": which gate the graph is paused at.
    pending: Optional[Dict[str, Any]] = None


class AgentInfo(BaseModel):
    id: str
    name: str
    emoji: str
    description: str
