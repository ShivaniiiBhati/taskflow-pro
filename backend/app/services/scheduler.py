"""
Schedule propagation: the "No Compounding" rule.

The approach is a forward relaxation pass, the same family of
algorithm as Bellman-Ford / the CPM forward pass, specialized to a
DAG so it's guaranteed to terminate:

    for each dependent of a changed task (breadth-first):
        candidate_start = max(end_date of ALL its real predecessors)
        if candidate_start pushes the task's start_date later:
            update it, log it, and re-check ITS dependents
        else:
            stop -- nothing downstream of this node needs to move

Because a task's new start date is always the *maximum* over its
predecessors, not a sum, a diamond (A -> B -> D, A -> C -> D) can
never compound: D looks at both B's and C's finish dates once, at the
end, and takes the later of the two. Both paths originating from the
same upstream change land on the same B/C dates, so D moves once, by
that same delta, not twice.

Re-enqueuing a node's dependents every time the node itself changes
(rather than doing a single topological pass) means a node can be
visited more than once if multiple predecessors update at different
times in the same BFS. That's intentional and still correct: dates
only ever move later (never earlier) in a single propagation run, so
repeated visits just re-confirm or push the date further, and the
process is guaranteed to converge since the graph is acyclic and
finite.
"""
from collections import deque
from datetime import date

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.dependency import ScheduleChangeLog
from app.services.dag_engine import get_predecessors, get_dependents


def propagate_schedule_change(db: Session, changed_task_id: int) -> list[int]:
    """
    Call this AFTER a task's own start_date/duration_days has already
    been updated and committed. Pushes the effect forward through the
    graph. Returns the list of task ids whose dates were actually
    changed as a result (empty if the change didn't affect anyone).
    """
    affected: list[int] = []
    queue = deque(get_dependents(db, changed_task_id))
    guard = 0
    max_iterations = 10_000  # safety valve; real boards are far smaller

    while queue and guard < max_iterations:
        guard += 1
        task = queue.popleft()

        predecessors = get_predecessors(db, task.id)
        if not predecessors:
            continue

        required_start: date = max(p.end_date for p in predecessors)

        if required_start > task.start_date:
            previous_end_date = task.end_date
            task.start_date = required_start
            db.add(task)

            db.add(ScheduleChangeLog(
                task_id=task.id,
                previous_end_date=previous_end_date,
                new_end_date=task.end_date,
                triggered_by_task_id=changed_task_id,
            ))
            db.commit()
            db.refresh(task)

            affected.append(task.id)
            queue.extend(get_dependents(db, task.id))
        # else: this node is unaffected, so nothing downstream of it
        # needs to be re-examined as a *result of this task* -- it may
        # still get re-visited via a different predecessor's update,
        # which is fine (see module docstring).

    return affected
