# TaskFlow Pro

A Kanban board backed by a real DAG (Directed Acyclic Graph) engine: task
dependencies are first-class, enforced server-side, and drive automatic
Blocked/Ready status and schedule propagation — not just visual cards on a
board.

- [Problem](#problem)
- [Features](#features)
- [Architecture](#architecture)
- [System Flow](#system-flow)
- [DAG Engine](#dag-engine)
- [Scheduling Algorithm](#scheduling-algorithm)
- [No-Compounding Strategy](#no-compounding-strategy)
- [AI Dependency Assistant](#ai-dependency-assistant)
- [Data Model](#data-model)
- [API Overview](#api-overview)
- [Setup](#setup)
- [Running Locally](#running-locally)
- [Running Tests](#running-tests)
- [Seed Data](#seed-data)
- [Example Scenarios](#example-scenarios)
- [Security](#security)
- [Key Assumptions](#key-assumptions)
- [Known Limitations](#known-limitations)
- [Future Improvements](#future-improvements)

## Problem

Most Kanban tools (Trello, basic Jira boards) treat every card as
independent. In real delivery work, tasks depend on each other — integration
tests can't start before the API and schema are done — and today that
ordering lives only in people's heads or a stale spreadsheet. TaskFlow Pro
puts a DAG engine behind the board so the system, not a person, tracks what's
actually workable right now.

## Features

- Four-column Kanban board (Backlog, In Progress, Review, Done) with
  drag-and-drop, persisted to the database.
- Task creation/editing, with start date and duration.
- Defining prerequisite dependencies between tasks, with server-side cycle
  rejection.
- Dynamic **Blocked / Ready** status, recalculated whenever relevant upstream
  tasks change (including rollback: moving a Done task back to In Progress
  correctly re-blocks its dependents).
- Automatic schedule propagation to downstream tasks when an upstream task's
  dates change, without compounding a shared delay across multiple paths.
- A dependency graph view with an optional critical-path highlight.
- An AI dependency-suggestion assistant, grounded against a closed candidate
  set and always subject to human approval + the deterministic cycle check.

## Architecture

```
                         TASKFLOW PRO
                              |
             +----------------+----------------+
             |                                 |
        React Frontend                    FastAPI Backend
        (Vite + TS + Tailwind)                  |
             |                            REST API Layer
       Kanban Board                             |
       Task Management            +-------------+-------------+
       Dependency editor          |             |             |
       AI Suggestions panel   DAG Engine    Scheduler     AI Service
       Dependency graph           |             |             |
                                  +------+------+
                                         |
                                     SQLite DB
```

Three tiers, deliberately conventional, because the interesting problems
here are graph/scheduling logic, not infrastructure:

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite |
| UI | Tailwind CSS |
| Drag and Drop | @dnd-kit |
| Backend | FastAPI |
| Database | SQLite + SQLAlchemy |
| Validation | Pydantic |
| DAG Engine | Custom Python (`app/services/dag_engine.py`) |
| Scheduler | Custom Python (`app/services/scheduler.py`) |
| AI | LLM API called from the backend, never the browser |
| Testing | Pytest |

All dependency logic lives in the backend. The frontend never decides
whether an edge would create a cycle or what a task's Ready/Blocked state
is — it only ever reflects what the API returns.

## System Flow

**Adding a dependency:**
```
User picks a prerequisite
        |
Validate both tasks exist
        |
Check existing graph -- would this edge create a cycle?
        |
       YES ---> 409 Conflict, graph left untouched
        |
       NO
        |
Persist the edge
        |
Recompute the successor's Readiness, cascade to its dependents
```

**Changing a task's dates:**
```
PATCH /tasks/{id} (start_date / duration_days)
        |
Commit the task's own new dates
        |
scheduler.propagate_schedule_change()
        |
Walk dependents; each dependent's new start = max(all its
predecessors' end dates); only continues past a node whose
date actually changed
        |
Every changed task logged to schedule_change_log
```

**Changing a task's status (including rollback):**
```
PATCH /tasks/{id} (status)
        |
Commit the new status
        |
dag_engine.recompute_readiness_cascade()
        |
Walk dependents; each one's Readiness recomputed from its own
predecessors' (status + readiness); cascade continues only
where Readiness actually flipped
```

## DAG Engine

`app/services/dag_engine.py` is the single source of truth for graph
correctness. Three responsibilities:

1. **Cycle prevention** (`would_create_cycle`) — before an edge is written, a
   BFS runs forward from the proposed successor looking for a path back to
   the proposed predecessor. If one exists, adding the edge would close a
   loop, so it's rejected and nothing is persisted.
2. **Readiness** (`compute_readiness` / `recompute_readiness_cascade`) — a
   task is Ready only when every direct predecessor is both `status ==
   DONE` **and** its own `readiness != BLOCKED`. That second condition is
   what makes a rollback correctly cascade through a multi-hop chain (see
   [Example Scenarios](#example-scenarios) below): an intermediate task can
   still show `DONE` on the board while its readiness flag flips to
   `BLOCKED`, and its own dependents see that.
3. **Critical path** (`get_critical_path`, bonus feature) — a single
   topological (Kahn's algorithm) dynamic-programming pass computes the
   longest cumulative-duration chain through the whole graph.

## Scheduling Algorithm

`app/services/scheduler.py` propagates date changes using a **forward
relaxation pass** — the same family of algorithm as the CPM (Critical Path
Method) forward pass / Bellman-Ford, specialized to a DAG so it's guaranteed
to terminate:

```
for each dependent of the changed task (breadth-first):
    candidate_start = max(end_date of ALL its real predecessors)
    if candidate_start pushes the task's start_date later:
        update it, log it, re-check ITS dependents
    else:
        stop -- nothing downstream of this node needs to move
```

Dates only ever move **later**, never earlier, in a single propagation run.
Since the graph is acyclic and finite, repeated visits (which can happen
when a node has more than one predecessor updating at different times)
simply re-confirm or push the date further — they can't loop forever, and
the process always converges to the correct final answer.

## No-Compounding Strategy

This is the rule the brief calls out as the trickiest one, and it falls out
naturally from the algorithm above rather than needing special-case code.
Because a downstream task's new start date is always the **maximum** over
its predecessors' end dates — never a sum — a diamond can't compound:

```
A --> B --+
          |--> D
A --> C --+
```

If A is extended by 3 days, B and C each move by 3 days (their only
predecessor is A). When D is processed, it takes `max(B.end, C.end)`, and
since both moved by the same 3 days, D also moves by exactly 3 — not 6. See
`tests/test_scheduler.py::test_diamond_dependency_does_not_compound` for the
exact assertion, and
`test_independent_upstream_changes_are_combined_correctly` for the
companion case: two genuinely independent delays on different paths must
still each be reflected (whichever is later wins), so "no compounding" isn't
solved by accidentally ignoring real changes either.

## AI Dependency Assistant

AI/LLM usage is a mandatory, scored part of this build. The design goal was
a real workflow, not a button that returns unvalidated text:

```
Create/Edit Task
       |
"Suggest Dependencies"
       |
Backend: local similarity pre-filter narrows the board down to
a small candidate set (no extra network call, cuts token cost)
       |
LLM, prompted to return ONLY structured JSON, and ONLY using
ids from the candidate set it was given
       |
Server-side validation: any id outside the candidate set, or
any malformed response, is discarded
       |
Shown to the user as a "Suggested Dependency" chip + reason
       |
Human clicks Accept or Reject
       |
Accept -> POST /dependencies -> same cycle check as a manual edge
```

**Grounding / hallucination reduction**, concretely:
- The model is only ever shown a handful of real candidate tasks (title +
  description), never the whole board, and is told explicitly: *"Do not
  invent tasks. Use only task IDs provided in the context. If none of the
  provided tasks are genuine prerequisites, return an empty list."*
- Even if the model ignores that instruction, the backend independently
  checks every returned `task_id` against the real candidate set before it
  is ever shown to a user.
- Nothing from the AI is ever written to the graph automatically — human
  approval is required, and approval routes through the exact same
  deterministic cycle-detection code path as a manually drawn dependency.
  **"AI proposes, deterministic DAG engine decides."**
- If no `ANTHROPIC_API_KEY` is set, the endpoint runs in a disclosed **mock
  mode** (`"mode": "mock"` in the response) so the feature is demoable
  offline; see `app/services/dependency_ai.py`.

## Data Model

```
tasks
  id, title, description, status, readiness,
  start_date, duration_days, created_at, updated_at

task_dependencies
  id, predecessor_id -> tasks.id, successor_id -> tasks.id, created_at
  UNIQUE(predecessor_id, successor_id)

schedule_change_log
  id, task_id -> tasks.id, previous_end_date, new_end_date,
  triggered_by_task_id -> tasks.id, timestamp
```

`end_date` is a computed property (`start_date + duration_days`), not a
stored column, so it can never drift out of sync with the source fields.
`schedule_change_log` exists purely as an audit trail so any propagation can
be traced (or, in principle, replayed/undone) after the fact.

## API Overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/tasks` | List all tasks |
| POST | `/tasks` | Create a task |
| GET | `/tasks/{id}` | Get one task |
| PATCH | `/tasks/{id}` | Update fields; triggers propagation/cascade as needed |
| DELETE | `/tasks/{id}` | Delete a task and its edges |
| GET | `/dependencies` | List all dependency edges |
| POST | `/dependencies` | Add an edge (rejects cycles with 409) |
| DELETE | `/dependencies/{id}` | Remove an edge |
| GET | `/dependencies/critical-path` | Longest chain by cumulative duration |
| POST | `/ai/suggest-dependencies` | Get (unpersisted) AI suggestions |
| GET | `/health` | Liveness + whether AI is in mock mode |

Full interactive docs (Swagger UI) are auto-generated by FastAPI at
`http://localhost:8000/docs` once the backend is running. Every route
except `/health` requires an `Authorization: Bearer <API_TOKEN>` header —
in Swagger UI, click **Authorize** and paste the token from your `.env`.

## Setup

**Prerequisites:** Python 3.11+, Node 18+.

```bash
git clone <this-repo-url>
cd taskflow-pro
```

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # optionally add a real ANTHROPIC_API_KEY;
                                # You MUST set a secure API_TOKEN
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env           # VITE_API_TOKEN must match backend's API_TOKEN
```

## Running Locally

```bash
# Terminal 1 -- backend
cd backend
source .venv/bin/activate
python -m app.seed             # optional: loads the 10 seeded tasks
uvicorn app.main:app --reload  # http://localhost:8000

# Terminal 2 -- frontend
cd frontend
npm run dev                    # http://localhost:5173
```

The database schema is created automatically on backend startup — no
migration step needed for this prototype.

## Running Tests

**Backend:**
```bash
cd backend
source .venv/bin/activate
pytest -v
```

Tests cover, among others: task CRUD and persistence, cycle rejection
(direct and multi-hop), the diamond no-compounding scenario, independent
vs. shared upstream changes, rollback-on-regression cascades, and the AI
suggestion validation/hallucination guards. Tests run against an isolated
temporary SQLite file and force the AI service into mock mode, so they need
no network access or API key.

**Frontend:**
```bash
cd frontend
npm run test
```

Vitest + React Testing Library tests cover the Kanban UI, optimistic status
updates and error rollback, and AI suggestion accept/conflict behavior.

## Seed Data

`python -m app.seed` loads 10 tasks modeling a realistic mini-project:

```
Requirements -> Database Schema -> Backend API -> Authentication --+
                                          |                        |
                                          +----> Integration Tests <+
                             Frontend Dashboard --+
Integration Tests -> Bug Fixes -> Regression Testing -> Release Prep -> Production Release
```

Backend API feeds Authentication and Frontend Dashboard, which both feed
Integration Tests — a deliberate diamond so the No-Compounding rule can be
exercised immediately against seeded data (see Example Scenarios below).

## Example Scenarios

**1. Cycle rejection** — with A → B → C already linked, try adding C → A in
the dependency editor or via `POST /dependencies`. Expect a 409 with a
message naming the offending chain, and the existing graph unchanged.

**2. Diamond / no compounding** — using the seeded diamond (Backend API →
Authentication & Frontend Dashboard → Integration Tests), extend Backend
API's duration by a few days. Integration Tests should move by that same
delta once, not twice.

**3. Rollback** — mark Backend API and Authentication both Done (Integration
Tests becomes Ready). Drag Backend API back to In Progress. Authentication
and Integration Tests should both flip to Blocked, even though
Authentication's board column stays Done.

**4. AI suggestion** — open a new or existing task, click "Suggest
Dependencies". A candidate prerequisite appears with a reason; Accept routes
it through the normal dependency endpoint (so it's still subject to cycle
checking), Reject discards it.

## Security

- All mutating endpoints go through Pydantic validation before touching the
  database; SQLAlchemy's parameterized queries prevent injection.
- Every route under `/tasks`, `/dependencies`, and `/ai` requires
  `Authorization: Bearer <API_TOKEN>` (see `app/auth.py`); requests without
  it, or with the wrong token, get a 401. `/health` is intentionally
  unauthenticated so it can be used for liveness checks. This is a single
  shared secret, not a real login/user-account system — see Known
  Limitations — but it means the API isn't wide open if a live deployment
  URL is shared.
- The AI suggestion endpoint only ever sends task titles/descriptions to the
  LLM provider — never internal ids beyond what's needed, never other user
  data.
- Both `ANTHROPIC_API_KEY` and `API_TOKEN` are read from server-side
  environment variables and never bundled into the frontend's compiled
  JavaScript beyond the token itself, which the frontend necessarily holds
  to call the API — swapping this for real per-user auth is the natural
  next step (see Future Improvements).
- CORS is restricted to the configured frontend origin.
- This prototype does not implement per-user authentication/authorization
  (see Known Limitations) — it assumes a single trusted workspace for the
  sprint, gated by the one shared token above.

## Key Assumptions

- A single shared workspace for this build; no multi-tenant isolation.
- Every calendar day counts equally — no weekend/holiday-aware scheduling.
- A dependency always means finish-to-start: a predecessor must reach `DONE`
  before its successor can be considered Ready.
- Readiness (Blocked/Ready) is **advisory**: the UI shows it, but a user can
  still drag a Blocked task forward if they choose to — the engine doesn't
  hard-block board moves, mirroring how humans actually use Kanban tools.

## Known Limitations

- Auth is a single shared bearer token, not per-user accounts, sessions, or
  roles — anyone with the token has full access to everything.
- No weekend/holiday-aware date math; `duration_days` are plain calendar
  days.
- No resource/capacity leveling (the engine doesn't know if two tasks
  compete for the same person's time).
- Conflict resolution on simultaneous edits from two users is last-write-wins;
  there's no operational-transform / real-time merge logic.
- The AI suggestion feature depends on Jaccard/lexical similarity for its
  candidate pre-filter, which is fast and free but weaker than an embedding-
  based similarity search — a task described in very different words from
  its true prerequisite may not surface as a candidate.
- The critical path view is explicitly a bonus feature and has had less
  polish than the core DAG/scheduling engine.

## Known Failure Cases

- **Semantic mismatch:** The lexical pre-filtering may miss semantically equivalent or synonymous tasks, resulting in the AI not being provided the correct candidates to suggest.
- **Data overwrite:** Concurrent edits are not conflict-resolved beyond the current persistence behavior (last-write-wins), which could overwrite another user's immediate changes.

## Future Improvements

- Multi-tenant workspaces with authentication.
- Calendar-aware scheduling (working days, holidays).
- Resource/capacity leveling across tasks and assignees.
- Real-time collaboration (WebSocket-pushed updates instead of client polling
  / manual refresh).
- Swap the lexical AI pre-filter for embedding-based similarity search, and/or
  let the AI suggestion feature run against a fine-tuned or self-hosted
  model.
- Undo/redo for schedule propagation, using the existing
  `schedule_change_log` audit trail as the basis for a reversal.
