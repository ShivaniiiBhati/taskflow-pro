from typing import Optional
from pydantic import BaseModel


class DependencyCreate(BaseModel):
    predecessor_id: int
    successor_id: int


class DependencyOut(BaseModel):
    id: int
    predecessor_id: int
    successor_id: int
    created_at: Optional[str] = None


class CriticalPathOut(BaseModel):
    task_ids: list[int]
    total_duration_days: int
