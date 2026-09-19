"""Unit tests for Phase 7 stretch items: shortest_service_first and tuning harness."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest
from dataclasses import dataclass, field
from typing import Any

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategies import (
    STRATEGIES,
    get_strategy,
    shortest_predicted_service_first,
    make_custom_strategy,
    evaluate_parameters,
    grid_search,
)


@dataclass(frozen=True)
class MockPatientView:
    """Mock frozen PatientView matching AGENT.md §2."""
    id: int
    urgency: int
    arrival_time: int
    wait_s: int
    required: dict[str, int] = field(default_factory=dict)
    predicted_service_time: int | None = None
    remaining_service: int = 3600
    arrival_mode: str = "WALK_IN"
    department: str = "general"
    interruptions: int = 0


@dataclass(frozen=True)
class MockStateView:
    """Mock frozen StateView matching AGENT.md §2."""
    clock: int = 0
    free_counts: dict[str, int] = field(default_factory=dict)
    active_capacities: dict[str, int] = field(default_factory=dict)
    waiting: tuple[MockPatientView, ...] = ()
    in_treatment: int = 0
    flags: dict[str, Any] = field(default_factory=dict)


class TestPhase7Stretch(unittest.TestCase):
    """Test suite for Phase 7 stretch strategies and tuning."""

    def setUp(self) -> None:
        self.state = MockStateView(
            clock=1000,
            free_counts={"BED": 5, "DOCTOR": 2},
            active_capacities={"BED": 10, "DOCTOR": 4},
        )

    def test_shortest_service_first_registration(self) -> None:
        """Verify strategy is registered in registry."""
        self.assertIn("shortest_predicted_service_first", STRATEGIES)
        self.assertIs(
            get_strategy("shortest_predicted_service_first"),
            shortest_predicted_service_first,
        )

    def test_shortest_service_first_prefers_shorter_predicted_los(self) -> None:
        """Between two identical patients, the one with shorter predicted LOS ranks higher."""
        p_quick = MockPatientView(id=1, urgency=3, arrival_time=1000, wait_s=0, predicted_service_time=600)   # 10 min
        p_long = MockPatientView(id=2, urgency=3, arrival_time=1000, wait_s=0, predicted_service_time=14400) # 4 hrs

        score_quick = shortest_predicted_service_first(p_quick, self.state, 1000)
        score_long = shortest_predicted_service_first(p_long, self.state, 1000)

        self.assertGreater(score_quick, score_long)

    def test_shortest_service_first_preserves_urgency_tier(self) -> None:
        """Shortest LOS bonus (max 10 pts) cannot let a Level 3 beat a Level 1."""
        p_crit_long = MockPatientView(id=1, urgency=1, arrival_time=1000, wait_s=0, predicted_service_time=36000) # 10 hrs
        p_urg_short = MockPatientView(id=2, urgency=3, arrival_time=1000, wait_s=0, predicted_service_time=300)   # 5 min

        score_crit = shortest_predicted_service_first(p_crit_long, self.state, 1000)
        score_urg = shortest_predicted_service_first(p_urg_short, self.state, 1000)

        self.assertGreater(score_crit, score_urg)

    def test_make_custom_strategy(self) -> None:
        """Verify custom strategy factory produces callable with requested hyperparameters."""
        custom_strat = make_custom_strategy(weight_per_min=1.0, cap=50.0, contention_weight=20.0)
        p = MockPatientView(id=1, urgency=4, arrival_time=1000, wait_s=600)  # 10 min wait
        score = custom_strat(p, self.state, 1000)
        # Base: 40.0, wait: 10 min * 1.0 = 10.0 -> 50.0
        self.assertEqual(score, 50.0)

    def test_tuning_evaluation_and_grid_search(self) -> None:
        """Test parameter evaluation and grid search execution using live engine."""
        results = grid_search(
            weight_per_min_vals=(0.5,),
            cap_vals=(40.0,),
            contention_weights=(10.0,),
            seeds=(42,),
            horizon_s=1800,  # short horizon for rapid unit test
        )
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertIsInstance(res.score, float)
        self.assertEqual(res.weight_per_min, 0.5)
        self.assertEqual(res.cap, 40.0)


if __name__ == "__main__":
    unittest.main()
