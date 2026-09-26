"""
The dependency graph engine.

Everything here treats the graph as the single source of truth for
correctness. Nothing in the API layer or the frontend is allowed to
set Readiness directly — it is always derived by the functions below.

Three responsibilities live in this file:
  1. Cycle prevention        -> would_create_cycle()
  2. Blocked/Ready state     -> recompute_readiness_cascade()
  3. Critical path (bonus)   -> get_critical_path()

Schedule propagation (the "no compounding" rule) lives in
scheduler.py, since it is date arithmetic rather than graph state,
but it reuses get_predecessors/get_dependents from here.
"""
from collections import deque
from typing import Optional

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus, Readiness
from app.models.dependency import Dependency


def get_predecessors(db: Session, task_id: int) -> list[Task]:
    """Direct prerequisites of a task (edges pointing INTO task_id)."""
    return (
        db.query(Task)
        .join(Dependency, Dependency.predecessor_id == Task.id)
        .filter(Dependency.successor_id == task_id)
        .all()
    )


def get_dependents(db: Session, task_id: int) -> list[Task]:
    """Direct dependents of a task (edges pointing OUT of task_id)."""
    return (
        db.query(Task)
        .join(Dependency, Dependency.successor_id == Task.id)
        .filter(Dependency.predecessor_id == task_id)
        .all()
    )


def dependency_count(db: Session, task_id: int) -> int:
    return db.query(Dependency).filter(Dependency.successor_id == task_id).count()


# ---------------------------------------------------------------------------
# 1. Cycle prevention
# ---------------------------------------------------------------------------

def would_create_cycle(db: Session, predecessor_id: int, successor_id: int) -> Optional[list[int]]:
    """
    Returns the offending path (list of task ids) if adding the edge
    predecessor_id -> successor_id would create a cycle, else None.

    Logic: adding this edge closes a loop exactly when predecessor_id
    is already reachable *from* successor_id by following existing
    edges forward. So we BFS forward starting at successor_id, and
    check whether we ever reach predecessor_id. A direct self-loop
    (predecessor_id == successor_id) is trivially a cycle.
    """
    if predecessor_id == successor_id:
        return [predecessor_id, successor_id]

    # BFS forward from successor_id, tracking the path taken so we can
    # report a human-readable chain in the 409 response.
    queue = deque([(successor_id, [successor_id])])
    visited = {successor_id}

    while queue:
        current_id, path = queue.popleft()
        for dependent in get_dependents(db, current_id):
            if dependent.id == predecessor_id:
                return path + [dependent.id, successor_id]
            if dependent.id not in visited:
                visited.add(dependent.id)
                queue.append((dependent.id, path + [dependent.id]))

    return None


# ---------------------------------------------------------------------------
# 2. Blocked / Ready cascade
# ---------------------------------------------------------------------------

def _predecessor_satisfied(predecessor: Task) -> bool:
    """
    A prerequisite counts as satisfied only if the predecessor is both
    marked Done AND its own readiness is not Blocked. The second half
    of that check is what makes rollback cascade correctly through a
    multi-hop chain (A -> B -> C): if A regresses, B's readiness flips
    to Blocked even though B's *column* is still Done, and C then sees
    B as unsatisfied too, even though C's direct predecessor's column
    never changed.
    """
    return predecessor.status == TaskStatus.DONE and predecessor.readiness != Readiness.BLOCKED


def compute_readiness(db: Session, task: Task) -> Readiness:
    predecessors = get_predecessors(db, task.id)
    if not predecessors:
        return Readiness.READY
    if all(_predecessor_satisfied(p) for p in predecessors):
        return Readiness.READY
    return Readiness.BLOCKED


def recompute_readiness_cascade(db: Session, start_task_id: int) -> list[int]:
    """
    Call this whenever a task's status changes, or whenever a
    dependency edge touching it is added/removed. Walks forward
    through dependents, recomputing Readiness at each hop, and only
    continues the cascade past a node if that node's readiness
    actually changed — a node whose readiness is unchanged cannot
    possibly change the readiness of anything further downstream,
    so there's no reason to keep walking through it.

    Returns the list of task ids whose readiness was actually updated,
    so the API layer can tell the frontend what else needs a refresh.
    """
    changed: list[int] = []
    queue = deque(get_dependents(db, start_task_id))
    seen_in_this_pass = set()

    while queue:
        task = queue.popleft()
        if task.id in seen_in_this_pass:
            continue
        seen_in_this_pass.add(task.id)

        new_readiness = compute_readiness(db, task)
        if new_readiness != task.readiness:
            task.readiness = new_readiness
            db.add(task)
            changed.append(task.id)
            queue.extend(get_dependents(db, task.id))

    if changed:
        db.commit()
    return changed


def recompute_task_and_cascade(db: Session, task_id: int) -> list[int]:
    """
    Use this when a task's OWN predecessor set just changed (a
    dependency edge touching it as the successor was added or
    removed), as opposed to recompute_readiness_cascade(), which is
    for when a task's STATUS changed and its dependents need
    re-checking. Recomputes task_id itself first, then, only if that
    changed, cascades onward through its dependents exactly like
    recompute_readiness_cascade().
    """
    task = db.get(Task, task_id)
    if task is None:
        return []

    changed: list[int] = []
    new_readiness = compute_readiness(db, task)
    if new_readiness == task.readiness:
        return []

    task.readiness = new_readiness
    db.add(task)
    db.commit()
    changed.append(task.id)

    changed.extend(recompute_readiness_cascade(db, task.id))
    return changed


# ---------------------------------------------------------------------------
# 3. Critical path (optional bonus feature)
# ---------------------------------------------------------------------------

def get_critical_path(db: Session) -> tuple[list[int], int]:
    """
    Longest chain by cumulative duration through the whole graph,
    computed with a single dynamic-programming pass over a
    topological ordering (Kahn's algorithm): the same style of
    forward pass used for schedule propagation, just maximizing
    cumulative duration instead of finish date.
    """
    tasks = {t.id: t for t in db.query(Task).all()}
    if not tasks:
        return [], 0

    edges = db.query(Dependency).all()
    predecessors_of: dict[int, list[int]] = {tid: [] for tid in tasks}
    dependents_of: dict[int, list[int]] = {tid: [] for tid in tasks}
    for e in edges:
        if e.predecessor_id in tasks and e.successor_id in tasks:
            predecessors_of[e.successor_id].append(e.predecessor_id)
            dependents_of[e.predecessor_id].append(e.successor_id)

    in_degree = {tid: len(preds) for tid, preds in predecessors_of.items()}
    queue = deque([tid for tid, d in in_degree.items() if d == 0])

    longest_finish = {tid: tasks[tid].duration_days for tid in tasks}
    best_predecessor: dict[int, Optional[int]] = {tid: None for tid in tasks}

    topo_order = []
    local_in_degree = dict(in_degree)
    while queue:
        tid = queue.popleft()
        topo_order.append(tid)
        for dep_id in dependents_of[tid]:
            candidate = longest_finish[tid] + tasks[dep_id].duration_days
            if candidate > longest_finish[dep_id]:
                longest_finish[dep_id] = candidate
                best_predecessor[dep_id] = tid
            local_in_degree[dep_id] -= 1
            if local_in_degree[dep_id] == 0:
                queue.append(dep_id)

    if not topo_order:
        return [], 0

    end_id = max(longest_finish, key=lambda tid: longest_finish[tid])
    path = []
    cur: Optional[int] = end_id
    while cur is not None:
        path.append(cur)
        cur = best_predecessor[cur]
    path.reverse()

    return path, longest_finish[end_id]
