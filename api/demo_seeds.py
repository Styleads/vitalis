"""Scripted demo scenarios and seed configurations for live demonstrations.

Conforms to AGENT.md §18 (Task 7).
"""

from __future__ import annotations

from typing import Any
from engine.types import ResourceType


DEMO_SCENARIOS: dict[str, dict[str, Any]] = {
    "queue_jump": {
        "description": "Critical patient arriving late jumps ahead of an earlier low-urgency patient",
        "seed": 101,
        "speed": 60.0,
        "strategy": "urgency_wait",
        "scripted": [],
    },
    "icu_contention": {
        "description": "Two Level-1s, one ICU bed -> second waits; BACKFILL lets Level-4 start",
        "seed": 202,
        "speed": 60.0,
        "strategy": "urgency_wait",
        "scripted": [],
    },
    "starvation": {
        "description": "Shows urgency_only starving Level 5 vs urgency_wait bounding wait time",
        "seed": 303,
        "speed": 120.0,
        "strategy": "urgency_only",
        "scripted": [],
    },
    "surge_demo": {
        "description": "Scripted patient arrival surge (3x multiplier for 1 hour at t=1800s)",
        "seed": 404,
        "speed": 60.0,
        "strategy": "urgency_wait",
        "scripted": [
            (1800, "surge", (3.0, 3600)),
        ],
    },
    "full_demo": {
        "description": "The complete demo scenario: surge at 30m, nurse shortage at 1h, equipment failure at 1.5h",
        "seed": 505,
        "speed": 60.0,
        "strategy": "urgency_wait_utilization",
        "scripted": [
            (1800, "surge", (3.0, 3600)),
            (3600, "capacity", (ResourceType.NURSE, 8)),
            (5400, "fail", (2, 1800)),
        ],
    },
}
