"""Pydantic schemas for the MedFlow API wire contract.

Conforms to AGENT.md Part IV §17.3, §19.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class SimStartRequest(BaseModel):
    seed: int = 42
    horizon_s: int = 86400  # 24 simulated hours
    speed: float = Field(default=60.0, gt=0, description="Simulated seconds per real second")
    strategy: str = "urgency_wait"
    demo: Optional[str] = None


class SpeedRequest(BaseModel):
    speed: float = Field(gt=0, description="Simulated seconds per real second")


class ResetRequest(BaseModel):
    seed: Optional[int] = 42
    demo: Optional[str] = None


class StrategyRequest(BaseModel):
    name: str = Field(description="Strategy name (e.g. urgency_only, urgency_wait, urgency_wait_utilization)")


class SurgeRequest(BaseModel):
    multiplier: float = Field(default=3.0, gt=1.0, description="Arrival multiplier during surge")
    duration_s: int = Field(default=3600, gt=0, description="Surge duration in simulated seconds")


class CapacityRequest(BaseModel):
    type: str = Field(description="ResourceType name, e.g. NURSE, DOCTOR, BED, ICU_BED")
    n: int = Field(ge=0, description="New target capacity")


class FailRequest(BaseModel):
    unit_id: int = Field(gt=0, description="Unit ID to fail")
    duration_s: int = Field(default=1800, gt=0, description="Failure duration in simulated seconds")


class ScenarioRequest(BaseModel):
    kind: str = Field(description="Scenario kind: surge, capacity, or fail")
    multiplier: Optional[float] = None
    duration_s: Optional[int] = None
    type: Optional[str] = None
    n: Optional[int] = None
    unit_id: Optional[int] = None


class CompareRequest(BaseModel):
    seed: int = 42
    horizon_s: int = 14400  # 4 hours
    until_s: int = 7200     # 2 hours
    strategies: list[str] = Field(
        default_factory=lambda: [
            "urgency_only",
            "urgency_wait",
            "urgency_wait_utilization",
        ]
    )
    scripted: list[Any] = Field(default_factory=list)


class DemoLoadRequest(BaseModel):
    name: str = Field(description="Name of the scripted demo scenario")
