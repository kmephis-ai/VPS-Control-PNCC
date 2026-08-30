import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/validate_writer_lease_registry_historical_state_reconciliation_authority_preparation.py"
CONTRACT = ROOT / ".pncc-dev/contracts/writer-lease-registry-historical-state-reconciliation-authority-preparation-wu121.json"
spec = importlib.util.spec_from_file_location("wu121prep", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def lease(lease_id, work_unit_id, generation, state, expires_at, *, base_sha="base", branch="branch"):
    return {
        "schema_version": 1,
        "role": "WRITER_LEASE",
        "lease_id": lease_id,
        "work_unit_id": work_unit_id,
        "conflict_domain": "test-domain-" + str(generation),
        "holder": "chatgpt-wave5-writer",
        "base_sha": base_sha,
        "branch": branch,
        "state": state,
        "generation": generation,
        "acquired_at": "2026-08-29T00:00:00Z",
        "heartbeat_at": "2026-08-29T00:00:00Z",
        "expires_at": expires_at,
    }


def registry_fixture():
    entries = [
        lease("3bf7a003-1e8e-4ab2-910d-0c1d4aba9b03", "PIPE-WU-096", 1, "ACTIVE", "2026-08-29T18:54:21Z"),
        lease("ee8b93cb-c629-4f69-82c6-25793fd10d8f", "PIPE-WU-105", 10, "ACTIVE", "2026-08-30T01:03:16Z"),
        lease("38a86545-e9b7-47eb-9b6e-3c9974bbd020", "PIPE-WU-105", 11, "ACTIVE", "2026-08-30T06:27:33Z"),
        lease("9c2dcb40-26dc-4dce-aa4f-c1be79a66983", "PIPE-WU-108", 15, "ACTIVE", "2026-08-30T10:23:00Z"),
        lease(
            "08e426fc-4bc5-40e6-a408-da4d7d06e97b",
            "PIPE-WU-121",
            29,
            "ACTIVE",
            "2026-08-30T17:13:00Z",
            base_sha="4bf295f43f46850b0a74341066b9d3719d862353",
            branch="agent/PIPE-WU-121-writer-lease-registry-historical-state-reconciliation",
        ),
    ]
    return {"schema_version": 1, "role": "WRITER_LEASE_REGISTRY", "generation": 29, "entries": entries}


class WriterLeaseHistoricalReconciliationPreparationWU121Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_live_contract_and_canonical_anchors_valid(self):
        mod.validate_contract(copy.deepcopy(self.contract))

    def test_exact_identity_and_waiting_state(self):
        c = self.contract
        self.assertEqual(c["role"], "WRITER_LEASE_REGISTRY_HISTORICAL_STATE_RECONCILIATION_AUTHORITY_PREPARATION")
        self.assertEqual(c["preparation_state"], "WAITING_EXPLICIT_OWNER_AUTHORIZATION")
        self.assertEqual(c["future_scope"], mod.EXPECTED_SCOPE)
        self.assertEqual(c["preparation_base_main_sha"], mod.EXPECTED_BASE)
        self.assertEqual(c["work_unit_id"], "PIPE-WU-121")
        self.assertEqual(c["issue_number"], 290)

    def test_generic_continue_is_not_owner_authorization(self):
        c = self.contract
        self.assertTrue(c["explicit_owner_authorization_required"])
        self.assertFalse(c["generic_continuation_text_is_owner_authorization"])
        self.assertFalse(c["owner_authorization_present"])
        self.assertFalse(c["owner_authorization_binding_complete"])

    def test_preparation_does_not_claim_historical_mutation(self):
        self.assertFalse(self.contract["historical_state_mutation_performed_in_preparation"])

    def test_all_authority_flags_are_false(self):
        for field in mod.FALSE_AUTHORITY_FIELDS:
            self.assertIs(self.contract[field], False, field)

    def test_future_owner_binding_is_exact(self):
        c = self.contract
        self.assertTrue(c["future_owner_receipt_must_bind_preparation_contract_blob_sha"])
        self.assertTrue(c["future_owner_receipt_must_bind_preparation_merge_main_sha"])
        self.assertEqual(c["future_owner_receipt_must_bind_authorization_scope"], mod.EXPECTED_SCOPE)
        self.assertEqual(c["next_boundary"], "EXPLICIT_OWNER_AUTHORIZATION_BOUND_TO_WU121_PREPARATION_MERGE_MAIN_AND_CONTRACT_BLOB")

    def test_predecessor_frontier_is_immutable_base_reference(self):
        self.assertEqual(
            self.contract["predecessor_frontier"],
            {
                "path": ".pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json",
                "blob_sha": "a6bb097dcc210c7cd64154565808c16015c74b86",
                "frontier_id": "WRITER_LEASE_REGISTRY_HISTORICAL_STATE_RECONCILIATION",
            },
        )

    def test_observed_registry_fixture_valid(self):
        mod.validate_observed_registry(self.contract, registry_fixture())

    def test_missing_stale_entry_fails_closed(self):
        r = registry_fixture()
        r["entries"] = [x for x in r["entries"] if x["lease_id"] != "38a86545-e9b7-47eb-9b6e-3c9974bbd020"]
        with self.assertRaises(mod.PreparationError):
            mod.validate_observed_registry(self.contract, r)

    def test_extra_expired_active_entry_fails_closed(self):
        r = registry_fixture()
        r["entries"].append(lease("extra-expired-active", "PIPE-WU-X", 28, "ACTIVE", "2026-08-30T12:00:00Z"))
        with self.assertRaises(mod.PreparationError):
            mod.validate_observed_registry(self.contract, r)

    def test_stale_entry_rejuvenation_fails_closed(self):
        r = registry_fixture()
        next(x for x in r["entries"] if x["lease_id"] == "9c2dcb40-26dc-4dce-aa4f-c1be79a66983")["expires_at"] = "2026-08-30T17:30:00Z"
        with self.assertRaises(mod.PreparationError):
            mod.validate_observed_registry(self.contract, r)

    def test_current_writer_binding_drift_fails_closed(self):
        r = registry_fixture()
        next(x for x in r["entries"] if x["lease_id"] == mod.EXPECTED_CURRENT_LEASE)["branch"] = "agent/wrong"
        with self.assertRaises(mod.PreparationError):
            mod.validate_observed_registry(self.contract, r)

    def test_current_writer_expired_at_reference_fails_closed(self):
        r = registry_fixture()
        next(x for x in r["entries"] if x["lease_id"] == mod.EXPECTED_CURRENT_LEASE)["expires_at"] = "2026-08-30T16:13:59Z"
        with self.assertRaises(mod.PreparationError):
            mod.validate_observed_registry(self.contract, r)

    def test_duplicate_lease_id_fails_closed(self):
        r = registry_fixture()
        r["entries"].append(copy.deepcopy(r["entries"][0]))
        with self.assertRaises(mod.PreparationError):
            mod.validate_observed_registry(self.contract, r)

    def test_expected_candidate_shape_valid(self):
        before = registry_fixture()
        after = mod.build_expected_reconciled_registry(before)
        mod.validate_authorized_candidate_shape(before, after)
        self.assertEqual(before["generation"], after["generation"])
        self.assertEqual([x["lease_id"] for x in before["entries"]], [x["lease_id"] for x in after["entries"]])

    def test_partial_reconciliation_fails_closed(self):
        before = registry_fixture()
        after = mod.build_expected_reconciled_registry(before)
        next(x for x in after["entries"] if x["lease_id"] == "38a86545-e9b7-47eb-9b6e-3c9974bbd020")["state"] = "ACTIVE"
        with self.assertRaises(mod.PreparationError):
            mod.validate_authorized_candidate_shape(before, after)

    def test_unrelated_current_writer_change_fails_closed(self):
        before = registry_fixture()
        after = mod.build_expected_reconciled_registry(before)
        next(x for x in after["entries"] if x["lease_id"] == mod.EXPECTED_CURRENT_LEASE)["state"] = "RELEASED"
        with self.assertRaises(mod.PreparationError):
            mod.validate_authorized_candidate_shape(before, after)

    def test_stale_timestamp_change_fails_closed(self):
        before = registry_fixture()
        after = mod.build_expected_reconciled_registry(before)
        next(x for x in after["entries"] if x["lease_id"] == "3bf7a003-1e8e-4ab2-910d-0c1d4aba9b03")["heartbeat_at"] = "2026-08-30T16:14:00Z"
        with self.assertRaises(mod.PreparationError):
            mod.validate_authorized_candidate_shape(before, after)

    def test_registry_generation_change_fails_closed(self):
        before = registry_fixture()
        after = mod.build_expected_reconciled_registry(before)
        after["generation"] = 30
        with self.assertRaises(mod.PreparationError):
            mod.validate_authorized_candidate_shape(before, after)

    def test_entry_order_change_fails_closed(self):
        before = registry_fixture()
        after = mod.build_expected_reconciled_registry(before)
        after["entries"][0], after["entries"][1] = after["entries"][1], after["entries"][0]
        with self.assertRaises(mod.PreparationError):
            mod.validate_authorized_candidate_shape(before, after)

    def test_authority_flip_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["writer_lease_historical_mutation_authority"] = True
        with self.assertRaises(mod.PreparationError):
            mod.validate_contract(c, check_anchor_content=False)

    def test_owner_authorization_in_preparation_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["owner_authorization_present"] = True
        with self.assertRaises(mod.PreparationError):
            mod.validate_contract(c, check_anchor_content=False)

    def test_false_claim_of_completed_mutation_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["historical_state_mutation_performed_in_preparation"] = True
        with self.assertRaises(mod.PreparationError):
            mod.validate_contract(c, check_anchor_content=False)

    def test_provider_snapshot_drift_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["provider_snapshot"]["registry_blob_sha"] = "0" * 40
        with self.assertRaises(mod.PreparationError):
            mod.validate_contract(c, check_anchor_content=False)

    def test_historical_set_superset_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["exact_historical_set"].append({"lease_id":"x","work_unit_id":"PIPE-WU-X","generation":999,"expected_pre_state":"ACTIVE","authorized_post_state":"RELEASED"})
        with self.assertRaises(mod.PreparationError):
            mod.validate_contract(c, check_anchor_content=False)

    def test_reference_time_drift_fails_closed(self):
        c = copy.deepcopy(self.contract)
        c["preparation_reference_time"] = "2026-08-30T17:30:00Z"
        with self.assertRaises(mod.PreparationError):
            mod.validate_contract(c, check_anchor_content=False)


if __name__ == "__main__":
    unittest.main()
