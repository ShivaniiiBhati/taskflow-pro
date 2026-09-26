"""
Centralized configuration loaded from environment variables / .env.

Kept deliberately tiny: this is a hackathon-scoped prototype, not a
multi-environment production config system.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./taskflow.db")

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    AI_MODEL: str = os.getenv("AI_MODEL", "claude-sonnet-5")

    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    # Simple shared-secret bearer token, matching what the synopsis
    # disclosed: "every endpoint sits behind a bearer token issued at
    # login." There's no real login flow (no user accounts) in this
    # sprint-scoped build -- it's one static token both the API and
    # the frontend are configured with -- but it's enough to keep the
    # API from being open to the public internet, and it's disclosed
    # as a Known Limitation in the README rather than presented as
    # full authentication.
    API_TOKEN: str = os.getenv("API_TOKEN", "dev-local-token")

    @property
    def ai_mock_mode(self) -> bool:
        """
        True when no real API key is configured. The AI suggestion
        feature still works end-to-end in this mode (see
        services/dependency_ai.py) so the app is demoable without
        any external credentials.
        """
        return not self.ANTHROPIC_API_KEY


settings = Settings()
