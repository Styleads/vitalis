"""Integration tests for MedFlow WebSocket broadcast endpoint.

Conforms to AGENT.md §18 (Task 8), §20.
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


class TestWebSocket(unittest.TestCase):
    """Test suite verifying WebSocket connects and receives initial state."""

    def test_websocket_connect_receives_initial_snapshot(self) -> None:
        """Client receives full snapshot state envelope immediately upon connecting."""
        client = TestClient(app)
        with client.websocket_connect("/ws/simulation") as websocket:
            data = websocket.receive_json()
            self.assertEqual(data.get("type"), "state")
            self.assertIn("data", data)
            snapshot = data["data"]
            self.assertIn("clock", snapshot)
            self.assertIn("queue", snapshot)
            self.assertIn("resources", snapshot)


if __name__ == "__main__":
    unittest.main()
