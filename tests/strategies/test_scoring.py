"""Unit tests for core scoring primitives (Phase 1).

Tests base_urgency, wait_bonus, contention_penalty, monotonicity,
and clinical plausibility invariants.
"""

from __future__ import annotations

import sys
from pathlib import Path
import unittest
from types import SimpleNamespace

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from strategies.scoring import (
    base_urgency,
    wait_bonus,
    contention_penalty,
    DEFAULT_WAIT_WEIGHT_PER_MIN,
    DEFAULT_WAIT_CAP,
    DEFAULT_CONTENTION_WEIGHT,
    DEFAULT_CONTENTION_THRESHOLD,
)


class TestScoringPrimitives(unittest.TestCase):
    """Test suite for strategies/scoring.py."""

    def test_base_urgency_values(self) -> None:
        """Verify exact hand-computed base urgency scores for ESI levels 1-5."""
        self.assertEqual(base_urgency(1), 100.0)
        self.assertEqual(base_urgency(2), 80.0)
        self.assertEqual(base_urgency(3), 60.0)
        self.assertEqual(base_urgency(4), 40.0)
        self.assertEqual(base_urgency(5), 20.0)

    def test_base_urgency_invalid(self) -> None:
        """Verify invalid urgency levels raise KeyError."""
        for invalid in [0, 6, -1, 10, 99]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(KeyError):
                    base_urgency(invalid)

    def test_wait_bonus_zero_and_negative(self) -> None:
        """Verify wait_bonus returns 0.0 for zero or negative waiting seconds."""
        self.assertEqual(wait_bonus(0), 0.0)
        self.assertEqual(wait_bonus(-10), 0.0)
        self.assertEqual(wait_bonus(-3600), 0.0)

    def test_wait_bonus_hand_computed_growth(self) -> None:
        """Verify hand-computed wait bonus progression at default rate (0.5 pt/min)."""
        # 60 seconds = 1 minute -> 0.5 points
        self.assertAlmostEqual(wait_bonus(60), 0.5)
        # 120 seconds = 2 minutes -> 1.0 points
        self.assertAlmostEqual(wait_bonus(120), 1.0)
        # 1200 seconds = 20 minutes -> 10.0 points
        self.assertAlmostEqual(wait_bonus(1200), 10.0)
        # 2400 seconds = 40 minutes -> 20.0 points
        self.assertAlmostEqual(wait_bonus(2400), 20.0)
        # 3600 seconds = 60 minutes -> 30.0 points
        self.assertAlmostEqual(wait_bonus(3600), 30.0)
        # 4800 seconds = 80 minutes -> 40.0 points (hits default cap)
        self.assertAlmostEqual(wait_bonus(4800), 40.0)

    def test_wait_bonus_cap_enforcement(self) -> None:
        """Verify wait bonus never exceeds the cap, even for massive wait times."""
        self.assertEqual(wait_bonus(4800), DEFAULT_WAIT_CAP)
        self.assertEqual(wait_bonus(7200), DEFAULT_WAIT_CAP)
        self.assertEqual(wait_bonus(86400), DEFAULT_WAIT_CAP)  # 24 hours
        self.assertEqual(wait_bonus(1_000_000), DEFAULT_WAIT_CAP)

        # Custom cap
        self.assertEqual(wait_bonus(10_000, cap=15.0), 15.0)

    def test_wait_bonus_monotonicity(self) -> None:
        """Verify wait_bonus is strictly non-decreasing with respect to wait_s."""
        prev = 0.0
        for wait_s in range(0, 10000, 30):
            current = wait_bonus(wait_s)
            self.assertGreaterEqual(
                current,
                prev,
                f"Monotonicity violated: wait_bonus({wait_s}) = {current} < previous = {prev}",
            )
            prev = current

    def test_clinical_safety_invariant_paper_cut_vs_heart_attack(self) -> None:
        """CRITICAL INVARIANT: Fresh critical patient always outranks stale non-urgent.
        
        A Level-5 patient with maximum possible wait time bonus must NEVER outrank
        a Level-1 (or even Level-2) patient who arrived just now with wait_s = 0.
        """
        fresh_level_1 = base_urgency(1) + wait_bonus(0)
        fresh_level_2 = base_urgency(2) + wait_bonus(0)
        stale_level_5_max_wait = base_urgency(5) + wait_bonus(10_000_000)

        # Stale Level 5 = 20.0 + 40.0 = 60.0
        self.assertEqual(stale_level_5_max_wait, 60.0)
        self.assertEqual(fresh_level_1, 100.0)
        self.assertEqual(fresh_level_2, 80.0)

        self.assertLess(
            stale_level_5_max_wait,
            fresh_level_1,
            "Clinical safety violated: stale Level 5 outranked fresh Level 1!",
        )
        self.assertLess(
            stale_level_5_max_wait,
            fresh_level_2,
            "Clinical safety violated: stale Level 5 outranked fresh Level 2!",
        )

    def test_contention_penalty_under_threshold(self) -> None:
        """Verify zero penalty when resource occupancy is below threshold (0.8)."""
        # 10 active, 5 free -> 50% occupied < 80%
        state = SimpleNamespace(
            active_capacities={"BED": 10, "DOCTOR": 4},
            free_counts={"BED": 5, "DOCTOR": 2},
        )
        penalty = contention_penalty({"BED": 1, "DOCTOR": 1}, state)
        self.assertEqual(penalty, 0.0)

    def test_contention_penalty_above_threshold_hand_computed(self) -> None:
        """Verify exact penalty calculation when occupancy is >= 80%."""
        # BED: 10 active, 1 free -> 90% occupied. Above 80% by 0.10.
        # Penalty = weight * (0.90 - 0.80) = 10.0 * 0.10 = 1.0.
        state = SimpleNamespace(
            active_capacities={"BED": 10, "DOCTOR": 4},
            free_counts={"BED": 1, "DOCTOR": 4},  # DOCTOR is 0% occupied
        )
        penalty = contention_penalty({"BED": 1, "DOCTOR": 1}, state)
        self.assertAlmostEqual(penalty, 1.0)

        # 100% occupied: 10 active, 0 free -> 100% occupied. Above 80% by 0.20.
        # Penalty = 10.0 * 0.20 = 2.0.
        state_full = SimpleNamespace(
            active_capacities={"BED": 10},
            free_counts={"BED": 0},
        )
        penalty_full = contention_penalty({"BED": 1}, state_full)
        self.assertAlmostEqual(penalty_full, 2.0)

    def test_contention_penalty_multiple_resources(self) -> None:
        """Verify penalty sums across multiple contended resource types in bundle."""
        # BED: 10 active, 1 free -> occ 0.90 -> penalty 10.0 * 0.10 = 1.0
        # ICU_BED: 4 active, 0 free -> occ 1.00 -> penalty 10.0 * 0.20 = 2.0
        state = SimpleNamespace(
            active_capacities={"BED": 10, "ICU_BED": 4},
            free_counts={"BED": 1, "ICU_BED": 0},
        )
        penalty = contention_penalty({"BED": 1, "ICU_BED": 1}, state)
        self.assertAlmostEqual(penalty, 3.0)

    def test_contention_penalty_bound_preserves_urgency_hierarchy(self) -> None:
        """Verify contention penalty cannot invert a 2-level urgency gap.
        
        Even with max contention (all required resources at 100% occupancy),
        penalty for a bundle of 3 resources is 3 * (10.0 * 0.2) = 6.0 points,
        which is much smaller than the 20-point step size between urgency levels.
        """
        state_full = SimpleNamespace(
            active_capacities={"BED": 10, "DOCTOR": 4, "NURSE": 8},
            free_counts={"BED": 0, "DOCTOR": 0, "NURSE": 0},
        )
        penalty = contention_penalty({"BED": 1, "DOCTOR": 1, "NURSE": 1}, state_full)
        self.assertAlmostEqual(penalty, 6.0)

        # Level 1 under max contention vs Level 2 with zero contention:
        # Level 1: 100.0 - 6.0 = 94.0 > Level 2: 80.0
        self.assertGreater(base_urgency(1) - penalty, base_urgency(2))

    def test_contention_penalty_edge_cases(self) -> None:
        """Verify zero division protection and empty requirements."""
        # Empty requirements
        state = SimpleNamespace(
            active_capacities={"BED": 10},
            free_counts={"BED": 0},
        )
        self.assertEqual(contention_penalty({}, state), 0.0)

        # Total capacity <= 0 (e.g. all units failed or off)
        state_zero_total = SimpleNamespace(
            active_capacities={"BED": 0},
            free_counts={"BED": 0},
        )
        self.assertEqual(contention_penalty({"BED": 1}, state_zero_total), 0.0)

        # Dict state fallback
        state_dict = {
            "active_capacities": {"BED": 10},
            "free_counts": {"BED": 1},
        }
        self.assertAlmostEqual(contention_penalty({"BED": 1}, state_dict), 1.0)


if __name__ == "__main__":
    unittest.main()
