"""PayTrace — AI-Powered Payment Reconciliation & Exception Tracing.

FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings


class HealthResponse(BaseModel):
    """Minimal health check response.

    Contains no secrets, no environment variables, no filesystem paths,
    and no sensitive information.
    """

    status: str
    service: str
    version: str


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    success: bool
    error: str


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Payment Reconciliation & Exception Tracing",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — restricted to Vite dev origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# API routes
from backend.api.routes import router as api_router  # noqa: E402
app.include_router(api_router)

from backend.api.ai_routes import router as ai_router  # noqa: E402
app.include_router(ai_router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns a minimal JSON response indicating PayTrace is running.
    Exposes no secrets, environment variables, or internal state.
    """
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
    )
