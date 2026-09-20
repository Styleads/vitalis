"""SimulationService: Single owner of the Engine instance and the asyncio tick loop.

Conforms to AGENT.md Part IV §17.4, §18 (Tasks 2-6), §21.1.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any, Optional

from engine import (
    Engine,
    EngineConfig,
    ResourceType,
    default_config,
    generate_arrivals,
    run_headless,
)
from strategies import (
    STRATEGIES,
    get_strategy,
    to_display_stats,
    compare_strategies,
)
from api.ws import manager
from api.demo_seeds import DEMO_SCENARIOS

logger = logging.getLogger("medflow.sim")


class SimulationService:
    """Manages the lifecycle, wall-clock tick loop, and mutations of the MedFlow Engine."""

    def __init__(self) -> None:
        self.config: EngineConfig = default_config()
        self.seed: int = 42
        self.speed: float = 60.0  # 60 sim seconds per real second
        self.tick_interval: float = 0.5  # wall clock seconds between steps
        self.strategy_name: str = "urgency_wait"
        self.running: bool = False

        self.lock = asyncio.Lock()
        self.tick_task: Optional[asyncio.Task] = None
        self.engine: Optional[Engine] = None

        # Build initial default engine
        self._initialize_engine(seed=self.seed, strategy_name=self.strategy_name)

    def _initialize_engine(
        self,
        seed: int,
        strategy_name: str,
        horizon_s: int = 86400,
        scripted: list[Any] = (),
    ) -> None:
        """Internal helper to instantiate Engine with deterministic arrivals."""
        self.seed = seed
        self.strategy_name = strategy_name
        strategy_fn = get_strategy(strategy_name)
        arrivals = generate_arrivals(seed, self.config, horizon_s)
        self.engine = Engine(
            self.config,
            arrivals,
            strategy_fn,
            seed,
            scripted=list(scripted),
        )

    async def start(
        self,
        seed: int = 42,
        horizon_s: int = 86400,
        speed: float = 60.0,
        strategy: str = "urgency_wait",
        demo: Optional[str] = None,
    ) -> dict[str, Any]:
        """Start or re-initialize simulation and start the tick loop."""
        async with self.lock:
            self.speed = speed
            if demo and demo in DEMO_SCENARIOS:
                await self._load_demo_locked(demo)
            else:
                self._initialize_engine(seed=seed, strategy_name=strategy, horizon_s=horizon_s)

            self.running = True
            self._ensure_tick_task()
            snapshot = self.engine.snapshot()

        await manager.broadcast_state(snapshot)
        return snapshot

    async def pause(self) -> dict[str, Any]:
        """Pause the simulation clock advance."""
        async with self.lock:
            self.running = False
            clock = self.engine.clock if self.engine else 0
        return {"running": False, "clock": clock}

    async def resume(self) -> dict[str, Any]:
        """Resume the simulation clock advance."""
        async with self.lock:
            self.running = True
            self._ensure_tick_task()
            clock = self.engine.clock if self.engine else 0
        return {"running": True, "clock": clock}

    async def set_speed(self, speed: float) -> dict[str, Any]:
        """Update simulation speed multiplier."""
        async with self.lock:
            self.speed = max(0.1, float(speed))
        return {"speed": self.speed}

    async def reset(self, seed: Optional[int] = None, demo: Optional[str] = None) -> dict[str, Any]:
        """Reset the simulation to initial state."""
        async with self.lock:
            target_seed = seed if seed is not None else self.seed
            if demo and demo in DEMO_SCENARIOS:
                await self._load_demo_locked(demo)
            else:
                self._initialize_engine(seed=target_seed, strategy_name=self.strategy_name)
            snapshot = self.engine.snapshot()

        await manager.broadcast_state(snapshot)
        return snapshot

    async def load_demo(self, name: str) -> dict[str, Any]:
        """Load a named scripted demo scenario."""
        if name not in DEMO_SCENARIOS:
            raise KeyError(f"Unknown demo scenario: {name}. Available: {list(DEMO_SCENARIOS.keys())}")
        async with self.lock:
            await self._load_demo_locked(name)
            snapshot = self.engine.snapshot()

        await manager.broadcast_state(snapshot)
        return snapshot

    async def _load_demo_locked(self, name: str) -> None:
        """Internal helper to load demo while holding lock."""
        scenario = DEMO_SCENARIOS[name]
        self.speed = scenario.get("speed", self.speed)
        self.strategy_name = scenario.get("strategy", self.strategy_name)
        self._initialize_engine(
            seed=scenario["seed"],
            strategy_name=self.strategy_name,
            scripted=scenario.get("scripted", []),
        )

    async def step_manual(self) -> dict[str, Any]:
        """Manually execute a single step (for /allocate when paused)."""
        async with self.lock:
            if self.running:
                raise RuntimeError("Cannot manually step while simulation is actively running.")
            events = self.engine.step()
            snapshot = self.engine.snapshot()

        await manager.broadcast_state(snapshot)
        return {"events": events, "snapshot": snapshot}

    def get_snapshot(self) -> dict[str, Any]:
        """Return fresh JSON-safe copy of engine snapshot."""
        if not self.engine:
            return {}
        return self.engine.snapshot()

    def get_stats(self) -> dict[str, Any]:
        """Return display stats transformed from raw engine stats."""
        if not self.engine:
            return {}
        raw = self.engine.stats_raw()
        return to_display_stats(raw)

    async def set_strategy(self, name: str) -> dict[str, Any]:
        """Switch active scheduling strategy and immediately re-sort queue."""
        strat_fn = get_strategy(name)  # raises KeyError if invalid
        async with self.lock:
            self.strategy_name = name
            self.engine.set_strategy(strat_fn)
            self.engine.run_until(self.engine.clock)
            snapshot = self.engine.snapshot()

        await manager.broadcast_state(snapshot)
        return {"active": self.strategy_name, "snapshot": snapshot}

    async def inject_surge(self, multiplier: float, duration_s: int) -> dict[str, Any]:
        """Inject patient arrival surge scenario."""
        async with self.lock:
            self.engine.inject_surge(multiplier, duration_s)
            self.engine.run_until(self.engine.clock)
            snapshot = self.engine.snapshot()

        await manager.broadcast_state(snapshot)
        return snapshot

    async def set_capacity(self, rtype: ResourceType, n: int) -> dict[str, Any]:
        """Adjust resource capacity (staff shortage or recovery)."""
        async with self.lock:
            self.engine.set_capacity(rtype, n)
            self.engine.run_until(self.engine.clock)
            snapshot = self.engine.snapshot()

        await manager.broadcast_state(snapshot)
        return snapshot

    async def fail_resource(self, unit_id: int, duration_s: int) -> dict[str, Any]:
        """Trigger temporary failure on a specific resource unit."""
        async with self.lock:
            self.engine.fail_resource(unit_id, duration_s)
            self.engine.run_until(self.engine.clock)
            snapshot = self.engine.snapshot()

        await manager.broadcast_state(snapshot)
        return snapshot

    def run_comparison(
        self,
        seed: int = 42,
        horizon_s: int = 14400,
        until_s: int = 7200,
        strategy_names: Sequence[str] = ("urgency_only", "urgency_wait", "urgency_wait_utilization"),
        scripted: Sequence[Any] = (),
    ) -> dict[str, Any]:
        """Execute headless comparisons across identical arrivals and diff results."""
        arrivals = generate_arrivals(seed, self.config, horizon_s)
        raw_results: dict[str, Any] = {}

        for name in strategy_names:
            strat_fn = get_strategy(name)
            # run_headless internally deep-copies arrivals so the list remains pristine
            raw = run_headless(
                self.config,
                arrivals,
                strat_fn,
                seed=seed,
                until_s=until_s,
                scripted=scripted,
            )
            raw_results[name] = raw

        comparison = compare_strategies(raw_results)
        return {
            "raw": raw_results,
            "comparison": comparison,
        }

    def _ensure_tick_task(self) -> None:
        """Ensure background tick task is active."""
        if self.tick_task is None or self.tick_task.done():
            self.tick_task = asyncio.create_task(self._tick_loop())

    async def _tick_loop(self) -> None:
        """Background loop advancing simulation clock by wall-clock interval."""
        logger.info("Simulation tick loop started.")
        try:
            while True:
                await asyncio.sleep(self.tick_interval)
                if not self.running or not self.engine:
                    continue

                async with self.lock:
                    step_delta = int(self.speed * self.tick_interval)
                    target_time = self.engine.clock + max(1, step_delta)
                    self.engine.run_until(target_time)
                    snapshot = self.engine.snapshot()

                await manager.broadcast_state(snapshot)
        except asyncio.CancelledError:
            logger.info("Simulation tick loop cancelled.")
        except Exception as e:
            logger.exception("Unexpected error in simulation tick loop: %s", e)

    async def shutdown(self) -> None:
        """Gracefully stop tick loop on application shutdown."""
        self.running = False
        if self.tick_task and not self.tick_task.done():
            self.tick_task.cancel()
            try:
                await self.tick_task
            except asyncio.CancelledError:
                pass


# Global singleton instance
sim_service = SimulationService()


def get_sim_service() -> SimulationService:
    """FastAPI dependency for accessing the simulation service."""
    return sim_service
