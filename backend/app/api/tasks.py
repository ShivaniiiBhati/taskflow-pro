from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate, TaskOut, TaskUpdateResponse
from app.services import dag_engine, scheduler
from app.auth import require_auth

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_auth)])


def _serialize(db: Session, task: Task) -> dict:
    return task.to_dict(dependency_count=dag_engine.dependency_count(db, task.id))


@router.get("", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.id).all()
    return [_serialize(db, t) for t in tasks]


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize(db, task)


@router.post("", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(
        title=payload.title,
        description=payload.description,
        start_date=payload.start_date,
        duration_days=payload.duration_days,
        status=TaskStatus.BACKLOG,
    )
    # A brand new task has no predecessors yet unless dependencies are
    # added afterward, so it starts Ready.
    task.readiness = dag_engine.compute_readiness(db, task)
    db.add(task)
    db.commit()
    db.refresh(task)
    return _serialize(db, task)


@router.patch("/{task_id}", response_model=TaskUpdateResponse)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    affected: list[int] = []

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description

    schedule_touched = payload.start_date is not None or payload.duration_days is not None
    if payload.start_date is not None:
        task.start_date = payload.start_date
    if payload.duration_days is not None:
        task.duration_days = payload.duration_days

    status_changed = False
    if payload.status is not None:
        try:
            new_status = TaskStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{payload.status}'")
        status_changed = new_status != task.status
        task.status = new_status

    db.add(task)
    db.commit()
    db.refresh(task)

    # Schedule propagation: a date/duration edit can push downstream
    # tasks later. Enforces the No Compounding rule (scheduler.py).
    if schedule_touched:
        affected.extend(scheduler.propagate_schedule_change(db, task.id))

    # Readiness cascade: a status change (in particular, a Done ->
    # In Progress rollback) can flip downstream tasks to Blocked.
    if status_changed:
        affected.extend(dag_engine.recompute_readiness_cascade(db, task.id))

    db.refresh(task)
    return {"task": _serialize(db, task), "affected_task_ids": sorted(set(affected))}


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    dependents = dag_engine.get_dependents(db, task_id)
    db.delete(task)  # cascades to edges via ondelete="CASCADE"
    db.commit()

    for dependent in dependents:
        # This task (a predecessor of `dependent`) just disappeared,
        # so `dependent`'s own predecessor set changed -- recompute
        # its readiness directly, not just its dependents' readiness.
        dag_engine.recompute_task_and_cascade(db, dependent.id)
    return None
