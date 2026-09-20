"""Scripted demo scenarios router.

Conforms to AGENT.md §19.7.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from api.sim_service import SimulationService, get_sim_service
from api.schemas import DemoLoadRequest
from api.demo_seeds import DEMO_SCENARIOS

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/scenarios")
def list_demo_scenarios():
    """List all available scripted demonstration scenarios."""
    return [
        {"name": name, "description": data["description"]}
        for name, data in DEMO_SCENARIOS.items()
    ]


@router.post("/load")
async def load_demo_scenario(
    req: DemoLoadRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Load a scripted scenario and reset the engine into that scenario state."""
    try:
        return await sim.load_demo(req.name)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown demo scenario: '{req.name}'. Available: {list(DEMO_SCENARIOS.keys())}",
        )
