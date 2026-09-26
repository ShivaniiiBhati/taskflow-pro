# AI Tool Declaration

## Did you use any AI tool during development?

**Yes.**

## AI-assisted development

Claude (Anthropic) was used throughout development for: architecture planning
and review, scaffolding the FastAPI project structure, drafting and refining
the DAG engine, scheduler, and AI-suggestion service, writing and reviewing
the pytest suite, drafting documentation (this file, the README, and
ARCHITECTURE.md), and debugging assistance. Every generated file was reviewed
by the development team before being committed, and the core algorithmic
logic (cycle detection, the no-compounding forward-relaxation scheduler, and
the readiness cascade) was traced by hand against the required test scenarios
from the problem statement before being trusted.

This is disclosed in the same spirit as citing a library: using an AI
assistant during the build is normal engineering practice for this sprint,
and we would rather state that plainly than have it discovered later.

## AI functionality inside TaskFlow Pro (the product feature)

TaskFlow Pro also includes an LLM-powered dependency-suggestion feature,
separate from AI-assisted development above. When a user creates or edits a
task, the backend:

1. Pre-filters the board locally (a lexical similarity pass, no network
   call) down to a small candidate set of plausibly related tasks.
2. Sends only that candidate set's titles/descriptions and the new task's
   text to the configured LLM, in a prompt that explicitly forbids
   inventing tasks or ids outside the candidate set.
3. Validates the model's JSON response server-side — any suggestion
   referencing an id outside the candidate set, or any malformed response,
   is discarded before the user ever sees it.
4. Never writes anything to the dependency graph directly. A suggestion is
   shown to the user as a labeled "Suggested Dependency" with the model's
   reasoning attached; only when a human clicks Accept does it go through
   `POST /dependencies`, the exact same endpoint (and cycle check) as a
   manually drawn edge.

If no `ANTHROPIC_API_KEY` is configured, the feature runs in a disclosed
**mock mode**: it returns the single closest lexical match instead of a live
model call, clearly labeled `"mode": "mock"` in the API response and in the
UI, so the app is fully demoable offline without misrepresenting a canned
response as a live AI call.

See `docs/ARCHITECTURE.md` → "AI Dependency Assistant" for the full prompt
and grounding design.
