#!/usr/bin/env python3

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/evaluate_wave6_scheduler_remediation_readiness_wu147.py"
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-scheduler-remediation-owner-decision-readiness-wu147.json"

spec = importlib.util.spec_from_file_location("wu147_eval", SCRIPT)
wu147 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(wu147)


class Wave6SchedulerRemediationReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def evaluate(self, data, anchors=False):
        return wu147.evaluate_contract(data, ROOT if anchors else None)

    def assert_fail_closed(self, data):
        result = self.evaluate(data)
        self.assertEqual("FAIL_CLOSED", result["verdict"])
        self.assertFalse(result["activation_authorized"])
        self.assertTrue(result["errors"])

    def test_canonical_packet_is_ready_but_never_authorizes_activation(self):
        result = self.evaluate(copy.deepcopy(self.canonical), anchors=True)
        self.assertEqual("READY_FOR_OWNER_DECISION", result["verdict"])
        self.assertFalse(result["activation_authorized"])
        self.assertEqual([], result["errors"])

    def test_authority_escalation_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["authority"]["repository_dispatch_authority"] = True
        self.assert_fail_closed(data)

    def test_premature_activation_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["decision_state"]["activation_performed"] = True
        self.assert_fail_closed(data)

    def test_candidate_selection_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["decision_state"]["selected_candidate"] = "BOUNDED_DISPATCH_FALLBACK_CLASS"
        self.assert_fail_closed(data)

    def test_decision_matrix_selected_flag_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["decision_matrix"][2]["selected"] = True
        self.assert_fail_closed(data)

    def test_provider_root_cause_overclaim_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["predecessor_evidence"]["provider_root_cause_proven"] = True
        self.assert_fail_closed(data)

    def test_global_github_outage_overclaim_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["predecessor_evidence"]["global_github_outage_proven"] = True
        self.assert_fail_closed(data)

    def test_stale_evidence_activation_bypass_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["freshness_boundary"]["stale_predecessor_evidence_may_authorize_activation"] = True
        self.assert_fail_closed(data)

    def test_fresh_readback_abort_gate_removal_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["freshness_boundary"]["activation_must_abort_if_fresh_readback_unavailable"] = False
        self.assert_fail_closed(data)

    def test_missing_abort_condition_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["mandatory_abort_conditions"].remove("ROLLBACK_PATH_UNPROVEN")
        self.assert_fail_closed(data)

    def test_missing_rollback_requirement_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["mandatory_rollback_requirements"].remove("VERIFY_POST_ROLLBACK_PROVIDER_AND_REPOSITORY_STATE")
        self.assert_fail_closed(data)

    def test_missing_activation_prerequisite_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["activation_prerequisites"].remove("EXPLICIT_OWNER_AUTHORIZATION_NAMING_EXACT_ACTIVATION_CLASS")
        self.assert_fail_closed(data)

    def test_native_schedule_redundancy_overclaim_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        for item in data["decision_matrix"]:
            if item["id"] == "GITHUB_NATIVE_REDUNDANT_SCHEDULE_OBSERVATION":
                item["sufficient_as_reliability_remediation"] = True
        self.assert_fail_closed(data)

    def test_dispatch_pre_authorization_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        for item in data["decision_matrix"]:
            if item["id"] == "BOUNDED_DISPATCH_FALLBACK_CLASS":
                item["repository_dispatch_authorized"] = True
        self.assert_fail_closed(data)

    def test_reusable_authority_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["decision_state"]["reusable_authority_allowed"] = True
        self.assert_fail_closed(data)

    def test_base_drift_fails_closed(self):
        data = copy.deepcopy(self.canonical)
        data["authorized_base_sha"] = "0" * 40
        self.assert_fail_closed(data)


if __name__ == "__main__":
    unittest.main()
