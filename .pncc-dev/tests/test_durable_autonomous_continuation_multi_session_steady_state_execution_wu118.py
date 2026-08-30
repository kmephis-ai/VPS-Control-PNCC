import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / ".pncc-dev/scripts/validate_durable_autonomous_continuation_multi_session_steady_state_execution_wu118.py"
EVIDENCE_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-steady-state-execution-wu118.json"
EVALUATOR_PATH = ROOT / ".pncc-dev/scripts/evaluate_durable_autonomous_continuation_multi_session_steady_state.py"
POLICY_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-steady-state-policy.json"
SESSION1_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-handoff-record-wu117.json"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


V = load_module(VALIDATOR_PATH, "wu118_validator_tests")
M = load_module(EVALUATOR_PATH, "wu118_evaluator_tests")


class WU118MultiSessionExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE_PATH.read_text())
        cls.policy = json.loads(POLICY_PATH.read_text())
        cls.session1 = json.loads(SESSION1_PATH.read_text())

    def ev(self):
        return copy.deepcopy(self.evidence)

    def assert_blocked(self, evidence):
        with self.assertRaises(V.ValidationError):
            V.validate_evidence(evidence, check_anchors=False, replay=False)

    def test_canonical_evidence_replays(self):
        result = V.validate_evidence(self.ev(), check_anchors=True, replay=True)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["independent_session_count"], 2)
        self.assertTrue(result["session_start_replayed"])
        self.assertFalse(result["authority_broadening_performed"])

    def test_session_count_must_be_two(self):
        e = self.ev(); e["independent_session_count"] = 1
        self.assert_blocked(e)

    def test_session_sequence_must_be_monotonic(self):
        e = self.ev(); e["session_2_start"]["session_sequence"] = 3
        self.assert_blocked(e)

    def test_session_identity_must_be_distinct(self):
        e = self.ev(); e["session_2_start"]["session_id"] = e["session_1"]["session_id"]
        self.assert_blocked(e)

    def test_checkpoint_identity_must_advance(self):
        e = self.ev(); e["session_2_handoff_refresh"]["new_checkpoint_id"] = e["session_1"]["checkpoint_id"]
        self.assert_blocked(e)

    def test_provider_drift_must_be_proven(self):
        e = self.ev(); e["provider_drift_between_sessions_detected"] = False
        self.assert_blocked(e)

    def test_prior_checkpoint_cannot_authorize_session2(self):
        e = self.ev(); e["session_2_start"]["prior_checkpoint_authority_used"] = True
        self.assert_blocked(e)

    def test_prior_control_loop_cannot_be_reused(self):
        e = self.ev(); e["session_2_start"]["prior_control_loop_reused"] = True
        self.assert_blocked(e)

    def test_prior_registry_cas_cannot_be_reused(self):
        e = self.ev(); e["session_2_start"]["prior_cas_reused"] = True
        self.assert_blocked(e)

    def test_prior_writer_lease_cannot_be_reused(self):
        e = self.ev(); e["session_2_start"]["prior_writer_lease_ownership_reused"] = True
        self.assert_blocked(e)

    def test_wu117_must_be_released_at_session2_start(self):
        e = self.ev(); e["session_2_start"]["provider_state_before_transaction"]["wu117_lease_state"] = "ACTIVE"
        self.assert_blocked(e)

    def test_wu118_must_be_absent_before_acquisition(self):
        e = self.ev(); e["session_2_start"]["provider_state_before_transaction"]["wu118_lease_present"] = True
        self.assert_blocked(e)

    def test_generation_chain_must_be_25_to_26(self):
        e = self.ev(); e["session_2_iterations"][0]["provider_state_after"]["registry_generation"] = 27
        self.assert_blocked(e)

    def test_second_iteration_does_not_advance_registry_generation(self):
        e = self.ev(); e["session_2_iterations"][1]["provider_state_after"]["registry_generation"] = 27
        self.assert_blocked(e)

    def test_batched_transaction_is_forbidden(self):
        e = self.ev(); e["session_2_iterations"][0]["delegated_transaction_count"] = 2
        self.assert_blocked(e)

    def test_final_evidence_requires_readback(self):
        e = self.ev(); e["session_2_iterations"][0]["fresh_provider_readback_completed"] = False
        self.assert_blocked(e)

    def test_second_iteration_requires_previous_readback(self):
        e = self.ev(); e["session_2_iterations"][1]["previous_iteration_provider_readback_completed"] = False
        self.assert_blocked(e)

    def test_branch_compare_must_be_identical(self):
        e = self.ev(); e["session_2_iterations"][1]["branch_state_after"]["compare_status"] = "ahead"
        self.assert_blocked(e)

    def test_interrupted_path_must_not_replay_transaction(self):
        e = self.ev(); e["reconciliation_paths"]["interrupted"]["delegated_transaction_replayed"] = True
        self.assert_blocked(e)

    def test_pending_path_must_not_mutate_before_readback(self):
        e = self.ev(); e["reconciliation_paths"]["readback_pending"]["new_mutation_before_readback"] = True
        self.assert_blocked(e)

    def test_product_runtime_mutation_is_forbidden(self):
        e = self.ev(); e["product_runtime_mutation_performed"] = True
        self.assert_blocked(e)

    def test_authority_broadening_is_forbidden(self):
        e = self.ev(); e["authority_broadening_performed"] = True
        self.assert_blocked(e)

    def test_private_evidence_publication_is_forbidden(self):
        e = self.ev(); e["private_evidence_publication_performed"] = True
        self.assert_blocked(e)

    def test_session_start_with_stale_provider_truth_blocks(self):
        snapshot = V._session_start_snapshot(self.ev(), self.session1)
        snapshot["provider_truth_fresh"] = False
        with self.assertRaises(M.MultiSessionError):
            M.evaluate(snapshot, policy=self.policy, check_anchors=False)

    def test_session_start_with_reused_session_id_blocks(self):
        snapshot = V._session_start_snapshot(self.ev(), self.session1)
        snapshot["session_id"] = self.session1["session_id"]
        with self.assertRaises(M.MultiSessionError):
            M.evaluate(snapshot, policy=self.policy, check_anchors=False)

    def test_interrupted_start_requires_reconciliation(self):
        prior = copy.deepcopy(self.session1)
        prior["handoff_class"] = "TRANSACTION_OUTCOME_UNKNOWN"
        result = M.evaluate(V._session_start_snapshot(self.ev(), prior), policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "RECONCILE_INTERRUPTED_SESSION")
        self.assertTrue(result["provider_reconciliation_required"])
        self.assertFalse(result["prior_checkpoint_authority_used"])

    def test_pending_start_requires_readback(self):
        prior = copy.deepcopy(self.session1)
        prior["handoff_class"] = "PROVIDER_READBACK_PENDING"
        prior["provider_readback_completed"] = False
        result = M.evaluate(V._session_start_snapshot(self.ev(), prior), policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "WAIT_FOR_PROVIDER_READBACK")
        self.assertTrue(result["provider_readback_required"])
        self.assertFalse(result["prior_checkpoint_authority_used"])

    def test_iteration_without_readback_stops_at_readback_boundary(self):
        item = self.ev()["session_2_iterations"][0]
        snapshot = {
            "schema_version": 1,
            "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_SNAPSHOT",
            "phase": "ITERATION",
            "repository": "kmephis-ai/VPS-Control-PNCC",
            "default_branch": "main",
            "classified_failure_detected": False,
            "provider_truth_fresh": True,
            "session_sequence": 2,
            "iteration_sequence": 1,
            "control_loop_fresh_for_iteration": True,
            "execution_admission_fresh_for_iteration": True,
            "control_loop_reused_from_prior_session": False,
            "execution_admission_reused_from_prior_session": False,
            "registry_cas_reused_from_prior_session": False,
            "previous_iteration_provider_readback_completed": False,
            "delegated_transaction": {
                "delegated_transaction_count": 1,
                "provider_mutation_performed": item["transaction_result"]["provider_mutation_performed"],
                "fresh_provider_readback_completed": False,
            },
        }
        result = M.evaluate(snapshot, policy=self.policy, check_anchors=False)
        self.assertEqual(result["decision"], "REQUIRE_PROVIDER_READBACK")
        self.assertTrue(result["provider_readback_required"])


if __name__ == "__main__":
    unittest.main()
