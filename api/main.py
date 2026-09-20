"""MedFlow FastAPI application entry point.

Conforms to AGENT.md §17.3, §18 (Task 2).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.sim_service import sim_service
from api.routers import (
    simulation,
    patients,
    resources,
    stats,
    strategy,
    scenario,
    compare,
    allocate,
    demo,
    websocket,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    yield
    await sim_service.shutdown()


app = FastAPI(
    title="MedFlow API",
    description="Hospital Resource Management Simulator - Backend & Coordination API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware allowing Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(simulation.router)
app.include_router(patients.router)
app.include_router(resources.router)
app.include_router(stats.router)
app.include_router(strategy.router)
app.include_router(scenario.router)
app.include_router(compare.router)
app.include_router(allocate.router)
app.include_router(demo.router)
app.include_router(websocket.router)


@app.get("/")
def root():
    """Service root health and docs link."""
    return {
        "message": "MedFlow API is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    """Health check endpoint confirming engine state and clock."""
    clock = sim_service.engine.clock if sim_service.engine else 0
    return {
        "ok": True,
        "clock": clock,
        "running": sim_service.running,
        "strategy": sim_service.strategy_name,
    }


@app.get("/state")
def get_full_state():
    """Convenience endpoint returning the complete current snapshot."""
    return sim_service.get_snapshot()
