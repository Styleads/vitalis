"""Scenario control router for surges, staff shortage, and equipment failure.

Conforms to AGENT.md §18 (Task 6), §19.5.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from engine.types import ResourceType
from api.sim_service import SimulationService, get_sim_service
from api.schemas import SurgeRequest, CapacityRequest, FailRequest, ScenarioRequest

router = APIRouter(prefix="/scenario", tags=["Scenario"])


@router.post("/surge")
async def trigger_surge(
    req: SurgeRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Trigger a patient arrival surge (e.g. 3x arrivals for 1 hour)."""
    return await sim.inject_surge(req.multiplier, req.duration_s)


@router.post("/capacity")
async def adjust_capacity(
    req: CapacityRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Adjust capacity of a resource type (e.g. staff shortage or shift change)."""
    try:
        rtype = ResourceType[req.type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid ResourceType: '{req.type}'. Valid types: {[r.name for r in ResourceType]}",
        )

    return await sim.set_capacity(rtype, req.n)


@router.post("/fail")
async def fail_resource(
    req: FailRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Simulate a temporary resource failure with automatic P-FAIL patient requeuing."""
    return await sim.fail_resource(req.unit_id, req.duration_s)


@router.post("/")
async def trigger_generic_scenario(
    req: ScenarioRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Generic scenario dispatcher supporting 'surge', 'capacity', or 'fail'."""
    kind = req.kind.lower()
    if kind == "surge":
        multiplier = req.multiplier if req.multiplier is not None else 3.0
        duration_s = req.duration_s if req.duration_s is not None else 3600
        return await sim.inject_surge(multiplier, duration_s)

    elif kind == "capacity":
        if not req.type or req.n is None:
            raise HTTPException(
                status_code=422,
                detail="Scenario 'capacity' requires 'type' and 'n'.",
            )
        try:
            rtype = ResourceType[req.type.upper()]
        except KeyError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid ResourceType: '{req.type}'. Valid types: {[r.name for r in ResourceType]}",
            )
        return await sim.set_capacity(rtype, req.n)

    elif kind == "fail":
        if req.unit_id is None:
            raise HTTPException(
                status_code=422,
                detail="Scenario 'fail' requires 'unit_id'.",
            )
        duration_s = req.duration_s if req.duration_s is not None else 1800
        return await sim.fail_resource(req.unit_id, duration_s)

    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown scenario kind: '{req.kind}'. Choose from: ['surge', 'capacity', 'fail']",
        )
