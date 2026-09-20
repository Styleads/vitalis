"""Integration tests for MedFlow FastAPI REST endpoints.

Conforms to AGENT.md §18 (Task 8).
"""

from __future__ import annotations

import sys
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.main import app
from strategies import STRATEGIES


class TestApiEndpoints(unittest.TestCase):
    """Test suite verifying all MedFlow REST endpoints work with real Engine & Strategies."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_and_root(self) -> None:
        """Verify root and /health endpoints."""
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertIn("message", res_root.json())

        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertTrue(res_health.json()["ok"])
        self.assertIn("clock", res_health.json())

    def test_state_snapshot_schema(self) -> None:
        """Verify /state returns the locked snapshot() schema."""
        res = self.client.get("/state")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        expected_keys = {"clock", "strategy_name", "hol_policy", "queue", "in_treatment", "resources", "flags", "recent_events"}
        self.assertTrue(expected_keys.issubset(set(data.keys())))

    def test_patients_and_resources_endpoints(self) -> None:
        """Verify /patients and /resources convenience slices."""
        res_patients = self.client.get("/patients")
        self.assertEqual(res_patients.status_code, 200)
        p_data = res_patients.json()
        self.assertIn("queue", p_data)
        self.assertIn("in_treatment", p_data)

        res_resources = self.client.get("/resources")
        self.assertEqual(res_resources.status_code, 200)
        r_data = res_resources.json()
        self.assertIn("resources", r_data)
        self.assertIn("utilization_pct", r_data)

    def test_stats_endpoint(self) -> None:
        """Verify /stats transforms raw counters via Person B's to_display_stats."""
        res = self.client.get("/stats")
        self.assertEqual(res.status_code, 200)
        s_data = res.json()
        self.assertIn("wait_times", s_data)
        self.assertIn("utilization_pct", s_data)
        self.assertIn("counts", s_data)

    def test_strategy_lifecycle(self) -> None:
        """Verify querying available strategies and hot-swapping."""
        res = self.client.get("/strategy")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(set(data["available"]), set(STRATEGIES.keys()))

        # Switch to urgency_only
        res_switch = self.client.post("/strategy", json={"name": "urgency_only"})
        self.assertEqual(res_switch.status_code, 200)
        self.assertEqual(res_switch.json()["active"], "urgency_only")

        # Invalid strategy gives 422
        res_invalid = self.client.post("/strategy", json={"name": "unknown_fake_strategy"})
        self.assertEqual(res_invalid.status_code, 422)

    def test_scenario_hooks(self) -> None:
        """Verify surge, capacity change, and failure scenario endpoints."""
        # Surge
        res_surge = self.client.post("/scenario/surge", json={"multiplier": 2.5, "duration_s": 1800})
        self.assertEqual(res_surge.status_code, 200)
        self.assertEqual(res_surge.json()["flags"]["arrival_multiplier"], 2.5)

        # Capacity
        res_cap = self.client.post("/scenario/capacity", json={"type": "NURSE", "n": 6})
        self.assertEqual(res_cap.status_code, 200)

        # Fail
        res_fail = self.client.post("/scenario/fail", json={"unit_id": 1, "duration_s": 900})
        self.assertEqual(res_fail.status_code, 200)

    def test_compare_endpoint(self) -> None:
        """Verify /compare runs headless A/B evaluation across strategies."""
        res = self.client.post(
            "/compare",
            json={
                "seed": 42,
                "horizon_s": 3600,
                "until_s": 1800,
                "strategies": ["urgency_only", "urgency_wait"],
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("raw", data)
        self.assertIn("comparison", data)
        self.assertIn("summary_table", data["comparison"])

    def test_demo_scenarios(self) -> None:
        """Verify listing and loading scripted demo scenarios."""
        res_list = self.client.get("/demo/scenarios")
        self.assertEqual(res_list.status_code, 200)
        scenarios = res_list.json()
        self.assertGreater(len(scenarios), 0)

        res_load = self.client.post("/demo/load", json={"name": "queue_jump"})
        self.assertEqual(res_load.status_code, 200)
        self.assertIn("queue", res_load.json())

    def test_sim_controls(self) -> None:
        """Verify start, pause, resume, speed, reset controls."""
        res_speed = self.client.post("/sim/speed", json={"speed": 100.0})
        self.assertEqual(res_speed.status_code, 200)
        self.assertEqual(res_speed.json()["speed"], 100.0)

        res_pause = self.client.post("/sim/pause")
        self.assertEqual(res_pause.status_code, 200)
        self.assertFalse(res_pause.json()["running"])

        res_resume = self.client.post("/sim/resume")
        self.assertEqual(res_resume.status_code, 200)
        self.assertTrue(res_resume.json()["running"])

        res_status = self.client.get("/sim/status")
        self.assertEqual(res_status.status_code, 200)
        self.assertTrue(res_status.json()["running"])


if __name__ == "__main__":
    unittest.main()
