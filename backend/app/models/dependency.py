from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Date, UniqueConstraint

from app.database import Base


class Dependency(Base):
    """
    A directed edge: predecessor_id must be satisfied before
    successor_id can be considered Ready. Stored as its own table,
    deliberately decoupled from the tasks table, so the graph
    structure never gets tangled up with board/display state.
    """
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("predecessor_id", "successor_id", name="uq_dependency_edge"),
    )

    id = Column(Integer, primary_key=True, index=True)
    predecessor_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    successor_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "predecessor_id": self.predecessor_id,
            "successor_id": self.successor_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScheduleChangeLog(Base):
    """
    Audit trail for every schedule propagation write. Exists purely
    so a change can be traced (and, if propagation ever misbehaves,
    diagnosed) after the fact: which task moved, from what date to
    what date, and which upstream change triggered it.
    """
    __tablename__ = "schedule_change_log"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_end_date = Column(Date, nullable=False)
    new_end_date = Column(Date, nullable=False)
    triggered_by_task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "previous_end_date": self.previous_end_date.isoformat(),
            "new_end_date": self.new_end_date.isoformat(),
            "triggered_by_task_id": self.triggered_by_task_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
