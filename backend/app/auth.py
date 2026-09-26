"""
Minimal bearer-token guard for the mutating/data API.

Uses FastAPI's HTTPBearer security scheme (rather than reading the
Authorization header manually) specifically so Swagger UI at /docs
renders a proper "Authorize" padlock button -- paste the token once
and every request in the docs UI carries it, which matters for a live
demo in front of judges.

This is deliberately simple: one shared secret (API_TOKEN), not a
user/session system. See Settings.API_TOKEN and the README's Security
/ Known Limitations sections for why, and what a real multi-user
version would need instead.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    if credentials.credentials != settings.API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid bearer token.")
