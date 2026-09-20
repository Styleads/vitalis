"""Statistics router exposing processed operational metrics.

Conforms to AGENT.md §19.2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from api.sim_service import SimulationService, get_sim_service

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/")
def get_statistics(
    sim: SimulationService = Depends(get_sim_service),
):
    """Return display stats transformed from raw simulation counters via Person B's layer."""
    return sim.get_stats()
