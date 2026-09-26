from typing import Optional
from pydantic import BaseModel


class SuggestDependenciesRequest(BaseModel):
    """
    Either reference an existing task by id, or pass a draft title +
    description for a task that hasn't been created yet (the UI calls
    this while the "New Task" form is still open, before Save).
    """
    task_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = ""


class SuggestionOut(BaseModel):
    task_id: int
    title: str
    reason: str
    similarity_score: float


class SuggestDependenciesResponse(BaseModel):
    suggestions: list[SuggestionOut]
    mode: str  # "live" or "mock"
