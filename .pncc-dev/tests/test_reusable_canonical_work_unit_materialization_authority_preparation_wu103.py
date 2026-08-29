from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev/contracts/reusable-canonical-work-unit-materialization-authority-preparation.json'


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f'blob {len(data)}\0'.encode('utf-8') + data).hexdigest()


class ReusableCanonicalWorkUnitMaterializationPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = json.loads(CONTRACT.read_text(encoding='utf-8'))

    def test_identity_and_default_deny(self):
        self.assertEqual(self.c['schema_version'], 1)
        self.assertEqual(self.c['role'], 'REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY_PREPARATION')
        self.assertEqual(self.c['preparation_state'], 'WAITING_EXPLICIT_OWNER_AUTHORIZATION')
        self.assertEqual(self.c['future_scope'], 'REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_ONLY')
        self.assertFalse(self.c['generic_continuation_counts_as_authorization'])
        self.assertFalse(self.c['owner_authorization_present'])
        self.assertFalse(self.c['owner_authorization_binding_complete'])
        self.assertFalse(self.c['reusable_authority_granted'])
        self.assertFalse(self.c['reusable_issue_creation_authority'])

    def test_exact_preparation_identity(self):
        self.assertEqual(self.c['preparation_main_sha'], 'dc2caccb903cd02fab38aa61b67ae3be03f0b021')
        self.assertEqual(self.c['preparation_work_unit_id'], 'PIPE-WU-103')
        self.assertEqual(self.c['preparation_issue_number'], 251)

    def test_immutable_anchor_blobs_are_exact(self):
        anchors = [
            ('planner_path', 'planner_blob_sha'),
            ('materialization_policy_path', 'materialization_policy_blob_sha'),
            ('selector_path', 'selector_blob_sha'),
            ('selection_governance_path', 'selection_governance_blob_sha'),
            ('work_unit_schema_path', 'work_unit_schema_blob_sha'),
        ]
        for path_key, sha_key in anchors:
            path = ROOT / self.c[path_key]
            self.assertTrue(path.is_file(), self.c[path_key])
            self.assertEqual(git_blob_sha(path), self.c[sha_key], self.c[path_key])

    def test_preparation_frontier_anchor_is_exact_but_dynamic_future_input(self):
        path = ROOT / self.c['frontier_path']
        self.assertEqual(git_blob_sha(path), self.c['frontier_blob_sha_at_preparation'])
        self.assertEqual(self.c['frontier_semantics'], 'DYNAMIC_GOVERNED_INPUT_REVALIDATED_EVERY_TRANSACTION')
        self.assertFalse(self.c['frontier_blob_is_lifetime_authority_anchor'])
        self.assertTrue(self.c['frontier_must_be_canonical_on_fresh_current_main'])
        self.assertTrue(self.c['frontier_blob_sha_must_be_recorded_per_transaction'])

    def test_future_transaction_requires_fresh_no_work_and_exact_proposal(self):
        required_true = [
            'per_transaction_fresh_provider_truth_required',
            'per_transaction_complete_issue_history_required',
            'per_transaction_selector_no_work_required',
            'per_transaction_no_open_canonical_work_unit_required',
            'per_transaction_materialization_eligible_required',
            'per_transaction_runtime_required_must_be_false',
            'per_transaction_proposal_base_must_equal_fresh_current_main',
            'per_transaction_exact_proposal_identity_required',
            'per_transaction_proposal_determinism_required',
            'per_transaction_exact_new_issue_absence_required_before_create',
            'post_create_fresh_provider_readback_required',
            'post_create_exact_issue_number_title_body_marker_match_required',
            'post_create_issue_must_be_open',
            'post_create_selector_must_select_exact_new_work_unit_or_fail_closed',
        ]
        for key in required_true:
            self.assertTrue(self.c[key], key)
        self.assertEqual(self.c['issue_create_operation_policy'], 'EXACT_SINGLE_NEW_PLANNER_DERIVED_ISSUE_CREATE_ONLY')
        self.assertEqual(self.c['maximum_new_issues_per_transaction'], 1)
        self.assertEqual(self.c['duplicate_or_ambiguous_work_unit_behavior'], 'BLOCK_FAIL_CLOSED')
        self.assertEqual(self.c['stale_or_unknown_provider_state_behavior'], 'BLOCK_FAIL_CLOSED')

    def test_existing_or_unrelated_issue_mutation_is_forbidden(self):
        self.assertTrue(self.c['existing_issue_mutation_forbidden'])
        self.assertTrue(self.c['unrelated_issue_mutation_forbidden'])
        self.assertFalse(self.c['issue_update_authority'])
        self.assertFalse(self.c['issue_close_authority'])

    def test_all_non_issue_create_authorities_remain_false(self):
        forbidden = [
            'pull_request_mutation_authority',
            'branch_mutation_authority',
            'provider_state_write_authority',
            'lease_acquisition_authority',
            'heartbeat_authority',
            'release_authority',
            'autonomous_merge_authority',
            'runtime_action_authority',
            'product_runtime_mutation_authority',
            'adwf_binding_mutation_authority',
            'promotion_release_tag_authority',
            'ruleset_policy_administration_authority',
            'private_evidence_publication_authority',
            'force_ref_update_authority',
            'silent_lease_steal_authority',
            'reserve_1080_lifecycle_mutation_authority',
            'primary_1081_lifecycle_mutation_authority',
        ]
        for key in forbidden:
            self.assertFalse(self.c[key], key)

    def test_authority_lifetime_and_boundary_fail_closed(self):
        self.assertEqual(
            self.c['authority_lifetime_policy'],
            'VALID_ONLY_WHILE_EXACT_GRANT_OWNER_RECEIPT_PREPARED_CONTRACT_AND_IMMUTABLE_PLANNER_POLICY_SELECTOR_SCHEMA_ANCHORS_REMAIN_CANONICAL_AND_NOT_REVOKED',
        )
        self.assertEqual(self.c['immutable_anchor_drift_or_revocation_behavior'], 'BLOCK_FAIL_CLOSED')
        self.assertEqual(
            self.c['next_boundary'],
            'EXPLICIT_OWNER_AUTHORIZATION_BOUND_TO_PREPARATION_MERGE_MAIN_AND_CONTRACT_BLOB',
        )


if __name__ == '__main__':
    unittest.main()
