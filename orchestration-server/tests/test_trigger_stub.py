from __future__ import annotations

import unittest
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

import app.main as main_mod


class TriggerStubTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_rules = main_mod.trigger_rules
        self._orig_events = main_mod.trigger_events
        main_mod.trigger_rules = {}
        main_mod.trigger_events = []
        self.client = TestClient(main_mod.app)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.trigger_rules = self._orig_rules
        main_mod.trigger_events = self._orig_events

    def test_register_fire_list_trigger(self) -> None:
        register = self.client.post(
            "/api/v1/triggers/register",
            json={
                "rule_id": "rule-1",
                "name": "Cue 1",
                "source": "osc",
                "cue_id": "cue-1",
                "payload": {"foo": "bar"},
            },
        )
        self.assertEqual(register.status_code, 200, register.text)
        rule = register.json()["rule"]
        self.assertEqual(rule["rule_id"], "rule-1")

        fire = self.client.post(
            "/api/v1/triggers/fire",
            json={"rule_id": "rule-1", "payload": {"level": 2}},
        )
        self.assertEqual(fire.status_code, 200, fire.text)
        event = fire.json()["event"]
        self.assertEqual(event["rule_id"], "rule-1")
        self.assertEqual(event["cue_id"], "cue-1")
        self.assertEqual(event["payload"]["foo"], "bar")
        self.assertEqual(event["payload"]["level"], 2)

        listing = self.client.get("/api/v1/triggers/events")
        self.assertEqual(listing.status_code, 200, listing.text)
        events = listing.json()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["rule_id"], "rule-1")


if __name__ == "__main__":
    unittest.main()
