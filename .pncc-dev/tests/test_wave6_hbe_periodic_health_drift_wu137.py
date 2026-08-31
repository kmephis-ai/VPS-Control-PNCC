#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "wu137_eval",
    ROOT / ".pncc-dev/scripts/evaluate_wave6_hbe_periodic_health_drift_wu137.py",
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)

ACTIVATION = json.loads(
    (ROOT / ".pncc-dev/contracts/wave6-hbe-periodic-health-drift-activation-wu137.json").read_text()
)
NOW = datetime(2026, 8, 31, 17, 1, 0, tzinfo=timezone.utc)

def healthy_snapshot():
    return {
        "observed_at": "2026-08-31T17:00:00Z",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "main_sha": "a" * 40,
        "checkout_sha": "a" * 40,
        "provider_state_sha": "b" * 40,
        "registry_generation": 51,
        "frontier_state": "NONE",
        "proposal_blob_sha": "7605105488aafad7400c26c13a5c8f5515d40a02",
        "authorization_issue_state": "open",
        "authorization_tokens_present": True,
        "ruleset_id": 21585301,
        "ruleset_enforcement": "active",
        "ruleset_bypass_actor_count": 0,
        "ruleset_current_user_can_bypass": "never",
        "ruleset_rule_types": ["deletion", "non_fast_forward", "pull_request", "required_status_checks"],
        "strict_required_status_checks_policy": True,
        "required_check_contexts": ["repo-integrity", "powershell-static", "truth-contract"],
        "required_check_conclusions": {
            "repo-integrity": "success",
            "powershell-static": "success",
            "truth-contract": "success",
        },
        "owner_boundary_requested": False,
    }

class TestWU137PeriodicHealthDrift(unittest.TestCase):
    def evaluate(self, snapshot):
        return mod.evaluate(snapshot, now=NOW, activation=ACTIVATION)

    def test_healthy(self):
        r = self.evaluate(healthy_snapshot())
        self.assertEqual(r["outcome"], "HEALTHY")
        self.assertFalse(r["provider_mutation_performed"])
        self.assertFalse(r["runtime_mutation_performed"])
        self.assertFalse(r["authority_granted"])

    def test_stale_snapshot_blocks(self):
        s = healthy_snapshot()
        s["observed_at"] = "2026-08-31T16:54:59Z"
        self.assertEqual(self.evaluate(s)["outcome"], "BLOCKED")

    def test_future_snapshot_blocks(self):
        s = healthy_snapshot()
        s["observed_at"] = "2026-08-31T17:01:31Z"
        self.assertEqual(self.evaluate(s)["outcome"], "BLOCKED")

    def test_main_identity_drift(self):
        s = healthy_snapshot()
        s["checkout_sha"] = "c" * 40
        r = self.evaluate(s)
        self.assertEqual(r["outcome"], "DRIFT_DETECTED")
        self.assertIn("MAIN_IDENTITY_DRIFT", r["reasons"])

    def test_required_check_failure_is_drift(self):
        s = healthy_snapshot()
        s["required_check_conclusions"]["truth-contract"] = "failure"
        r = self.evaluate(s)
        self.assertEqual(r["outcome"], "DRIFT_DETECTED")
        self.assertIn("REQUIRED_CHECK_NOT_SUCCESS:truth-contract", r["reasons"])

    def test_ruleset_bypass_requires_owner_exception(self):
        s = healthy_snapshot()
        s["ruleset_bypass_actor_count"] = 1
        self.assertEqual(self.evaluate(s)["outcome"], "OWNER_EXCEPTION_REQUIRED")

    def test_ruleset_bypass_capability_requires_owner_exception(self):
        s = healthy_snapshot()
        s["ruleset_current_user_can_bypass"] = "always"
        self.assertEqual(self.evaluate(s)["outcome"], "OWNER_EXCEPTION_REQUIRED")

    def test_missing_authorization_binding_requires_owner_exception(self):
        s = healthy_snapshot()
        s["authorization_tokens_present"] = False
        self.assertEqual(self.evaluate(s)["outcome"], "OWNER_EXCEPTION_REQUIRED")

    def test_frontier_drift(self):
        s = healthy_snapshot()
        s["frontier_state"] = "ACTIVE"
        self.assertEqual(self.evaluate(s)["outcome"], "DRIFT_DETECTED")

    def test_provider_generation_regression(self):
        s = healthy_snapshot()
        s["registry_generation"] = 50
        self.assertEqual(self.evaluate(s)["outcome"], "DRIFT_DETECTED")

    def test_unknown_snapshot_field_blocks(self):
        s = healthy_snapshot()
        s["unexpected"] = True
        self.assertEqual(self.evaluate(s)["outcome"], "BLOCKED")

    def test_activation_cannot_grant_mutation_authority(self):
        a = deepcopy(ACTIVATION)
        a["authority"]["provider_mutation_authority"] = True
        r = mod.evaluate(healthy_snapshot(), now=NOW, activation=a)
        self.assertEqual(r["outcome"], "BLOCKED")
        self.assertIn("AUTHORITY_PRESENT:provider_mutation_authority", r["reasons"])

if __name__ == "__main__":
    unittest.main()
