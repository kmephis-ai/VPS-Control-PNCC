#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".pncc-dev/scripts/evaluate_wave6_wu144_provider_delivery_qualification_wu145.py"
spec = importlib.util.spec_from_file_location("wu145", MODULE_PATH)
assert spec is not None and spec.loader is not None
wu145 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wu145)


def payload(observed_at: str, *, fetched_at: str | None = None, observer_runs=None, wu137_runs=None):
    return {
        "observed_at": observed_at,
        "provider_fetched_at": fetched_at or observed_at,
        "observer_workflow_runs": [] if observer_runs is None else observer_runs,
        "wu137_workflow_runs": [] if wu137_runs is None else wu137_runs,
    }


def run(run_id: int, created_at: str, *, status="completed", conclusion="success", event="schedule"):
    return {
        "id": run_id,
        "event": event,
        "status": status,
        "conclusion": conclusion,
        "created_at": created_at,
        "head_sha": "9c8a5f4d18ce0557a121d3d0bcc66f8cc7e19367",
    }


class WU145QualificationTests(unittest.TestCase):
    def test_before_first_nominal_is_waiting_not_miss(self):
        result = wu145.evaluate(payload("2026-09-01T16:00:00Z"))
        self.assertEqual(result["state"], "WAITING_MATURE_OBSERVATION_WINDOW")
        self.assertEqual(result["matured_observer_opportunity_count"], 0)
        self.assertEqual(result["immature_observer_opportunity"]["nominal_at"], "2026-09-01T16:07:00Z")
        self.assertFalse(result["mutation_authority"])

    def test_after_nominal_before_deadline_is_waiting_not_miss(self):
        result = wu145.evaluate(payload("2026-09-01T16:30:00Z"))
        self.assertEqual(result["state"], "WAITING_MATURE_OBSERVATION_WINDOW")
        self.assertEqual(result["matured_observer_opportunity_count"], 0)
        self.assertEqual(result["immature_observer_opportunity"]["deadline_at"], "2026-09-01T16:52:00Z")

    def test_missing_run_after_deadline_is_miss(self):
        result = wu145.evaluate(payload("2026-09-01T16:53:00Z"))
        self.assertEqual(result["state"], "OBSERVER_DELIVERY_MISS_OBSERVED")
        self.assertEqual(result["matured_observer_opportunity_count"], 1)
        self.assertEqual(result["observer_consecutive_misses"], 1)

    def test_successful_observer_delivery_is_healthy(self):
        result = wu145.evaluate(payload(
            "2026-09-01T16:53:00Z",
            observer_runs=[run(101, "2026-09-01T16:20:00Z")],
        ))
        self.assertEqual(result["state"], "OBSERVER_DELIVERY_HEALTHY")
        self.assertEqual(result["matured_observer_opportunities"][0]["healthy_run_ids"], [101])
        self.assertEqual(result["recommended_action"], "OBSERVE_ONLY_NO_CHANGE")

    def test_duplicate_healthy_observer_runs_are_visible_not_silent(self):
        result = wu145.evaluate(payload(
            "2026-09-01T16:53:00Z",
            observer_runs=[run(101, "2026-09-01T16:20:00Z"), run(102, "2026-09-01T16:21:00Z")],
        ))
        self.assertEqual(result["state"], "OBSERVER_DELIVERY_HEALTHY")
        self.assertEqual(result["matured_observer_opportunities"][0]["duplicate_healthy_run_count"], 1)

    def test_unhealthy_observer_execution_requires_owner_review(self):
        result = wu145.evaluate(payload(
            "2026-09-01T16:53:00Z",
            observer_runs=[run(201, "2026-09-01T16:20:00Z", conclusion="failure")],
        ))
        self.assertEqual(result["state"], "OBSERVER_EXECUTION_UNHEALTHY_OBSERVED")
        self.assertEqual(result["observer_unhealthy_run_ids"], [201])
        self.assertEqual(result["recommended_action"], "OWNER_REVIEW_NO_ACTIVATION")

    def test_nonterminal_observer_execution_is_not_counted_healthy(self):
        result = wu145.evaluate(payload(
            "2026-09-01T16:53:00Z",
            observer_runs=[run(301, "2026-09-01T16:20:00Z", status="in_progress", conclusion=None)],
        ))
        self.assertEqual(result["state"], "OBSERVER_EXECUTION_NONTERMINAL_OBSERVED")
        self.assertEqual(result["observer_nonterminal_run_ids"], [301])

    def test_out_of_window_run_is_ignored_and_does_not_mask_miss(self):
        result = wu145.evaluate(payload(
            "2026-09-01T16:53:00Z",
            observer_runs=[run(401, "2026-09-01T15:30:00Z")],
        ))
        self.assertEqual(result["state"], "OBSERVER_DELIVERY_MISS_OBSERVED")
        self.assertEqual(result["ignored_observer_run_ids"], [401])

    def test_duplicate_provider_run_id_fails_closed(self):
        with self.assertRaisesRegex(wu145.QualificationError, "duplicate run id"):
            wu145.evaluate(payload(
                "2026-09-01T16:53:00Z",
                observer_runs=[run(501, "2026-09-01T16:20:00Z"), run(501, "2026-09-01T16:21:00Z")],
            ))

    def test_stale_provider_snapshot_fails_closed(self):
        with self.assertRaisesRegex(wu145.QualificationError, "stale provider snapshot"):
            wu145.evaluate(payload(
                "2026-09-01T16:53:00Z",
                fetched_at="2026-09-01T16:40:00Z",
            ))

    def test_malformed_event_fails_closed(self):
        with self.assertRaisesRegex(wu145.QualificationError, "expected schedule"):
            wu145.evaluate(payload(
                "2026-09-01T16:53:00Z",
                observer_runs=[run(601, "2026-09-01T16:20:00Z", event="workflow_dispatch")],
            ))

    def test_wu137_observation_is_composed_from_immutable_wu144_evaluator(self):
        wu137_run = {
            "id": 701,
            "event": "schedule",
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-09-01T15:31:12Z",
            "head_sha": "9e11e2b9288c199754ee39133560b35d82471367",
        }
        result = wu145.evaluate(payload(
            "2026-09-01T16:53:00Z",
            observer_runs=[run(702, "2026-09-01T16:20:00Z")],
            wu137_runs=[wu137_run],
        ))
        nested = result["wu137_delivery_observation"]
        self.assertEqual(nested["role"], "WAVE6_WU137_GITHUB_NATIVE_REDUNDANT_OBSERVER_RESULT")
        self.assertFalse(nested["mutation_authority"])
        self.assertFalse(result["scheduler_mutation_authority"])
        self.assertFalse(result["reserve_1080_lifecycle_mutation_authority"])
        self.assertFalse(result["primary_1081_lifecycle_mutation_authority"])


if __name__ == "__main__":
    unittest.main()
