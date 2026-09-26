from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    start_date: date
    duration_days: int = Field(..., ge=1)


class TaskUpdate(BaseModel):
    """All fields optional: PATCH semantics, only supplied fields change."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None  # one of TaskStatus values
    start_date: Optional[date] = None
    duration_days: Optional[int] = Field(None, ge=1)


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    status: str
    readiness: str
    start_date: date
    end_date: date
    duration_days: int
    dependency_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TaskUpdateResponse(BaseModel):
    """
    Returned instead of a bare TaskOut on PATCH, so the frontend can
    show "this also moved 3 downstream tasks" rather than silently
    updating one card and leaving the rest of the board stale.
    """
    task: TaskOut
    affected_task_ids: list[int] = []
