"""
engine/__init__.py
==================
Public exports for the engine package.  Spec §12.

These are the names B, C, and D import.  Do not remove or rename them
without announcing the change to the team.
"""

from engine.types import (
    ResourceType,
    Patient,
    Unit,
    PatientView,
    StateView,
    Event,
    UnitStatus,
    PatientStatus,
    ArrivalMode,
)
from engine.config import EngineConfig, ScriptedAction, default_config
from engine.arrivals import generate_arrivals, make_patient
from engine.resources import ResourcePool, try_reserve, release
from engine.engine import Engine
from engine.invariants import assert_invariants
from engine.headless import run_headless

__all__ = [
    # types
    "ResourceType",
    "Patient",
    "Unit",
    "PatientView",
    "StateView",
    "Event",
    "UnitStatus",
    "PatientStatus",
    "ArrivalMode",
    # config
    "EngineConfig",
    "ScriptedAction",
    "default_config",
    # arrivals
    "generate_arrivals",
    "make_patient",
    # resources
    "ResourcePool",
    "try_reserve",
    "release",
    # engine
    "Engine",
    # invariants
    "assert_invariants",
    # headless
    "run_headless",
]
