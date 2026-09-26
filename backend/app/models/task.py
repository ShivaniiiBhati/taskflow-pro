import enum
from datetime import date, datetime, timedelta

from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TaskStatus(str, enum.Enum):
    """The four Kanban columns. This is the board position a human
    controls by dragging a card — separate from Readiness below."""
    BACKLOG = "BACKLOG"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"


class Readiness(str, enum.Enum):
    """
    Derived, engine-computed dependency state. Unlike TaskStatus, a
    human never sets this directly — it is always recalculated by
    app.services.dag_engine from the state of a task's prerequisites.

    Note this is tracked even for DONE tasks: if an upstream task that
    a DONE task depended on regresses, the DONE task's readiness can
    flip to BLOCKED (its column stays DONE, but the UI can flag that
    its completion now rests on a shaky prerequisite). This is what
    lets a rollback ("Done -> In Progress") cascade correctly through
    a chain like A -> B -> C even when B and C are still sitting in
    the Done column. See services/dag_engine.recompute_readiness_cascade.
    """
    READY = "READY"
    BLOCKED = "BLOCKED"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")

    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.BACKLOG)
    readiness = Column(Enum(Readiness), nullable=False, default=Readiness.READY)

    start_date = Column(Date, nullable=False, default=date.today)
    duration_days = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Edges where this task is the predecessor / successor. Cascade
    # delete so removing a task doesn't leave orphaned edges pointing
    # at a nonexistent id (see Prohibited Content / data-integrity
    # concerns called out in the README's Known Limitations section).
    outgoing_edges = relationship(
        "Dependency",
        foreign_keys="Dependency.predecessor_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    incoming_edges = relationship(
        "Dependency",
        foreign_keys="Dependency.successor_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def end_date(self) -> date:
        return self.start_date + timedelta(days=self.duration_days)

    def to_dict(self, dependency_count: int = 0) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "readiness": self.readiness.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "duration_days": self.duration_days,
            "dependency_count": dependency_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
