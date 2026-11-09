"""
FastAPI Main Application Entry Point.
Adaptive MVCC-Based Transaction Management and Recovery Framework for Asynchronous Federated Learning.
"""
import sys
import os
from pathlib import Path

# Automatically ensure backend root is in sys.path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import SessionLocal, init_db
from app.db.init_data import seed_system
from app.engine import coordinator
from app.api import (
    fl_routes,
    transaction_routes,
    mvcc_routes,
    wal_routes,
    optimization_routes,
    analytics_routes
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence: Seed database and hydrate DBMS coordinator
    print("[Startup] Initializing system catalog and datasets...")
    init_db()
    db = SessionLocal()
    try:
        seed_system(db)
        coordinator.initialize(db)
        print(f"[Startup] DBMS Coordinator hydrated. Current version: {coordinator.mvcc.current_version_id}")
    finally:
        db.close()
    yield
    # Shutdown sequence
    print("[Shutdown] Cleaning up AFL coordinator resources...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Custom DBMS transaction management engine designed for asynchronous federated learning.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for React frontend (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(fl_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(transaction_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(mvcc_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(wal_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(optimization_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_routes.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def root():
    return {
        "framework": settings.PROJECT_NAME,
        "status": "ONLINE",
        "docs_url": "/docs",
        "current_version": coordinator.mvcc.current_version_id,
        "is_crashed": coordinator.recovery.is_crashed
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
