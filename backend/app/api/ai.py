from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.schemas.ai import SuggestDependenciesRequest, SuggestDependenciesResponse
from app.services import dependency_ai
from app.auth import require_auth

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(require_auth)])


@router.post("/suggest-dependencies", response_model=SuggestDependenciesResponse)
def suggest_dependencies(payload: SuggestDependenciesRequest, db: Session = Depends(get_db)):
    """
    Returns candidate dependency suggestions only. Nothing here is
    persisted -- accepting a suggestion is a separate, explicit call
    to POST /dependencies from the frontend, which runs the full
    cycle check exactly as if the user had drawn the edge by hand.
    """
    title, description, exclude_id = payload.title, payload.description or "", None

    if payload.task_id is not None:
        task = db.get(Task, payload.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        title, description, exclude_id = task.title, task.description, task.id

    if not title:
        raise HTTPException(status_code=400, detail="Either task_id or title must be provided.")

    suggestions, mode = dependency_ai.suggest_dependencies(db, title, description, exclude_id)
    return {"suggestions": suggestions, "mode": mode}
