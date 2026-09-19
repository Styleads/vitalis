"""Unit tests for stats display and strategy comparison (Phase 5).

Verifies:
1. to_display_stats correctly transforms Engine.stats_raw() schema.
2. Guarded division by zero when available_s == 0.
3. Accurate wait times, percentiles, utilization %, and starvation indicators.
4. compare_strategies diffs multiple runs and outputs dashboard-ready tables and deltas.
"""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategies.stats_display import to_display_stats, compare_strategies


class TestStatsDisplay(unittest.TestCase):
    """Test suite for strategies/stats_display.py."""

    def test_to_display_stats_hand_computed(self) -> None:
        """Verify exact values from hand-constructed stats_raw fixture."""
        raw_fixture = {
            "patients": [
                # Urgency 1: wait = 120s
                {"id": 1, "urgency": 1, "arrival": 1000, "start": 1120, "end": 5000, "status": "DISCHARGED"},
                # Urgency 1: wait = 180s
                {"id": 2, "urgency": 1, "arrival": 2000, "start": 2180, "end": 6000, "status": "DISCHARGED"},
                # Urgency 3: wait = 600s
                {"id": 3, "urgency": 3, "arrival": 3000, "start": 3600, "end": 7000, "status": "DISCHARGED"},
                # Urgency 5: wait = 4000s (> 1 hr -> starved)
                {"id": 4, "urgency": 5, "arrival": 1000, "start": 5000, "end": 6000, "status": "DISCHARGED"},
                # Urgency 5: not yet started (still waiting) -> wait not finalised
                {"id": 5, "urgency": 5, "arrival": 4000, "start": None, "end": None, "status": "WAITING"},
            ],
            "busy_s": {
                "BED": 8000,
                "ICU_BED": 5000,
                "DOCTOR": 9000,
                "OFF_DEVICE": 0,
            },
            "available_s": {
                "BED": 10000,      # 80.0%
                "ICU_BED": 5000,   # 100.0%
                "DOCTOR": 10000,   # 90.0%
                "OFF_DEVICE": 0,   # 0 available (fully OFF/FAILED) -> guard div-by-zero
            },
            "counts": {
                "arrived": 5,
                "treated": 4,
                "waiting": 1,
                "in_treatment": 0,
                "interrupted": 0,
            },
        }

        display = to_display_stats(raw_fixture)

        # 4 started patients: waits = [120, 180, 600, 4000]
        # Sum = 4900 / 4 = 1225.0s
        self.assertEqual(display["wait_times"]["overall"]["avg_wait_s"], 1225.0)
        self.assertEqual(display["wait_times"]["overall"]["max_wait_s"], 4000.0)
        self.assertEqual(display["wait_times"]["overall"]["sample_count"], 4)

        # By urgency
        u1 = display["wait_times"]["by_urgency"][1]
        self.assertEqual(u1["avg_wait_s"], 150.0)  # (120 + 180) / 2
        self.assertEqual(u1["sample_count"], 2)

        u3 = display["wait_times"]["by_urgency"][3]
        self.assertEqual(u3["avg_wait_s"], 600.0)
        self.assertEqual(u3["sample_count"], 1)

        u5 = display["wait_times"]["by_urgency"][5]
        self.assertEqual(u5["avg_wait_s"], 4000.0)
        self.assertEqual(u5["sample_count"], 1)

        # Utilization % (guarded div-by-zero)
        self.assertEqual(display["utilization_pct"]["BED"], 80.0)
        self.assertEqual(display["utilization_pct"]["ICU_BED"], 100.0)
        self.assertEqual(display["utilization_pct"]["DOCTOR"], 90.0)
        self.assertEqual(display["utilization_pct"]["OFF_DEVICE"], 0.0)

        # Starvation
        self.assertEqual(display["starvation"]["starved_level_4_5_count"], 1)
        self.assertEqual(display["starvation"]["total_level_4_5"], 1)
        self.assertEqual(display["starvation"]["starvation_pct"], 100.0)

    def test_compare_strategies_produces_summary_and_deltas(self) -> None:
        """Verify side-by-side strategy comparison across identical batches."""
        raw_urgency_only = {
            "patients": [
                # Critical treated instantly, low urgency starved
                {"id": 1, "urgency": 1, "arrival": 0, "start": 60, "end": 1000, "status": "DISCHARGED"},
                {"id": 2, "urgency": 5, "arrival": 0, "start": 7200, "end": 8000, "status": "DISCHARGED"},
            ],
            "busy_s": {"BED": 6000},
            "available_s": {"BED": 10000},
            "counts": {"arrived": 2, "treated": 2, "waiting": 0, "in_treatment": 0, "interrupted": 0},
        }

        raw_urgency_wait = {
            "patients": [
                # Critical treated fast, low urgency bounded wait
                {"id": 1, "urgency": 1, "arrival": 0, "start": 90, "end": 1000, "status": "DISCHARGED"},
                {"id": 2, "urgency": 5, "arrival": 0, "start": 1800, "end": 2600, "status": "DISCHARGED"},
            ],
            "busy_s": {"BED": 7000},
            "available_s": {"BED": 10000},
            "counts": {"arrived": 2, "treated": 2, "waiting": 0, "in_treatment": 0, "interrupted": 0},
        }

        results = {
            "urgency_only": raw_urgency_only,
            "urgency_wait": raw_urgency_wait,
        }

        comparison = compare_strategies(results)

        # Verify summary table exists and is populated
        self.assertIn("summary_table", comparison)
        self.assertEqual(len(comparison["summary_table"]), 2)

        # Verify deltas vs urgency_only baseline
        deltas = comparison["deltas_vs_baseline"]
        self.assertIn("urgency_wait", deltas)

        uw_delta = deltas["urgency_wait"]
        # Non-urgent wait decreased: 1800 - 7200 = -5400s
        self.assertEqual(uw_delta["nonurgent_wait_delta_s"], -5400.0)
        # Starvation reduced
        self.assertEqual(uw_delta["starvation_reduction_pct"], 100.0)

    def test_empty_raw_stats_safe(self) -> None:
        """Verify to_display_stats handles completely empty simulation data safely."""
        empty_raw = {
            "patients": [],
            "busy_s": {},
            "available_s": {},
            "counts": {},
        }
        display = to_display_stats(empty_raw)
        self.assertEqual(display["wait_times"]["overall"]["avg_wait_s"], 0.0)
        self.assertEqual(display["utilization_pct"], {})
        self.assertEqual(display["starvation"]["starved_level_4_5_count"], 0)


if __name__ == "__main__":
    unittest.main()
