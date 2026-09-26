from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.task import Task
from app.models.dependency import Dependency
from app.schemas.dependency import DependencyCreate, DependencyOut, CriticalPathOut
from app.services import dag_engine, scheduler
from app.auth import require_auth

router = APIRouter(prefix="/dependencies", tags=["dependencies"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[DependencyOut])
def list_dependencies(db: Session = Depends(get_db)):
    return [d.to_dict() for d in db.query(Dependency).all()]


@router.get("/critical-path", response_model=CriticalPathOut)
def critical_path(db: Session = Depends(get_db)):
    path, total = dag_engine.get_critical_path(db)
    return {"task_ids": path, "total_duration_days": total}


@router.post("", response_model=DependencyOut, status_code=201)
def create_dependency(payload: DependencyCreate, db: Session = Depends(get_db)):
    if payload.predecessor_id == payload.successor_id:
        raise HTTPException(status_code=409, detail="A task cannot depend on itself.")

    predecessor = db.get(Task, payload.predecessor_id)
    successor = db.get(Task, payload.successor_id)
    if not predecessor or not successor:
        raise HTTPException(status_code=404, detail="predecessor_id or successor_id does not exist.")

    # --- Rule: No Cycles -------------------------------------------------
    # Checked BEFORE anything touches the database. On rejection, the
    # existing graph is left completely unchanged -- we never insert
    # then roll back; we simply never insert.
    cycle_path = dag_engine.would_create_cycle(db, payload.predecessor_id, payload.successor_id)
    if cycle_path is not None:
        chain = " -> ".join(str(t) for t in cycle_path)
        raise HTTPException(
            status_code=409,
            detail=f"Rejected: this dependency would create a cycle ({chain}).",
        )

    dependency = Dependency(predecessor_id=payload.predecessor_id, successor_id=payload.successor_id)
    db.add(dependency)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This dependency already exists.")
    db.refresh(dependency)

    # The successor just gained a new predecessor -- its own readiness
    # may now be Blocked, and that can cascade further downstream.
    dag_engine.recompute_task_and_cascade(db, payload.successor_id)
    scheduler.reconcile_task_schedule(db, payload.successor_id)

    return dependency.to_dict()


@router.delete("/{dependency_id}", status_code=204)
def delete_dependency(dependency_id: int, db: Session = Depends(get_db)):
    dependency = db.get(Dependency, dependency_id)
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")

    successor_id = dependency.successor_id
    db.delete(dependency)
    db.commit()

    dag_engine.recompute_task_and_cascade(db, successor_id)
    return None
