from typing import List, Literal, Optional
from pydantic import BaseModel


class TaskCreate(BaseModel):
    goal: str
    max_revisions: int = 1


class AgentEvent(BaseModel):
    agent: str
    name: str
    status: Literal["running", "done", "failed"] = "done"
    output: str
    step: int = 0


class TaskResult(BaseModel):
    id: str
    goal: str
    status: Literal["running", "done", "failed"] = "done"
    events: List[AgentEvent] = []
    final_report: str = ""
    approved: bool = False


class AgentInfo(BaseModel):
    id: str
    name: str
    emoji: str
    description: str
