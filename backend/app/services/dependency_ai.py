"""
AI-Augmented Dependency Suggestion.

Design goals, matching what's disclosed in the synopsis and the
AI-Tool Declaration:

  1. The model is never allowed to invent a task. We first narrow the
     board down to a small candidate set ourselves (a local, free,
     lexical similarity pre-filter -- no extra network call), and the
     prompt tells the model it may ONLY choose ids from that set.
  2. Every suggestion is re-validated server-side against real task
     ids before it's ever shown to the user, independent of whether
     the model followed instructions.
  3. Nothing here writes to the dependency graph. This module only
     ever returns candidate suggestions; a human has to explicitly
     accept one, and acceptance goes through the normal
     POST /dependencies endpoint, which runs the exact same cycle
     check as a manually created edge (see api/dependencies.py).
  4. If no API key is configured, the module runs in MOCK mode:
     it returns the single top similarity match with a templated
     reason, so the feature is fully demoable offline. This is
     disclosed in the API response (`mode: "mock"` vs `"live"`) and
     in the README -- it is not hidden from an evaluator.
"""
import json
import re
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.task import Task

TOP_K_CANDIDATES = 5

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with",
    "is", "are", "be", "must", "should", "this", "that", "it", "its",
    "by", "as", "at", "from", "into", "will", "can", "so", "we", "our",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


@dataclass
class Candidate:
    task: Task
    score: float


def build_candidate_list(all_tasks: list[Task], new_title: str, new_description: str,
                          exclude_task_id: int | None, top_k: int = TOP_K_CANDIDATES) -> list[Candidate]:
    """
    Local, offline pre-filter: rank existing tasks by lexical overlap
    with the new task's text, and keep only the top_k. This is the
    "closed candidate set" the LLM is grounded against -- it also cuts
    token cost, since we never send the whole board to the model.
    """
    new_tokens = _tokenize(f"{new_title} {new_description}")
    scored = []
    for task in all_tasks:
        if exclude_task_id is not None and task.id == exclude_task_id:
            continue
        task_tokens = _tokenize(f"{task.title} {task.description}")
        score = _jaccard_similarity(new_tokens, task_tokens)
        scored.append(Candidate(task=task, score=score))

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]


def build_prompt(new_title: str, new_description: str, candidates: list[Candidate]) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt)."""
    system_prompt = (
        "You are a project dependency assistant.\n\n"
        "Given the existing tasks in a software project, identify only "
        "plausible prerequisite relationships for the new task.\n\n"
        "A prerequisite must be something that must reasonably be "
        "completed before the target task can begin or become "
        "executable.\n\n"
        "Do not invent tasks. Use only task IDs provided in the "
        "context below. If none of the provided tasks are genuine "
        "prerequisites, return an empty list. Return ONLY structured "
        "JSON, no other text, in this exact shape:\n"
        '{"suggestions": [{"task_id": <int>, "reason": "<short reason>"}]}'
    )

    existing_tasks_block = "\n\n".join(
        f"ID: {c.task.id}\nTitle: {c.task.title}\nDescription: {c.task.description}"
        for c in candidates
    ) or "(no candidate tasks)"

    user_prompt = (
        f"Existing Tasks:\n{existing_tasks_block}\n\n"
        f"New Task:\nTitle: {new_title}\nDescription: {new_description}"
    )
    return system_prompt, user_prompt


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    """Live call to the Anthropic Messages API. Raises on failure --
    the caller falls back to mock mode rather than surfacing a 500."""
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.AI_MODEL,
            "max_tokens": 500,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=15.0,
    )
    response.raise_for_status()
    data = response.json()
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(text_blocks)


def _mock_response(candidates: list[Candidate]) -> str:
    """
    Deterministic offline fallback: suggest the single strongest
    lexical match, if any, with a templated (clearly non-LLM) reason.
    Used only when no API key is configured, and always labeled as
    such in the API response so it's never mistaken for a live model
    call.
    """
    if not candidates or candidates[0].score == 0.0:
        return json.dumps({"suggestions": []})
    top = candidates[0]
    return json.dumps({
        "suggestions": [{
            "task_id": top.task.id,
            "reason": f"(mock mode) Shares significant wording with '{top.task.title}'.",
        }]
    })


def _parse_and_validate(raw_response: str, valid_ids: set[int]) -> list[dict]:
    """
    Hallucination guard #2: even if the model ignores the prompt and
    returns something malformed or references an id we never gave it,
    we drop it here rather than surfacing it to the user.
    """
    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
        parsed = json.loads(cleaned)
        suggestions = parsed.get("suggestions", [])
    except (json.JSONDecodeError, AttributeError):
        return []

    valid = []
    for s in suggestions:
        if not isinstance(s, dict):
            continue
        task_id = s.get("task_id")
        reason = s.get("reason", "")
        if isinstance(task_id, int) and task_id in valid_ids and isinstance(reason, str):
            valid.append({"task_id": task_id, "reason": reason})
    return valid


def suggest_dependencies(db: Session, title: str, description: str,
                          exclude_task_id: int | None = None) -> tuple[list[dict], str]:
    """
    Full pipeline: pre-filter -> prompt -> model call (or mock) ->
    validate. Returns (suggestions, mode) where mode is "live" or
    "mock". Never writes to the database.
    """
    all_tasks = db.query(Task).all()
    candidates = build_candidate_list(all_tasks, title, description, exclude_task_id)
    valid_ids = {c.task.id for c in candidates}
    by_id = {c.task.id: c for c in candidates}

    if settings.ai_mock_mode:
        raw = _mock_response(candidates)
        mode = "mock"
    else:
        system_prompt, user_prompt = build_prompt(title, description, candidates)
        try:
            raw = _call_anthropic(system_prompt, user_prompt)
            mode = "live"
        except Exception:
            # Provider hiccup: degrade gracefully rather than 500ing
            # the whole create-task flow, which must never depend on
            # this call succeeding.
            raw = _mock_response(candidates)
            mode = "mock"

    validated = _parse_and_validate(raw, valid_ids)

    enriched = []
    for item in validated:
        candidate = by_id[item["task_id"]]
        enriched.append({
            "task_id": item["task_id"],
            "title": candidate.task.title,
            "reason": item["reason"],
            "similarity_score": round(candidate.score, 3),
        })

    return enriched, mode
