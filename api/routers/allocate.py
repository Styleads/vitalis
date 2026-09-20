"""Manual allocation and step trigger router.

Conforms to AGENT.md §19.3.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from api.sim_service import SimulationService, get_sim_service

router = APIRouter(prefix="/allocate", tags=["Allocation"])


@router.post("/")
async def manual_step_allocate(
    sim: SimulationService = Depends(get_sim_service),
):
    """Manually execute a single step and allocation pass while the simulation is paused."""
    try:
        return await sim.step_manual()
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
