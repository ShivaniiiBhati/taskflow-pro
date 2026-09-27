from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.api import tasks, dependencies, ai

# Import models so their tables are registered on Base before create_all.
from app import models  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="TaskFlow Pro API",
    description="Dependency-aware workflow and DAG scheduling engine.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





@app.get("/health")
def health():
    return {"status": "ok", "ai_mock_mode": settings.ai_mock_mode}


app.include_router(tasks.router)
app.include_router(dependencies.router)
app.include_router(ai.router)
