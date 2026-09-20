"""Simulation lifecycle control router.

Conforms to AGENT.md §19.1.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from api.sim_service import SimulationService, get_sim_service
from api.schemas import SimStartRequest, SpeedRequest, ResetRequest

router = APIRouter(prefix="/sim", tags=["Simulation"])


@router.post("/start")
async def start_simulation(
    req: SimStartRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Start simulation clock advance with specified parameters."""
    return await sim.start(
        seed=req.seed,
        horizon_s=req.horizon_s,
        speed=req.speed,
        strategy=req.strategy,
        demo=req.demo,
    )


@router.post("/pause")
async def pause_simulation(
    sim: SimulationService = Depends(get_sim_service),
):
    """Pause simulation clock advance."""
    return await sim.pause()


@router.post("/resume")
async def resume_simulation(
    sim: SimulationService = Depends(get_sim_service),
):
    """Resume simulation clock advance."""
    return await sim.resume()


@router.post("/speed")
async def set_simulation_speed(
    req: SpeedRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Set simulation speed multiplier (simulated seconds per real second)."""
    return await sim.set_speed(req.speed)


@router.post("/reset")
async def reset_simulation(
    req: ResetRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Reset simulation engine to initial state."""
    return await sim.reset(seed=req.seed, demo=req.demo)


@router.get("/status")
def get_simulation_status(
    sim: SimulationService = Depends(get_sim_service),
):
    """Return status metadata for the active simulation."""
    clock = sim.engine.clock if sim.engine else 0
    return {
        "running": sim.running,
        "clock": clock,
        "speed": sim.speed,
        "seed": sim.seed,
        "strategy_name": sim.strategy_name,
        "hol_policy": sim.config.hol_policy,
    }
