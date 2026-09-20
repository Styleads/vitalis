"""Patients router providing queue and in-treatment patient lists.

Conforms to AGENT.md §19.2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from api.sim_service import SimulationService, get_sim_service

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/")
def get_patients(
    sim: SimulationService = Depends(get_sim_service),
):
    """Return current waiting queue and in-treatment patients directly from snapshot."""
    snapshot = sim.get_snapshot()
    return {
        "clock": snapshot.get("clock", 0),
        "queue": snapshot.get("queue", []),
        "in_treatment": snapshot.get("in_treatment", []),
    }
