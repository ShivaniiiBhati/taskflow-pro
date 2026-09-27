"""
Seeds 10 realistic tasks with dependency relationships, including a
deliberate diamond (Backend API -> {Authentication, Frontend
Dashboard} -> Integration Tests) so an evaluator can immediately
exercise the No Compounding rule against seeded data, plus a
straight chain long enough to make the Critical Path view meaningful.

Run with:  python -m app.seed   (from the backend/ directory)
"""
from datetime import date

from app.database import Base, engine, SessionLocal
from app.models.task import Task, TaskStatus
from app.models.dependency import Dependency
from app.services import dag_engine

Base.metadata.create_all(bind=engine)

TASKS = [
    ("Project Requirements", "Gather and document functional requirements with stakeholders.", 2),
    ("Database Schema", "Design the relational schema for tasks and dependencies.", 2),
    ("Backend API", "Build REST endpoints for tasks, dependencies, and scheduling.", 4),
    ("Authentication", "Add token-based auth to protect all API endpoints.", 2),
    ("Frontend Dashboard", "Build the Kanban board UI with drag and drop.", 4),
    ("Integration Tests", "End-to-end tests across API, auth, and frontend.", 2),
    ("Bug Fixes", "Address issues found during integration testing.", 2),
    ("Regression Testing", "Re-run the full suite after bug fixes.", 1),
    ("Release Preparation", "Changelog, versioning, deployment checklist.", 1),
    ("Production Release", "Deploy to production and monitor rollout.", 1),
]

# (predecessor title, successor title)
EDGES = [
    ("Project Requirements", "Database Schema"),
    ("Project Requirements", "Backend API"),
    ("Database Schema", "Backend API"),
    ("Backend API", "Authentication"),
    ("Backend API", "Frontend Dashboard"),        # diamond leg 1
    ("Authentication", "Integration Tests"),      # diamond converges here
    ("Frontend Dashboard", "Integration Tests"),  # diamond leg 2
    ("Integration Tests", "Bug Fixes"),
    ("Bug Fixes", "Regression Testing"),
    ("Regression Testing", "Release Preparation"),
    ("Release Preparation", "Production Release"),
]


def seed():
    db = SessionLocal()
    try:
        if db.query(Task).count() > 0:
            print("Tasks already exist -- skipping seed. Delete taskflow.db to reseed.")
            return

        start = date.today()
        title_to_task = {}
        for title, description, duration in TASKS:
            task = Task(
                title=title,
                description=description,
                start_date=start,
                duration_days=duration,
                status=TaskStatus.BACKLOG,
            )
            db.add(task)
            db.flush()  # get task.id without a full commit
            title_to_task[title] = task

        db.commit()

        for predecessor_title, successor_title in EDGES:
            pred = title_to_task[predecessor_title]
            succ = title_to_task[successor_title]
            db.add(Dependency(predecessor_id=pred.id, successor_id=succ.id))
        db.commit()

        # Initial readiness pass now that all edges exist.
        for task in title_to_task.values():
            task.readiness = dag_engine.compute_readiness(db, task)
            db.add(task)
        db.commit()

        # Reconcile schedule so dates are logically compatible
        from app.services import scheduler
        for task in title_to_task.values():
            scheduler.propagate_schedule_change(db, task.id)

        print(f"Seeded {len(TASKS)} tasks and {len(EDGES)} dependencies.")
        print("Deliberate diamond: Backend API -> (Authentication, Frontend Dashboard) -> Integration Tests")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
