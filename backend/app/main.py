from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.db.session import engine, Base
from app.api.endpoints import auth, machines, slots, records, bookings, analytics
from app.api.endpoints.auth import limiter

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for QuietHours – Shared Washing Machine Smart Scheduling and Usage Analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Attach SlowAPI limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global consistent error handling for uncaught exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if settings.ENVIRONMENT == "development" else "Internal server error"}
    )

# Routers
app.include_router(auth.router, prefix="/api")
app.include_router(machines.router, prefix="/api")
app.include_router(slots.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(bookings.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")

@app.get("/")
def health_check():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "docs": "/docs"
    }
