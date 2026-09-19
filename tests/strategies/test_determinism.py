"""Determinism and purity test suite for strategies (Phase 4).

Verifies:
1. Pure functions: Same (PatientView, StateView, now) -> identical float, always.
2. Zero side effects: No mutation of inputs, no hidden state, no global RNG reliance.
3. Robustness: Never raises on full domain of valid inputs (urgency 1-5, empty/multi-resource bundles).
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

from strategies import STRATEGIES, urgency_only, urgency_wait, urgency_wait_utilization


@dataclass(frozen=True)
class MockPatientView:
    """Mock frozen PatientView matching AGENT.md §2."""
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
    """Mock frozen StateView matching AGENT.md §2."""
    clock: int = 0
    free_counts: dict[str, int] = field(default_factory=dict)
    active_capacities: dict[str, int] = field(default_factory=dict)
    waiting: tuple[MockPatientView, ...] = ()
    in_treatment: int = 0
    flags: dict[str, Any] = field(default_factory=dict)


class TestDeterminismAndPurity(unittest.TestCase):
    """Test suite for deterministic behavior of scoring strategies."""

    def setUp(self) -> None:
        self.patient = MockPatientView(
            id=42,
            urgency=2,
            arrival_time=1200,
            wait_s=600,
            required={"BED": 1, "DOCTOR": 1, "NURSE": 1},
            predicted_service_time=1800,
        )
        self.state = MockStateView(
            clock=1800,
            free_counts={"BED": 1, "DOCTOR": 0, "NURSE": 2},
            active_capacities={"BED": 10, "DOCTOR": 2, "NURSE": 4},
        )
        self.now = 1800

    def test_identical_outputs_across_repeated_calls(self) -> None:
        """Call each strategy 1,000 times; output must be strictly identical floats."""
        for name, strategy in STRATEGIES.items():
            with self.subTest(strategy=name):
                first_score = strategy(self.patient, self.state, self.now)
                for _ in range(1000):
                    subsequent_score = strategy(self.patient, self.state, self.now)
                    self.assertEqual(
                        first_score,
                        subsequent_score,
                        f"Non-deterministic scoring detected in {name}!",
                    )

    def test_no_input_mutation(self) -> None:
        """Confirm that calling strategies leaves input objects completely untouched."""
        patient_copy = MockPatientView(
            id=self.patient.id,
            urgency=self.patient.urgency,
            arrival_time=self.patient.arrival_time,
            wait_s=self.patient.wait_s,
            required=dict(self.patient.required),
            predicted_service_time=self.patient.predicted_service_time,
        )
        state_copy = MockStateView(
            clock=self.state.clock,
            free_counts=dict(self.state.free_counts),
            active_capacities=dict(self.state.active_capacities),
        )

        for name, strategy in STRATEGIES.items():
            with self.subTest(strategy=name):
                _ = strategy(self.patient, self.state, self.now)
                self.assertEqual(self.patient, patient_copy)
                self.assertEqual(self.state, state_copy)

    def test_full_urgency_domain_never_raises(self) -> None:
        """Confirm strategies evaluate all valid urgency levels (1-5) safely."""
        for name, strategy in STRATEGIES.items():
            for urgency in (1, 2, 3, 4, 5):
                p = MockPatientView(id=1, urgency=urgency, arrival_time=0, wait_s=120)
                try:
                    score = strategy(p, self.state, self.now)
                    self.assertIsInstance(score, float)
                except Exception as e:
                    self.fail(f"Strategy {name} raised {e} on valid urgency {urgency}")

    def test_bundle_variations_never_raise(self) -> None:
        """Confirm strategies evaluate empty, single, and complex bundles without error."""
        bundles = [
            {},
            {"DOCTOR": 1},
            {"BED": 1, "DOCTOR": 1, "NURSE": 2},
            {"ICU_BED": 1, "DOCTOR": 2, "NURSE": 3, "OR": 1},
            {"UNKNOWN_TYPE": 1},  # robust to types not in state
        ]
        for name, strategy in STRATEGIES.items():
            for bundle in bundles:
                p = MockPatientView(id=1, urgency=2, arrival_time=0, wait_s=100, required=bundle)
                try:
                    score = strategy(p, self.state, self.now)
                    self.assertIsInstance(score, float)
                except Exception as e:
                    self.fail(f"Strategy {name} raised {e} on bundle {bundle}")


if __name__ == "__main__":
    unittest.main()
