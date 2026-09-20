"""Unit tests for strategies (Phase 2).

Tests urgency_only and urgency_wait strategies, including exact verification
against the sample snapshot in AGENT.md Part 1.3 / §8.
"""

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
    urgency_only,
    urgency_wait,
    urgency_wait_utilization,
)


@dataclass(frozen=True)
class MockPatientView:
    """Mock frozen PatientView matching AGENT.md §2 / §10.4."""
    id: int
    urgency: int
    arrival_time: int
    wait_s: int
    required: dict[str, int] = field(default_factory=dict)
    predicted_service_time: int | None = None
    remaining_service: int = 0
    arrival_mode: str = "WALK_IN"
    department: str = "general"
    interruptions: int = 0


@dataclass(frozen=True)
class MockStateView:
    """Mock frozen StateView matching AGENT.md §2 / §10.4."""
    clock: int = 0
    free_counts: dict[str, int] = field(default_factory=dict)
    active_capacities: dict[str, int] = field(default_factory=dict)
    waiting: tuple[MockPatientView, ...] = ()
    in_treatment: int = 0
    flags: dict[str, Any] = field(default_factory=dict)


class TestStrategies(unittest.TestCase):
    """Test suite for strategies/urgency_only.py and strategies/urgency_wait.py."""

    def setUp(self) -> None:
        self.state = MockStateView(
            clock=9000,
            free_counts={"BED": 5, "ICU_BED": 0, "DOCTOR": 0, "NURSE": 1},
            active_capacities={"BED": 6, "ICU_BED": 1, "DOCTOR": 2, "NURSE": 4},
        )

    def test_registry_contains_strategies(self) -> None:
        """Verify strategies are registered and accessible via get_strategy."""
        self.assertIn("urgency_only", STRATEGIES)
        self.assertIn("urgency_wait", STRATEGIES)
        self.assertIn("urgency_wait_utilization", STRATEGIES)
        self.assertIs(get_strategy("urgency_only"), urgency_only)
        self.assertIs(get_strategy("urgency_wait"), urgency_wait)
        self.assertIs(get_strategy("urgency_wait_utilization"), urgency_wait_utilization)

        with self.assertRaises(KeyError):
            get_strategy("invalid_strategy_name")

    def test_urgency_only_ignores_wait_time(self) -> None:
        """Verify urgency_only returns base urgency regardless of wait_s."""
        now = 9000

        p_fresh_1 = MockPatientView(id=1, urgency=1, arrival_time=now, wait_s=0)
        p_stale_1 = MockPatientView(id=2, urgency=1, arrival_time=0, wait_s=9000)
        p_stale_5 = MockPatientView(id=3, urgency=5, arrival_time=0, wait_s=90000)

        # Level 1 always scores 100.0
        self.assertEqual(urgency_only(p_fresh_1, self.state, now), 100.0)
        self.assertEqual(urgency_only(p_stale_1, self.state, now), 100.0)

        # Level 5 always scores 20.0
        self.assertEqual(urgency_only(p_stale_5, self.state, now), 20.0)

        # Starvation: Fresh Level 1 outranks Level 5 that has waited 25 hours
        self.assertGreater(
            urgency_only(p_fresh_1, self.state, now),
            urgency_only(p_stale_5, self.state, now),
        )

    def test_urgency_wait_exact_spec_snapshot_match(self) -> None:
        """CRITICAL TEST: Exact match against the sample snapshot in AGENT.md §8 / Part 1.3.
        
        Spec lines 70-72:
          - Patient 14: urgency 1, wait_s 120  -> score 101.0
          - Patient 9:  urgency 3, wait_s 2700 -> score 82.5
          - Patient 12: urgency 4, wait_s 1500 -> score 52.5
        """
        now = 9000

        p14 = MockPatientView(
            id=14, urgency=1, arrival_time=8880, wait_s=120,
            required={"ICU_BED": 1, "DOCTOR": 1, "NURSE": 2},
        )
        p9 = MockPatientView(
            id=9, urgency=3, arrival_time=6300, wait_s=2700,
            required={"BED": 1, "DOCTOR": 1, "NURSE": 1},
        )
        p12 = MockPatientView(
            id=12, urgency=4, arrival_time=7500, wait_s=1500,
            required={"BED": 1, "DOCTOR": 1},
        )

        score_p14 = urgency_wait(p14, self.state, now)
        score_p9 = urgency_wait(p9, self.state, now)
        score_p12 = urgency_wait(p12, self.state, now)

        self.assertAlmostEqual(score_p14, 101.0, places=5)
        self.assertAlmostEqual(score_p9, 82.5, places=5)
        self.assertAlmostEqual(score_p12, 52.5, places=5)

        # Queue order by score descending: p14 > p9 > p12
        self.assertGreater(score_p14, score_p9)
        self.assertGreater(score_p9, score_p12)

    def test_urgency_wait_starvation_prevention(self) -> None:
        """Verify waiting patients within the same urgency level gain priority over fresh arrivals."""
        now = 3600
        p_fresh = MockPatientView(id=1, urgency=3, arrival_time=3600, wait_s=0)
        p_waiting_30min = MockPatientView(id=2, urgency=3, arrival_time=1800, wait_s=1800)

        # Fresh level 3: 60.0
        # Waiting 30 min level 3: 60.0 + (1800/60)*0.5 = 60.0 + 15.0 = 75.0
        score_fresh = urgency_wait(p_fresh, self.state, now)
        score_waiting = urgency_wait(p_waiting_30min, self.state, now)

        self.assertEqual(score_fresh, 60.0)
        self.assertEqual(score_waiting, 75.0)
        self.assertGreater(score_waiting, score_fresh)

    def test_urgency_wait_clinical_priority_bound(self) -> None:
        """Verify that a stale Level-5 patient cannot overtake a fresh Level-1 or Level-2."""
        now = 100_000
        p_critical_fresh = MockPatientView(id=1, urgency=1, arrival_time=now, wait_s=0)
        p_emergent_fresh = MockPatientView(id=2, urgency=2, arrival_time=now, wait_s=0)
        p_nonurgent_stale = MockPatientView(id=3, urgency=5, arrival_time=0, wait_s=100_000)

        score_crit = urgency_wait(p_critical_fresh, self.state, now)
        score_emerg = urgency_wait(p_emergent_fresh, self.state, now)
        score_nonurgent = urgency_wait(p_nonurgent_stale, self.state, now)

        # Level 5 max capped score = 20.0 + 40.0 = 60.0
        self.assertEqual(score_nonurgent, 60.0)
        self.assertEqual(score_crit, 100.0)
        self.assertEqual(score_emerg, 80.0)

        self.assertGreater(score_crit, score_nonurgent)
        self.assertGreater(score_emerg, score_nonurgent)

    def test_urgency_wait_utilization_under_threshold(self) -> None:
        """When occupancy is below threshold (0.8), urgency_wait_utilization == urgency_wait."""
        now = 9000
        # BED 50% occupied (free 5/10), DOCTOR 50% occupied (free 1/2)
        state_low_load = MockStateView(
            clock=now,
            free_counts={"BED": 5, "DOCTOR": 1},
            active_capacities={"BED": 10, "DOCTOR": 2},
        )
        p = MockPatientView(
            id=1, urgency=2, arrival_time=8400, wait_s=600,
            required={"BED": 1, "DOCTOR": 1},
        )
        score_uw = urgency_wait(p, state_low_load, now)
        score_uwu = urgency_wait_utilization(p, state_low_load, now)

        self.assertEqual(score_uwu, score_uw)
        # 80.0 + (600/60)*0.5 = 85.0
        self.assertEqual(score_uwu, 85.0)

    def test_urgency_wait_utilization_hand_computed_penalty(self) -> None:
        """Verify hand-computed score with contention penalty applied above 80% occupancy."""
        now = 9000
        # ICU_BED 100% occupied (free 0/1) -> penalty = 10.0 * (1.0 - 0.8) = 2.0
        # DOCTOR 100% occupied (free 0/2) -> penalty = 10.0 * (1.0 - 0.8) = 2.0
        # Total penalty = 4.0
        state_contended = MockStateView(
            clock=now,
            free_counts={"BED": 5, "ICU_BED": 0, "DOCTOR": 0, "NURSE": 2},
            active_capacities={"BED": 6, "ICU_BED": 1, "DOCTOR": 2, "NURSE": 4},
        )
        p = MockPatientView(
            id=14, urgency=1, arrival_time=8880, wait_s=120,
            required={"ICU_BED": 1, "DOCTOR": 1},
        )
        # Base: 100.0, wait: 1.0, penalty: 4.0 -> 97.0
        score = urgency_wait_utilization(p, state_contended, now)
        self.assertAlmostEqual(score, 97.0)

    def test_urgency_wait_utilization_deprioritizes_contended_bundle(self) -> None:
        """Between two identical patients, the one needing the contended resource ranks lower."""
        now = 5000
        state = MockStateView(
            clock=now,
            free_counts={"BED": 4, "ICU_BED": 0, "DOCTOR": 1},
            active_capacities={"BED": 10, "ICU_BED": 2, "DOCTOR": 2},
        )
        # Both Urgency 3, arrived at same time
        p_regular = MockPatientView(id=1, urgency=3, arrival_time=4400, wait_s=600, required={"BED": 1})
        p_contended = MockPatientView(id=2, urgency=3, arrival_time=4400, wait_s=600, required={"ICU_BED": 1})

        score_regular = urgency_wait_utilization(p_regular, state, now)
        score_contended = urgency_wait_utilization(p_contended, state, now)

        self.assertGreater(score_regular, score_contended)

    def test_urgency_wait_utilization_never_inverts_urgency_gap(self) -> None:
        """Verify that contention penalty can never cause a Level-3 to beat a Level-1 arrival."""
        now = 1000
        # Fully saturated system
        state_maxed = MockStateView(
            clock=now,
            free_counts={"BED": 0, "ICU_BED": 0, "DOCTOR": 0, "NURSE": 0},
            active_capacities={"BED": 10, "ICU_BED": 2, "DOCTOR": 4, "NURSE": 8},
        )
        # Fresh critical patient requiring heavily contended bundle
        p_crit = MockPatientView(
            id=1, urgency=1, arrival_time=now, wait_s=0,
            required={"ICU_BED": 1, "DOCTOR": 1, "NURSE": 2},
        )
        # Fresh urgent patient needing uncongested or no resources
        p_urgent = MockPatientView(
            id=2, urgency=3, arrival_time=now, wait_s=0,
            required={},
        )
        score_crit = urgency_wait_utilization(p_crit, state_maxed, now)
        score_urgent = urgency_wait_utilization(p_urgent, state_maxed, now)

        self.assertGreater(
            score_crit,
            score_urgent,
            "Contention penalty erroneously inverted a genuine clinical urgency gap!",
        )

    def test_predicted_service_time_unused(self) -> None:
        """Fairness guarantee: predicted_service_time must NOT alter scores in required strategies."""
        now = 1000
        p_short = MockPatientView(id=1, urgency=2, arrival_time=now, wait_s=60, predicted_service_time=600)
        p_long = MockPatientView(id=2, urgency=2, arrival_time=now, wait_s=60, predicted_service_time=36000)

        for strat in [urgency_only, urgency_wait, urgency_wait_utilization]:
            with self.subTest(strategy=strat.__name__):
                score_short = strat(p_short, self.state, now)
                score_long = strat(p_long, self.state, now)
                self.assertEqual(
                    score_short,
                    score_long,
                    f"{strat.__name__} penalized a patient for having a longer predicted service time!",
                )

    def test_real_engine_types_compatibility(self) -> None:
        """Verify strategies evaluate against Person A's real engine.types classes."""
        try:
            from engine.types import PatientView, StateView, ResourceType
        except ImportError:
            self.skipTest("engine.types not available")

        pv = PatientView(
            id=99,
            urgency=1,
            arrival_time=1000,
            wait_s=300,
            required={ResourceType.ICU_BED: 1, ResourceType.DOCTOR: 1},
            predicted_service_time=3600,
            remaining_service=3600,
            arrival_mode="WALK_IN",
            department="general",
            interruptions=0,
        )
        sv = StateView(
            clock=1300,
            free={ResourceType.ICU_BED: 0, ResourceType.DOCTOR: 1},
            total={ResourceType.ICU_BED: 2, ResourceType.DOCTOR: 4},
            waiting=(),
            in_treatment=3,
            flags={"arrival_multiplier": 1.0},
        )

        for name, strat in STRATEGIES.items():
            with self.subTest(strategy=name):
                score = strat(pv, sv, 1300)
                self.assertIsInstance(score, float)
                self.assertGreater(score, 0.0)


if __name__ == "__main__":
    unittest.main()

