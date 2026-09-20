"""Strategy A/B comparison router.

Conforms to AGENT.md §19.6.
Executes fair multi-strategy simulation comparison over identical patient arrival batches.
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from api.sim_service import SimulationService, get_sim_service
from api.schemas import CompareRequest
from strategies import STRATEGIES

router = APIRouter(prefix="/compare", tags=["Compare"])


@router.post("/")
async def compare_strategies_endpoint(
    req: CompareRequest,
    sim: SimulationService = Depends(get_sim_service),
):
    """Execute fair headless comparisons across strategies and return comparison metrics and deltas."""
    for name in req.strategies:
        if name not in STRATEGIES:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown strategy in comparison list: '{name}'. Available: {list(STRATEGIES.keys())}",
            )

    # Run CPU-bound headless simulations in threadpool to avoid blocking event loop
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sim.run_comparison(
            seed=req.seed,
            horizon_s=req.horizon_s,
            until_s=req.until_s,
            strategy_names=req.strategies,
            scripted=req.scripted,
        ),
    )
    return result
