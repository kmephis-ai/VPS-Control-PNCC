#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import copy
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pncc_claim",
    ROOT / ".pncc-dev" / "scripts" / "evaluate_writer_lease_claim_admission.py",
)
claim = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(claim)

HEAD = "a" * 40
OTHER = "b" * 40
NOW = "2030-01-01T00:30:00Z"
HOLDER = "agent-session-1"


def orchestration(disposition="EXECUTABLE", *, base=HEAD, runtime=False):
    selected = {
        "issue": 226,
        "work_unit_id": "PIPE-WU-094",
        "state": "ACTIVE",
        "conflict_domain": "wave5-writer-lease-claim-admission",
        "base_sha": base,
        "branch": None,
        "runtime_required": runtime,
        "materialization_phase": "INTAKE",
        "classification": "EXECUTABLE_READ_ONLY_SELECTION",
        "reason": None,
    }
    return {
        "schema_version": 2,
        "role": "READ_ONLY_PROVIDER_WORK_UNIT_SELECTION",
        "state": "READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "default_branch_head_sha": HEAD,
        "observed_at": NOW,
        "decision": "SELECTED" if disposition == "EXECUTABLE" else "NO_EXECUTABLE_WORK_UNIT",
        "orchestration_disposition": disposition,
        "selected": selected if disposition == "EXECUTABLE" else None,
    }


def lease(*, lease_id="70c397e8-8c1d-4939-8dc8-59aec23bdf60", wid="PIPE-WU-090", domain="other-domain", holder="other-writer", state="ACTIVE", heartbeat="2030-01-01T00:20:00Z", expires="2030-01-01T01:00:00Z"):
    return {
        "schema_version": 1,
        "role": "WRITER_LEASE",
        "lease_id": lease_id,
        "work_unit_id": wid,
        "conflict_domain": domain,
        "holder": holder,
        "base_sha": HEAD,
        "branch": "agent/example",
        "state": state,
        "generation": 1,
        "acquired_at": "2030-01-01T00:00:00Z",
        "heartbeat_at": heartbeat,
        "expires_at": expires,
    }


class ClaimAdmissionTests(unittest.TestCase):
    def evaluate(self, orchestration_value=None, leases=None, holder=HOLDER):
        return claim.evaluate_claim_admission(
            orchestration_value if orchestration_value is not None else orchestration(),
            [] if leases is None else leases,
            holder=holder,
            now_iso=NOW,
        )

    def test_empty_inventory_is_eligible_but_does_not_acquire(self):
        result = self.evaluate()
        self.assertEqual(result["decision"], "CLAIM_ELIGIBLE")
        self.assertEqual(result["state"], "READ_ONLY_CLAIM_ADMISSION_PASS")
        self.assertFalse(result["provider_mutation_performed"])
        self.assertFalse(result["writer_lease_acquired"])
        self.assertFalse(result["writer_lease_updated"])
        self.assertFalse(result["writer_lease_stolen"])
        self.assertEqual(result["next_boundary"], "SEPARATE_EXPLICIT_WRITER_LEASE_ACQUISITION_AUTHORITY_DESIGN")

    def test_non_executable_dispositions_block(self):
        for disposition in ("WAITING_RUNTIME", "BLOCKED", "NO_WORK"):
            with self.subTest(disposition=disposition):
                result = self.evaluate(orchestration(disposition))
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertIn("ORCHESTRATION_NOT_EXECUTABLE", result["reasons"])

    def test_stale_selected_base_blocks(self):
        result = self.evaluate(orchestration(base=OTHER))
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("SELECTION_BASE_STALE", result["reasons"])

    def test_runtime_required_selected_work_blocks(self):
        result = self.evaluate(orchestration(runtime=True))
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("SELECTED_RUNTIME_REQUIRED", result["reasons"])

    def test_empty_holder_blocks(self):
        result = self.evaluate(holder="   ")
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("HOLDER_REQUIRED", result["reasons"])

    def test_unexpired_active_same_domain_blocks_even_foreign_holder(self):
        result = self.evaluate(leases=[lease(domain="wave5-writer-lease-claim-admission")])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("ACTIVE_CONFLICT_DOMAIN_LEASE_PRESENT", result["reasons"])

    def test_unexpired_active_same_work_unit_blocks_even_other_domain(self):
        result = self.evaluate(leases=[lease(wid="PIPE-WU-094")])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("ACTIVE_WORK_UNIT_LEASE_PRESENT", result["reasons"])

    def test_unrelated_active_lease_does_not_block(self):
        result = self.evaluate(leases=[lease()])
        self.assertEqual(result["decision"], "CLAIM_ELIGIBLE")

    def test_released_and_expired_records_are_historical_only(self):
        released = lease(state="RELEASED")
        expired = lease(lease_id="b7d08baf-5a9d-41f8-9b42-b2e0611f38f5", state="EXPIRED")
        result = self.evaluate(leases=[released, expired])
        self.assertEqual(result["decision"], "CLAIM_ELIGIBLE")
        self.assertEqual(result["historical_lease_count"], 2)
        self.assertFalse(result["writer_lease_acquired"])

    def test_active_record_expired_by_time_is_historical_not_reused(self):
        old = lease(domain="wave5-writer-lease-claim-admission", expires="2030-01-01T00:25:00Z")
        result = self.evaluate(leases=[old])
        self.assertEqual(result["decision"], "CLAIM_ELIGIBLE")
        self.assertEqual(result["historical_lease_count"], 1)

    def test_future_heartbeat_blocks_fail_closed(self):
        result = self.evaluate(leases=[lease(heartbeat="2030-01-01T00:40:00Z")])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("ACTIVE_LEASE_FUTURE_HEARTBEAT", result["reasons"])

    def test_malformed_lease_inventory_blocks(self):
        bad = lease()
        bad["lease_id"] = "not-a-uuid"
        result = self.evaluate(leases=[bad])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertTrue(result["reasons"][0].startswith("LEASE_INVENTORY_INVALID:"))

    def test_duplicate_lease_id_blocks_ambiguous_inventory(self):
        first = lease(state="RELEASED")
        second = copy.deepcopy(first)
        second["state"] = "EXPIRED"
        result = self.evaluate(leases=[first, second])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("LEASE_INVENTORY_DUPLICATE_ID", result["reasons"])

    def test_policy_is_default_deny_for_all_mutation_authorities(self):
        policy = json.loads((ROOT / ".pncc-dev/contracts/writer-lease-claim-admission-policy.json").read_text(encoding="utf-8"))
        false_fields = [key for key in policy if key.endswith("_authority")]
        self.assertGreaterEqual(len(false_fields), 10)
        self.assertTrue(all(policy[key] is False for key in false_fields))
        claim._validate_policy(policy)

    def test_existing_writer_lease_example_remains_valid(self):
        example = json.loads((ROOT / ".pncc-dev/examples/writer-lease.valid.json").read_text(encoding="utf-8"))
        claim.state.validate_writer_lease(example)


if __name__ == "__main__":
    unittest.main()
