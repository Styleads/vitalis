"""Resources router exposing resource pool states and active utilization.

Conforms to AGENT.md §19.2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from api.sim_service import SimulationService, get_sim_service

router = APIRouter(prefix="/resources", tags=["Resources"])


@router.get("/")
def get_resources(
    sim: SimulationService = Depends(get_sim_service),
):
    """Return pools per ResourceType plus instantaneous utilization percentage."""
    snapshot = sim.get_snapshot()
    raw_resources = snapshot.get("resources", {})

    utilization: dict[str, float] = {}
    for rtype, pool in raw_resources.items():
        total = pool.get("total", 0)
        failed = pool.get("failed", 0)
        off = pool.get("off", 0)
        occupied = pool.get("occupied", 0)

        active = total - failed - off
        if active > 0:
            utilization[rtype] = round((occupied / active) * 100.0, 2)
        else:
            utilization[rtype] = 0.0

    return {
        "clock": snapshot.get("clock", 0),
        "resources": raw_resources,
        "utilization_pct": utilization,
    }
