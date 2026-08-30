import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/validate_reusable_autonomous_continuation_executor_authority_preparation.py"
CONTRACT = ROOT / ".pncc-dev/contracts/reusable-autonomous-continuation-executor-authority-preparation.json"
spec = importlib.util.spec_from_file_location("wu110prep", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class ReusableAutonomousContinuationExecutorPreparationWU110Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_live_contract_valid(self):
        mod.validate(copy.deepcopy(self.contract))

    def test_exact_identity_and_waiting_state(self):
        c = self.contract
        self.assertEqual(c["role"], "REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_AUTHORITY_PREPARATION")
        self.assertEqual(c["preparation_state"], "WAITING_EXPLICIT_OWNER_AUTHORIZATION")
        self.assertEqual(c["future_scope"], "REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_ONLY")
        self.assertEqual(c["preparation_base_main_sha"], "435d856c0747a91e1208d904e22bed820b12a224")

    def test_generic_continuation_is_not_authorization(self):
        self.assertTrue(self.contract["explicit_owner_authorization_required"])
        self.assertFalse(self.contract["generic_continuation_text_is_owner_authorization"])
        self.assertFalse(self.contract["owner_authorization_present"])
        self.assertFalse(self.contract["owner_authorization_binding_complete"])

    def test_future_owner_binding_is_exact(self):
        c = self.contract
        self.assertEqual(c["future_owner_authorization_receipt_path"], ".pncc-dev/attestations/reusable-autonomous-continuation-executor-owner-authorization-wu111.json")
        self.assertEqual(c["future_authorized_grant_path"], ".pncc-dev/contracts/reusable-autonomous-continuation-executor-authorized.json")
        self.assertTrue(c["future_owner_receipt_must_bind_preparation_contract_blob_sha"])
        self.assertTrue(c["future_owner_receipt_must_bind_preparation_merge_main_sha"])
        self.assertEqual(c["future_owner_receipt_must_bind_authorization_scope"], "REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_ONLY")

    def test_all_authority_flags_are_false(self):
        for field in mod.FALSE_AUTHORITY_FIELDS:
            self.assertIs(self.contract[field], False, field)

    def test_all_transaction_gates_are_true(self):
        for field in mod.TRUE_GATE_FIELDS:
            self.assertIs(self.contract[field], True, field)

    def test_exact_anchor_map(self):
        expected_paths = {k: v[0] for k, v in mod.EXPECTED_ANCHORS.items()}
        expected_blobs = {k: v[1] for k, v in mod.EXPECTED_ANCHORS.items()}
        self.assertEqual(self.contract["anchor_paths"], expected_paths)
        self.assertEqual(self.contract["anchor_blobs"], expected_blobs)

    def test_non_mutating_admission_states_stay_non_mutating(self):
        d = self.contract["delegation_policy"]
        self.assertEqual(d["WAIT_ONLY"], "NO_MUTATION")
        self.assertEqual(d["STOP_ONLY"], "NO_MUTATION")
        self.assertEqual(d["SEPARATE_AUTHORITY_REQUIRED"], "NO_MUTATION_AND_SEPARATE_EXPLICIT_AUTHORITY_REQUIRED")
        self.assertEqual(d["BLOCKED"], "NO_MUTATION_FAIL_CLOSED")

    def test_mutating_paths_delegate_only_to_existing_grants(self):
        d = self.contract["delegation_policy"]
        self.assertEqual(d["ADMIT_EXISTING_MATERIALIZATION_AUTHORITY"], "EXISTING_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY")
        self.assertEqual(d["ADMIT_EXISTING_WRITER_LEASE_AUTHORITY"], "EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY")
        self.assertEqual(d["ADMIT_EXISTING_MERGE_CLOSE_AUTHORITY"], "EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY")

    def test_stale_preparation_base_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["preparation_base_main_sha"] = "0" * 40
        with self.assertRaises(mod.PreparationError):
            mod.validate(c)

    def test_premature_owner_authorization_fails_preparation_validation(self):
        c = copy.deepcopy(self.contract)
        c["owner_authorization_present"] = True
        with self.assertRaises(mod.PreparationError):
            mod.validate(c)

    def test_premature_reusable_authority_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["reusable_autonomous_continuation_executor_authority"] = True
        with self.assertRaises(mod.PreparationError):
            mod.validate(c)

    def test_anchor_declaration_drift_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["anchor_blobs"]["admission_policy"] = "0" * 40
        with self.assertRaises(mod.PreparationError):
            mod.validate(c)

    def test_delegation_broadening_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["delegation_policy"]["WAIT_ONLY"] = "EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY"
        with self.assertRaises(mod.PreparationError):
            mod.validate(c)

    def test_interruption_and_failure_semantics_are_fail_closed(self):
        self.assertEqual(self.contract["interruption_behavior"], "STOP_OR_WAIT_FAIL_CLOSED_AND_REEVALUATE_FRESH_PROVIDER_TRUTH")
        self.assertEqual(self.contract["classified_failure_behavior"], "SEPARATE_AUTHORITY_REQUIRED_NO_GUESSED_RECOVERY")
        self.assertEqual(self.contract["unknown_or_contradictory_behavior"], "BLOCK_FAIL_CLOSED")

    def test_next_boundary_requires_exact_owner_binding(self):
        self.assertEqual(self.contract["next_boundary"], "EXPLICIT_OWNER_AUTHORIZATION_BOUND_TO_PREPARATION_MERGE_MAIN_AND_CONTRACT_BLOB")


if __name__ == "__main__":
    unittest.main()
