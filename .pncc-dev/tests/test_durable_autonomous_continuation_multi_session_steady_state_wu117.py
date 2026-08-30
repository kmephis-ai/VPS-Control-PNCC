import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".pncc-dev/scripts/evaluate_durable_autonomous_continuation_multi_session_steady_state.py"
POLICY_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-steady-state-policy.json"
RECORD_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-handoff-record-wu117.json"
spec = importlib.util.spec_from_file_location("wu117_multi_session", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class WU117MultiSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY_PATH.read_text())
        cls.record = json.loads(RECORD_PATH.read_text())

    def session_start(self, prior=None):
        return {
            "schema_version": 1,
            "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_SNAPSHOT",
            "phase": "SESSION_START",
            "repository": "kmephis-ai/VPS-Control-PNCC",
            "default_branch": "main",
            "session_sequence": 2 if prior is not None else 1,
            "session_id": "PNCC-SESSION-WU117-MULTI-SESSION-A2" if prior is not None else "PNCC-SESSION-WU117-BOOTSTRAP-A1",
            "prior_handoff": prior,
            "provider_truth_fresh": True,
            "contradictory_provider_truth": False,
            "current_main_sha": "daa77dc4a263ba9d8f9a185d134bdc4ceae5bcad",
            "selected_work_unit": copy.deepcopy(self.record["selected_work_unit"]),
            "provider_state": copy.deepcopy(self.record["provider_state"]),
            "branch_pr_ci_truth_fresh": True,
            "classified_failure_detected": False,
        }

    def iteration(self):
        return {
            "schema_version": 1,
            "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_SNAPSHOT",
            "phase": "ITERATION",
            "repository": "kmephis-ai/VPS-Control-PNCC",
            "default_branch": "main",
            "session_sequence": 2,
            "iteration_sequence": 1,
            "provider_truth_fresh": True,
            "control_loop_fresh_for_iteration": True,
            "execution_admission_fresh_for_iteration": True,
            "control_loop_reused_from_prior_session": False,
            "execution_admission_reused_from_prior_session": False,
            "registry_cas_reused_from_prior_session": False,
            "previous_iteration_provider_readback_completed": False,
            "delegated_transaction": {
                "delegated_transaction_count": 0,
                "provider_mutation_performed": False,
                "fresh_provider_readback_completed": False,
            },
            "classified_failure_detected": False,
        }

    def refreshed_record(self):
        new = copy.deepcopy(self.record)
        new["session_sequence"] = 2
        new["session_id"] = "PNCC-SESSION-WU118-MULTI-SESSION-A2"
        new["checkpoint_id"] = "PNCC-CONTINUATION-CHECKPOINT-WU118-CLEAN-A1"
        new["checkpoint_blob_sha"] = "1" * 40
        new["previous_checkpoint_id"] = self.record["checkpoint_id"]
        new["retained_historical_checkpoint_ids"] = [
            "PNCC-CONTINUATION-CHECKPOINT-WU115-CLEAN-A1",
            self.record["checkpoint_id"],
        ]
        new["recorded_main_sha"] = "2" * 40
        new["selected_work_unit"] = {
            "work_unit_id": "PIPE-WU-118",
            "issue_number": 283,
            "base_sha": "2" * 40,
            "runtime_required": False,
            "provider_open": True,
        }
        new["provider_state"] = {
            "state_branch_head_sha": "3" * 40,
            "registry_blob_sha": "4" * 40,
            "registry_generation": 26,
        }
        new["execution_state"] = {
            "lease_state": "ACTIVE",
            "lease_id": "next-lease",
            "branch_name": "agent/PIPE-WU-118-example",
            "branch_head_sha": "2" * 40,
            "pull_request_state": "NONE",
            "pull_request_number": None,
            "ci_state": "NONE",
            "ci_head_sha": None,
        }
        new["last_completed_iteration"] = 2
        return new

    def refresh_snapshot(self):
        new = self.refreshed_record()
        return {
            "schema_version": 1,
            "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_SNAPSHOT",
            "phase": "HANDOFF_REFRESH",
            "repository": "kmephis-ai/VPS-Control-PNCC",
            "default_branch": "main",
            "provider_truth_fresh": True,
            "fresh_provider_readback_completed": True,
            "classified_failure_detected": False,
            "current_main_sha": new["recorded_main_sha"],
            "selected_work_unit": copy.deepcopy(new["selected_work_unit"]),
            "provider_state": copy.deepcopy(new["provider_state"]),
            "execution_state": copy.deepcopy(new["execution_state"]),
            "prior_handoff": copy.deepcopy(self.record),
            "new_handoff": new,
        }

    def assertBlocked(self, snapshot):
        with self.assertRaises(module.MultiSessionError):
            module.evaluate(snapshot, policy=self.policy, check_anchors=False)

    def test_policy_and_canonical_record_are_valid_with_anchors(self):
        module.validate_policy(self.policy)
        module.validate_anchors(self.policy)
        module.validate_handoff_record(copy.deepcopy(self.record), self.policy)

    def test_bootstrap_session_requires_fresh_recompute(self):
        result = module.evaluate(self.session_start(), policy=self.policy, check_anchors=True)
        self.assertEqual(result["decision"], "START_FRESH_RECOMPUTE")
        self.assertFalse(result["prior_checkpoint_authority_used"])

    def test_clean_prior_session_discards_persisted_decisions(self):
        result = module.evaluate(self.session_start(copy.deepcopy(self.record)), policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "START_FRESH_RECOMPUTE")
        self.assertEqual(set(result["discarded_prior_persisted_decisions"]), {"control_loop_decision", "execution_admission_decision"})
        self.assertTrue(result["fresh_wu108_recomputation_required_before_mutation"])
        self.assertTrue(result["fresh_wu109_recomputation_required_before_mutation"])

    def test_interrupted_prior_session_requires_reconciliation(self):
        prior = copy.deepcopy(self.record)
        prior["handoff_class"] = "TRANSACTION_OUTCOME_UNKNOWN"
        result = module.evaluate(self.session_start(prior), policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "RECONCILE_INTERRUPTED_SESSION")
        self.assertTrue(result["provider_reconciliation_required"])
        self.assertFalse(result["prior_checkpoint_authority_used"])

    def test_readback_pending_prior_session_waits(self):
        prior = copy.deepcopy(self.record)
        prior["handoff_class"] = "PROVIDER_READBACK_PENDING"
        prior["provider_readback_completed"] = False
        result = module.evaluate(self.session_start(prior), policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "WAIT_FOR_PROVIDER_READBACK")
        self.assertTrue(result["provider_readback_required"])

    def test_nonfresh_provider_truth_blocks_session_start(self):
        snap = self.session_start(copy.deepcopy(self.record))
        snap["provider_truth_fresh"] = False
        self.assertBlocked(snap)

    def test_session_sequence_reuse_blocks(self):
        snap = self.session_start(copy.deepcopy(self.record))
        snap["session_sequence"] = 1
        self.assertBlocked(snap)

    def test_session_id_reuse_blocks(self):
        prior = copy.deepcopy(self.record)
        snap = self.session_start(prior)
        snap["session_id"] = prior["session_id"]
        self.assertBlocked(snap)

    def test_classified_failure_routes_separate_authority(self):
        snap = self.session_start(copy.deepcopy(self.record))
        snap["classified_failure_detected"] = True
        result = module.evaluate(snap, policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "SEPARATE_AUTHORITY_REQUIRED")

    def test_fresh_iteration_is_admitted_plan_only(self):
        result = module.evaluate(self.iteration(), policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "ADMIT_FRESH_ITERATION")
        self.assertFalse(result["provider_mutation_performed"])

    def test_performed_transaction_requires_readback(self):
        snap = self.iteration()
        snap["delegated_transaction"] = {
            "delegated_transaction_count": 1,
            "provider_mutation_performed": True,
            "fresh_provider_readback_completed": False,
        }
        result = module.evaluate(snap, policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "REQUIRE_PROVIDER_READBACK")
        self.assertTrue(result["provider_readback_required"])

    def test_transaction_with_readback_allows_clean_handoff(self):
        snap = self.iteration()
        snap["delegated_transaction"] = {
            "delegated_transaction_count": 1,
            "provider_mutation_performed": True,
            "fresh_provider_readback_completed": True,
        }
        result = module.evaluate(snap, policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "CLEAN_HANDOFF_READY")
        self.assertTrue(result["checkpoint_refresh_allowed"])

    def test_batched_transaction_blocks(self):
        snap = self.iteration()
        snap["delegated_transaction"] = {
            "delegated_transaction_count": 2,
            "provider_mutation_performed": True,
            "fresh_provider_readback_completed": True,
        }
        self.assertBlocked(snap)

    def test_stale_prior_session_control_loop_blocks(self):
        snap = self.iteration()
        snap["control_loop_reused_from_prior_session"] = True
        self.assertBlocked(snap)

    def test_second_iteration_without_previous_readback_blocks(self):
        snap = self.iteration()
        snap["iteration_sequence"] = 2
        snap["previous_iteration_provider_readback_completed"] = False
        self.assertBlocked(snap)

    def test_checkpoint_refresh_advances_identity_and_retains_prior(self):
        result = module.evaluate(self.refresh_snapshot(), policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "CLEAN_HANDOFF_READY")
        self.assertTrue(result["checkpoint_refresh_allowed"])
        self.assertFalse(result["prior_checkpoint_authority_used"])

    def test_checkpoint_refresh_same_identity_blocks(self):
        snap = self.refresh_snapshot()
        snap["new_handoff"]["checkpoint_id"] = snap["prior_handoff"]["checkpoint_id"]
        self.assertBlocked(snap)

    def test_checkpoint_refresh_without_prior_retention_blocks(self):
        snap = self.refresh_snapshot()
        snap["new_handoff"]["retained_historical_checkpoint_ids"] = ["PNCC-CONTINUATION-CHECKPOINT-WU115-CLEAN-A1"]
        self.assertBlocked(snap)

    def test_more_than_eight_retained_identities_blocks(self):
        record = copy.deepcopy(self.record)
        record["retained_historical_checkpoint_ids"] = [f"PNCC-CONTINUATION-CHECKPOINT-HISTORY-{i:02d}-AAAA" for i in range(9)]
        with self.assertRaises(module.MultiSessionError):
            module.validate_handoff_record(record, self.policy)

    def test_sensitive_checkpoint_flag_blocks(self):
        record = copy.deepcopy(self.record)
        record["contains_credentials"] = True
        with self.assertRaises(module.MultiSessionError):
            module.validate_handoff_record(record, self.policy)


if __name__ == "__main__":
    unittest.main()
