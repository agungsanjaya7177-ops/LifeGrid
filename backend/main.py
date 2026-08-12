"""
FastAPI application factory for LifeGrid backend.

Configures middleware, routers, and startup/shutdown lifecycle.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from backend.config import settings, get_allowed_origins
from backend.database import SessionLocal

# Import routers
from backend.routers.auth import router as auth_router
# from backend.routers import tasks, finance, learning, fitness, security, dashboard


def cleanup_expired_blocklist():
    """
    Remove expired entries from jwt_blocklist table.

    This is a background job that runs periodically to clean up blocklist entries
    that have expired. Expired tokens can no longer be used, so their blocklist
    entries are no longer needed and can be safely deleted.

    The job queries and deletes all blocklist entries where expires_at < now().
    This prevents the blocklist table from growing indefinitely.
    """
    db = SessionLocal()
    try:
        # Delete all expired blocklist entries
        db.execute(
            text("DELETE FROM jwt_blocklist WHERE expires_at < now()")
        )
        db.commit()
    except Exception as e:
        # Log the error but don't raise - we want the scheduler to keep running
        print(f"Error cleaning up expired blocklist entries: {e}")
    finally:
        db.close()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Includes CORS middleware, all domain routers, and background job scheduler.

    Returns:
        FastAPI: The configured application instance
    """
    app = FastAPI(
        title="LifeGrid API",
        description="Personal life management dashboard REST API",
        version="0.1.0",
    )

    # Configure CORS middleware
    allowed_origins = get_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint for monitoring."""
        return {"status": "ok"}

    # Include routers
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    # app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
    # app.include_router(finance.router, prefix="/api/v1/finance", tags=["finance"])
    # app.include_router(learning.router, prefix="/api/v1/learning", tags=["learning"])
    # app.include_router(fitness.router, prefix="/api/v1/fitness", tags=["fitness"])
    # app.include_router(security.router, prefix="/api/v1/security", tags=["security"])
    # app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])

    # Initialize and start APScheduler for background jobs
    scheduler = BackgroundScheduler()

    # Schedule the blocklist cleanup job to run every hour
    scheduler.add_job(
        cleanup_expired_blocklist,
        "interval",
        hours=1,
        id="cleanup_expired_blocklist",
        name="Clean up expired JWT blocklist entries",
    )

    # Start the scheduler
    scheduler.start()

    # Register shutdown event to gracefully shut down the scheduler
    @app.on_event("shutdown")
    def shutdown_scheduler():
        """Shut down the background scheduler gracefully."""
        if scheduler.running:
            scheduler.shutdown()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
