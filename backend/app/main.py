"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.core.logging_config import logger
from app.core.exceptions import AppException
from app.db.database import init_db, SessionLocal
from app.api import health, auth, admin, generations
from app.api.generations import generation_worker
from app.models.user import Role


async def init_default_roles():
    """Initialize default roles in the database."""
    db = SessionLocal()
    try:
        # Check if roles already exist
        existing_roles = db.query(Role).all()
        if existing_roles:
            logger.info(f"Default roles already exist ({len(existing_roles)} roles)")
            return
        
        # Create default roles
        default_roles = [
            Role(name="user", description="Regular user"),
            Role(name="admin", description="Administrator with full access"),
            Role(name="manager", description="Manager with limited admin access"),
        ]
        
        db.add_all(default_roles)
        db.commit()
        logger.info(f"Default roles created: {[role.name for role in default_roles]}")
    except Exception as e:
        logger.error(f"Failed to initialize default roles: {e}")
        db.rollback()
    finally:
        db.close()


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    await init_default_roles()
    generation_worker.start()
    yield
    # Shutdown
    generation_worker.stop()
    logger.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    """Convert app exceptions into HTTP responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


# Include routers
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(generations.router, prefix=settings.API_V1_PREFIX)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Wan2GP Platform API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
