#!/usr/bin/env python3
"""Adversarial tests for PIPE-WU-126 Human-by-Exception operationalization."""
from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".pncc-dev/scripts/evaluate_autonomous_continuation_human_by_exception_operationalization.py"
SPEC = importlib.util.spec_from_file_location("wu126_hbe", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)
POLICY = MOD.load_json(ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-operationalization-policy-wu126.json")
MAIN = "0114ebb9f4e49d24922500803803b5507da7aa7c"


def admission(decision: str, delegated: str, target: str | None, *, blocked: bool = False):
    return {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_DECISION",
        "state": "PLAN_ONLY_ADMISSION_BLOCKED" if blocked else "PLAN_ONLY_ADMISSION_PASS",
        "decision": decision,
        "reasons": [],
        "control_loop_decision": "SYNTHETIC_TEST_ONLY",
        "delegated_authority": delegated,
        "target_action": target,
        "provider_mutation_performed": False,
        "issue_mutation_performed": False,
        "branch_mutation_performed": False,
        "pull_request_mutation_performed": False,
        "writer_lease_mutation_performed": False,
        "workflow_rerun_performed": False,
        "merge_performed": False,
        "runtime_action_performed": False,
    }


def snapshot(value=None):
    return {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_SNAPSHOT",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "provider_truth_fresh": True,
        "current_main_sha": MAIN,
        "admission_current_main_sha": MAIN,
        "input_mode": "EXECUTION_ADMISSION",
        "execution_admission_decision": value,
        "owner_exception": None,
    }


class HumanByExceptionOperationalizationTests(unittest.TestCase):
    def run_eval(self, value, policy=None):
        return MOD.evaluate(copy.deepcopy(value), policy=copy.deepcopy(policy or POLICY), check_anchors=False)

    def assert_continue(self, decision, delegated):
        out = self.run_eval(snapshot(admission(decision, delegated, "EXACT_EXISTING_AUTHORITY_PATH")))
        self.assertEqual(out["outcome"], "CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY")
        self.assertEqual(out["delegated_authority"], delegated)
        self.assertTrue(out["automatic_continuation_permitted"])
        self.assertFalse(out["authority_granted"])
        self.assertFalse(out["higher_autonomy_authorized"])
        self.assertFalse(out["runtime_action_performed"])

    def test_three_existing_authorities_continue_without_new_authority(self):
        self.assert_continue("ADMIT_EXISTING_MATERIALIZATION_AUTHORITY", "EXISTING_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY")
        self.assert_continue("ADMIT_EXISTING_WRITER_LEASE_AUTHORITY", "EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY")
        self.assert_continue("ADMIT_EXISTING_MERGE_CLOSE_AUTHORITY", "EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY")

    def test_wait_is_wait_only_and_no_replay(self):
        out = self.run_eval(snapshot(admission("WAIT_ONLY", "NONE_WAIT_ONLY", "WAIT_NO_MUTATION")))
        self.assertEqual(out["outcome"], "WAIT_ONLY")
        self.assertFalse(out["automatic_continuation_permitted"])
        self.assertFalse(out["automatic_replay_permitted"])

    def test_stop_is_terminal(self):
        out = self.run_eval(snapshot(admission("STOP_ONLY", "NONE_TERMINAL", "STOP_NO_MUTATION")))
        self.assertEqual(out["outcome"], "STOP_ONLY")
        self.assertTrue(out["terminal_stop"])
        self.assertFalse(out["automatic_continuation_permitted"])

    def test_separate_authority_remains_fail_closed(self):
        out = self.run_eval(snapshot(admission("SEPARATE_AUTHORITY_REQUIRED", "NONE_SEPARATE_RECOVERY_AUTHORITY_REQUIRED", "REQUIRE_SEPARATE_RECOVERY_AUTHORITY")))
        self.assertEqual(out["outcome"], "SEPARATE_AUTHORITY_REQUIRED")
        self.assertTrue(out["separate_authority_required"])
        self.assertFalse(out["automatic_continuation_permitted"])

    def test_blocked_remains_fail_closed(self):
        out = self.run_eval(snapshot(admission("BLOCKED", "NONE_FAIL_CLOSED", None, blocked=True)))
        self.assertEqual(out["outcome"], "BLOCKED")
        self.assertFalse(out["automatic_continuation_permitted"])

    def test_owner_exception_surfaces_without_mutation_or_replay(self):
        s = snapshot(None)
        s["input_mode"] = "OWNER_EXCEPTION"
        s["owner_exception"] = {
            "classification": "OWNER_ESCALATION_REQUIRED",
            "reason_classification_present": True,
            "mutation_permitted": False,
            "automatic_replay_permitted": False,
        }
        out = self.run_eval(s)
        self.assertEqual(out["outcome"], "OWNER_ESCALATION_REQUIRED")
        self.assertTrue(out["owner_escalation_required"])
        self.assertFalse(out["automatic_continuation_permitted"])
        self.assertFalse(out["automatic_replay_permitted"])
        self.assertFalse(out["authority_granted"])

    def test_delegated_authority_mismatch_blocks(self):
        a = admission("ADMIT_EXISTING_WRITER_LEASE_AUTHORITY", "EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY", "WRONG")
        out = self.run_eval(snapshot(a))
        self.assertEqual(out["outcome"], "BLOCKED")
        self.assertIn("ADMISSION_DELEGATION_MISMATCH", out["reasons"][0])

    def test_stale_provider_truth_blocks(self):
        s = snapshot(admission("WAIT_ONLY", "NONE_WAIT_ONLY", "WAIT_NO_MUTATION"))
        s["provider_truth_fresh"] = False
        self.assertEqual(self.run_eval(s)["outcome"], "BLOCKED")

    def test_main_binding_mismatch_blocks(self):
        s = snapshot(admission("WAIT_ONLY", "NONE_WAIT_ONLY", "WAIT_NO_MUTATION"))
        s["admission_current_main_sha"] = "1" * 40
        self.assertEqual(self.run_eval(s)["outcome"], "BLOCKED")

    def test_reported_mutation_blocks(self):
        a = admission("ADMIT_EXISTING_WRITER_LEASE_AUTHORITY", "EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY", "PATH")
        a["writer_lease_mutation_performed"] = True
        self.assertEqual(self.run_eval(snapshot(a))["outcome"], "BLOCKED")

    def test_owner_exception_and_admission_are_mutually_exclusive(self):
        s = snapshot(admission("WAIT_ONLY", "NONE_WAIT_ONLY", "WAIT_NO_MUTATION"))
        s["input_mode"] = "OWNER_EXCEPTION"
        s["owner_exception"] = {
            "classification": "OWNER_ESCALATION_REQUIRED",
            "reason_classification_present": True,
            "mutation_permitted": False,
            "automatic_replay_permitted": False,
        }
        self.assertEqual(self.run_eval(s)["outcome"], "BLOCKED")

    def test_policy_cannot_gain_authority(self):
        p = copy.deepcopy(POLICY)
        p["authority_flags"]["higher_autonomy_authority"] = True
        self.assertEqual(self.run_eval(snapshot(admission("WAIT_ONLY", "NONE_WAIT_ONLY", "WAIT_NO_MUTATION")), policy=p)["outcome"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
