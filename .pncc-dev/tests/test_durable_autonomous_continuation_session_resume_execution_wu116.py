import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".pncc-dev/scripts/validate_durable_autonomous_continuation_session_resume_execution_wu116.py"
spec = importlib.util.spec_from_file_location("wu116_validator_tests", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class WU116DurableResumeExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = module.load_json(module.EVIDENCE_PATH)

    def assertBlocked(self, mutate):
        evidence = copy.deepcopy(self.canonical)
        mutate(evidence)
        with self.assertRaises(module.ValidationError):
            module.validate_evidence(evidence, check_anchors=False, replay=False)

    def test_canonical_evidence_replays_resume_and_two_fresh_iterations(self):
        result = module.validate_evidence(copy.deepcopy(self.canonical), check_anchors=True, replay=True)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["post_handoff_iterations_validated"], 2)
        self.assertTrue(result["checkpoint_provider_drift_proven"])

    def test_checkpoint_authority_blocks(self):
        self.assertBlocked(lambda e: e["handoff"].__setitem__("checkpoint_is_mutation_authority", True))

    def test_persisted_control_loop_reuse_blocks(self):
        self.assertBlocked(lambda e: e["handoff"].__setitem__("persisted_control_loop_reused", True))

    def test_persisted_cas_reuse_blocks(self):
        self.assertBlocked(lambda e: e["handoff"].__setitem__("persisted_registry_cas_reused", True))

    def test_checkpoint_drift_field_omission_blocks(self):
        self.assertBlocked(lambda e: e["fresh_resume_truth_before_transaction"]["checkpoint_drift_fields"].remove("provider_state"))

    def test_checkpoint_main_without_drift_blocks(self):
        self.assertBlocked(lambda e: e["fresh_resume_truth_before_transaction"].__setitem__("current_main_sha", e["handoff"]["checkpoint_recorded_main_sha"]))

    def test_nonfresh_control_loop_blocks(self):
        self.assertBlocked(lambda e: e["post_handoff_iterations"][0].__setitem__("control_loop_fresh_for_iteration", False))

    def test_nonfresh_execution_admission_blocks(self):
        self.assertBlocked(lambda e: e["post_handoff_iterations"][0].__setitem__("execution_admission_fresh_for_iteration", False))

    def test_batched_transaction_blocks(self):
        self.assertBlocked(lambda e: e["post_handoff_iterations"][0].__setitem__("delegated_transaction_count", 2))

    def test_missing_transaction_readback_blocks(self):
        self.assertBlocked(lambda e: e["post_handoff_iterations"][0].__setitem__("fresh_provider_readback_completed", False))

    def test_next_iteration_without_previous_readback_blocks(self):
        self.assertBlocked(lambda e: e["post_handoff_iterations"][1].__setitem__("previous_iteration_fresh_provider_readback_completed", False))

    def test_provider_chain_gap_blocks(self):
        self.assertBlocked(lambda e: e["post_handoff_iterations"][1]["provider_state_before"].__setitem__("registry_blob_sha", "0" * 40))

    def test_branch_compare_drift_blocks(self):
        def mutate(e):
            e["post_handoff_iterations"][1]["branch_state_after"]["compare_status"] = "ahead"
            e["post_handoff_iterations"][1]["branch_state_after"]["ahead_by"] = 1
        self.assertBlocked(mutate)

    def test_interrupted_transaction_replay_blocks(self):
        self.assertBlocked(lambda e: e["interrupted_checkpoint_path"].__setitem__("delegated_transaction_replayed", True))

    def test_readback_pending_mutation_blocks(self):
        self.assertBlocked(lambda e: e["readback_pending_checkpoint_path"].__setitem__("mutation_performed_before_readback", True))

    def test_main_drift_during_iterations_blocks(self):
        self.assertBlocked(lambda e: e.__setitem__("main_sha_after_iterations", "0" * 40))

    def test_product_runtime_mutation_blocks(self):
        self.assertBlocked(lambda e: e.__setitem__("product_runtime_mutation_performed", True))

    def test_authority_broadening_blocks(self):
        self.assertBlocked(lambda e: e.__setitem__("authority_broadening_performed", True))


if __name__ == "__main__":
    unittest.main()
