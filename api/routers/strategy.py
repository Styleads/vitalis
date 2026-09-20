"""Strategy router exposing active strategy querying and hot-swapping.

Conforms to AGENT.md §19.4.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from strategies import STRATEGIES
from api.sim_service import SimulationService, get_sim_service
from api.schemas import StrategyRequest

router = APIRouter(prefix="/strategy", tags=["Strategy"])


@router.get("/")
def get_current_strategy(
    sim: SimulationService = Depends(get_sim_service),
):
    """Return the active strategy name and all available strategy algorithms."""
    return {
        "active": sim.strategy_name,
        "available": list(STRATEGIES.keys()),
    }


@router.post("/")
async def set_active_strategy(
    req: StrategyRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Switch the active scheduling strategy and immediately re-sort the queue."""
    if req.name not in STRATEGIES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown strategy: '{req.name}'. Available: {list(STRATEGIES.keys())}",
        )

    return await sim.set_strategy(req.name)
