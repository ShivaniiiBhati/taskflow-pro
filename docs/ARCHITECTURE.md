# Architecture Reference

This is the deeper companion to the README's Architecture/DAG Engine/
Scheduling Algorithm/AI Dependency Assistant sections — the same
design, with the exact prompt text, directory layout, and sequence
diagrams that didn't fit comfortably in the top-level README.

## Directory layout

```
backend/
└── app/
    ├── main.py                 FastAPI app, CORS, router registration
    ├── config.py                Settings (env vars)
    ├── database.py               SQLAlchemy engine/session
    ├── auth.py                  Bearer-token guard
    ├── seed.py                  10-task seed script (deliberate diamond)
    │
    ├── models/
    │   ├── task.py               Task, TaskStatus, Readiness
    │   └── dependency.py         Dependency, ScheduleChangeLog
    │
    ├── schemas/                 Pydantic request/response shapes
    │   ├── task.py
    │   ├── dependency.py
    │   └── ai.py
    │
    ├── services/                 Where the actual engineering is
    │   ├── dag_engine.py         Cycle detection, readiness cascade, critical path
    │   ├── scheduler.py          No-compounding schedule propagation
    │   └── dependency_ai.py      AI suggestion pipeline
    │
    └── api/                       Thin HTTP layer over services/
        ├── tasks.py
        ├── dependencies.py
        └── ai.py

frontend/
└── src/
    ├── main.tsx / App.tsx
    ├── types.ts                  Mirrors the backend's Pydantic shapes
    ├── api/client.ts             Typed fetch wrapper (axios)
    ├── hooks/useTasks.ts         Board data fetching/refresh
    └── components/
        ├── KanbanBoard.tsx / Column.tsx / TaskCard.tsx
        ├── TaskModal.tsx          Edit task, manage dependencies
        ├── AISuggestions.tsx      Suggest / Accept / Reject flow
        └── DependencyGraph.tsx   SVG DAG view + critical path highlight
```

The API layer (`app/api/*.py`) is intentionally thin: it validates
input via Pydantic, calls into `services/`, and serializes the
result. Every piece of logic that decides *correctness* (is this a
cycle? is this task Blocked? how far does a date shift propagate?)
lives in `services/`, not in a route handler — that's what "the
evaluator should be able to look at dag_engine.py and immediately see
the core problem has been addressed" (from the build plan) actually
means in practice.

## Sequence: adding a dependency (with cycle rejection)

```
Frontend                Backend (api/dependencies.py)      dag_engine.py
   |                              |                              |
   |--POST /dependencies -------->|                              |
   |   {predecessor, successor}   |                              |
   |                              |--would_create_cycle()------->|
   |                              |                              | BFS forward
   |                              |                              | from successor,
   |                              |                              | looking for
   |                              |                              | predecessor
   |                              |<--cycle path or None----------|
   |                              |
   |                    [cycle found]              [no cycle]
   |                        |                            |
   |<--409 + chain----------+                            |
   |   (nothing written)                       INSERT Dependency row
   |                                                       |
   |                              |--recompute_task_and_cascade(successor)-->|
   |                              |                              | recompute successor's
   |                              |                              | readiness, cascade to
   |                              |                              | its dependents if changed
   |<--201 + created edge----------------------------------------|
```

## Sequence: schedule propagation (No Compounding)

```
Frontend                Backend (api/tasks.py)         scheduler.py
   |                            |                            |
   |--PATCH /tasks/{id} ------->|                            |
   |   {duration_days: N}       |                            |
   |                    task.duration_days = N (committed)   |
   |                            |--propagate_schedule_change(task.id)-->|
   |                            |                            | BFS over dependents:
   |                            |                            |   required_start =
   |                            |                            |     max(all real
   |                            |                            |     predecessors' end_date)
   |                            |                            |   if required_start >
   |                            |                            |     task.start_date:
   |                            |                            |       update + log +
   |                            |                            |       enqueue ITS dependents
   |                            |                            |   else: stop here
   |<--200 + affected_task_ids--|<---------------------------|
```

Because `required_start` is always a `max(...)` over real predecessor
end dates — recomputed fresh every time a node is visited, never
accumulated — a diamond (`A -> B -> D`, `A -> C -> D`) cannot compound:
`D` looks at both `B.end_date` and `C.end_date` and takes the later of
the two, once, regardless of how many paths lead to it. See
`backend/tests/test_scheduler.py` for the exact assertions, including
the companion case where two genuinely *independent* upstream changes
must still both be reflected (whichever is later wins) — "no
compounding" would be trivial (and wrong) if it were implemented by
simply ignoring a predecessor's second change.

## Sequence: rollback-on-regression

```
Frontend                Backend (api/tasks.py)         dag_engine.py
   |                            |                            |
   |--PATCH /tasks/{id} ------->|                            |
   |   {status: "IN_PROGRESS"}  |                            |
   |                    task.status = IN_PROGRESS (committed) |
   |                            |--recompute_readiness_cascade(task.id)-->|
   |                            |                            | for each direct dependent:
   |                            |                            |   satisfied = (predecessor
   |                            |                            |     .status == DONE AND
   |                            |                            |     predecessor.readiness
   |                            |                            |     != BLOCKED)
   |                            |                            |   if any predecessor
   |                            |                            |     unsatisfied ->
   |                            |                            |     readiness = BLOCKED
   |                            |                            |   only cascade further if
   |                            |                            |     this node's readiness
   |                            |                            |     actually changed
   |<--200 + affected_task_ids--|<---------------------------|
```

The `readiness != BLOCKED` half of the "satisfied" check (not just
`status == DONE`) is what lets this cascade correctly through a
multi-hop chain `A -> B -> C`: when `A` regresses, `B`'s *column*
never changes (it can stay sitting in Done), but `B.readiness` flips
to `BLOCKED` — and `C` is checking `B.readiness`, not just `B.status`,
so `C` also flips to `BLOCKED` even though its direct predecessor's
board column never moved.

## AI prompt (exact template)

`app/services/dependency_ai.py::build_prompt()`:

**System prompt:**
```
You are a project dependency assistant.

Given the existing tasks in a software project, identify only
plausible prerequisite relationships for the new task.

A prerequisite must be something that must reasonably be completed
before the target task can begin or become executable.

Do not invent tasks. Use only task IDs provided in the context below.
If none of the provided tasks are genuine prerequisites, return an
empty list. Return ONLY structured JSON, no other text, in this exact
shape:
{"suggestions": [{"task_id": <int>, "reason": "<short reason>"}]}
```

**User prompt** (built per-request from the local pre-filter's top
candidates, never the whole board):
```
Existing Tasks:
ID: <id>
Title: <title>
Description: <description>

... (repeated for each of the top ~5 lexically-similar candidates)

New Task:
Title: <new task title>
Description: <new task description>
```

The pre-filter (`build_candidate_list`) scores existing tasks by
Jaccard similarity of stop-word-filtered tokens against the new
task's title + description, and keeps only the top 5. This is what
makes the candidate set "closed": the model is structurally unable to
suggest a task it was never shown, and the response is re-validated
against that same set server-side (`_parse_and_validate`) regardless
of whether the model followed the instruction.

## Data model

```sql
tasks
  id               INTEGER PRIMARY KEY
  title            VARCHAR(200) NOT NULL
  description      TEXT NOT NULL DEFAULT ''
  status           ENUM('BACKLOG','IN_PROGRESS','REVIEW','DONE') NOT NULL
  readiness        ENUM('READY','BLOCKED') NOT NULL
  start_date       DATE NOT NULL
  duration_days    INTEGER NOT NULL
  created_at       DATETIME
  updated_at       DATETIME
  -- end_date is NOT a column: it's a computed property
  -- (start_date + duration_days) so it can never drift.

task_dependencies
  id                INTEGER PRIMARY KEY
  predecessor_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE
  successor_id      INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE
  created_at        DATETIME
  UNIQUE(predecessor_id, successor_id)

schedule_change_log
  id                    INTEGER PRIMARY KEY
  task_id               INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE
  previous_end_date     DATE NOT NULL
  new_end_date          DATE NOT NULL
  triggered_by_task_id  INTEGER REFERENCES tasks(id) ON DELETE SET NULL
  timestamp             DATETIME
```

`ON DELETE CASCADE` on both edge foreign keys means deleting a task
never leaves an orphaned `task_dependencies` row pointing at a
nonexistent id — the API layer additionally recomputes readiness for
whatever the deleted task used to unblock (see `api/tasks.py::delete_task`).

## Why these specific engineering choices

- **SQLite over Postgres**: zero setup for an evaluator running this
  locally in a hackathon window; the SQLAlchemy layer means swapping
  the `DATABASE_URL` to Postgres later is a config change, not a
  rewrite.
- **A relaxation pass instead of a strict single topological sort**
  for propagation: simpler to implement correctly under time
  pressure, still provably terminates (dates are monotonically
  non-decreasing on a finite DAG), and the "skip if unchanged"
  short-circuit keeps it cheap in the common case where most of the
  board is unaffected by a given change.
- **Readiness as a stored, cached column** (not recomputed on every
  read): the alternative — recomputing Blocked/Ready live for every
  task on every `GET /tasks` — would mean an O(tasks × average
  predecessor chain length) cost on every board load. Caching it and
  invalidating precisely (only the cascade actually touched) keeps
  reads cheap.
- **A single shared bearer token instead of full auth**: matches the
  sprint's actual scope — see README Known Limitations for what a real
  multi-user version would need (per-user accounts, workspace
  isolation, and likely row-level scoping on every query in
  `services/`).
