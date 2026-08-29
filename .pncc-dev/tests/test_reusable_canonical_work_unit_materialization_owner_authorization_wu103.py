import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / '.pncc-dev/contracts/reusable-canonical-work-unit-materialization-authority-preparation.json'
RECEIPT = ROOT / '.pncc-dev/attestations/reusable-canonical-work-unit-materialization-owner-authorization-wu103.json'
GRANT = ROOT / '.pncc-dev/contracts/reusable-canonical-work-unit-materialization-authorized.json'

PREPARATION_MERGE_MAIN = 'a337c0c775df959fdb55d86dcace71204f508dae'
PREP_BLOB = '39066812c079bbfb9b0a4b598427f65d6ec4f9a8'
RECEIPT_BLOB = '77097901769fbed927a6cf4a5f8e0172c97527d3'
GRANT_BLOB = '39db0554b86932b1beb4bb7250d040c06f9371ea'
FRONTIER_BLOB_AT_AUTHORIZATION = '3897e6db3bb9d853de7b4b04cebc82c6f0d55563'
SCOPE = 'REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_ONLY'
ANCHORS = {
    'planner': ('.pncc-dev/scripts/plan_governed_work_unit_materialization.py', 'c561b34dbf3fb7cfefd1a2a9780aba6e857ec78c'),
    'materialization_policy': ('.pncc-dev/contracts/governed-work-unit-materialization-policy.json', '8b6b6d9116b96a8f4746c22906a522589a9ae6e0'),
    'selector': ('.pncc-dev/scripts/select_provider_work_unit.py', '8045a97d5344f058064690cb265b30f88973e2b8'),
    'selection_governance': ('docs/governance/PROVIDER_TRUTH_WORK_UNIT_SELECTION.md', 'c6b5c9e394415febd586273d3e64ef01c8628cf8'),
    'work_unit_schema': ('.pncc-dev/schemas/work-unit.schema.json', 'a6b23c5695262192175216e6293d832f8e835851'),
}


def git_blob(path: Path) -> str:
    return subprocess.check_output(['git', 'hash-object', str(path)], cwd=ROOT, text=True).strip()


class ReusableCanonicalWorkUnitMaterializationOwnerAuthorizationWu103Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prep = json.loads(PREP.read_text(encoding='utf-8'))
        cls.receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
        cls.grant = json.loads(GRANT.read_text(encoding='utf-8'))

    def test_exact_primary_blob_anchors(self):
        self.assertEqual(git_blob(PREP), PREP_BLOB)
        self.assertEqual(git_blob(RECEIPT), RECEIPT_BLOB)
        self.assertEqual(git_blob(GRANT), GRANT_BLOB)

    def test_all_immutable_bound_anchors_are_exact(self):
        for key, (path, expected_blob) in ANCHORS.items():
            self.assertEqual(git_blob(ROOT / path), expected_blob, key)
            self.assertEqual(self.grant['bound_anchor_paths'][key], path, key)
            self.assertEqual(self.grant['bound_anchor_blobs'][key], expected_blob, key)
            self.assertEqual(self.receipt['bound_immutable_anchors'][key], expected_blob, key)

    def test_owner_authorization_binding_is_exact(self):
        r = self.receipt
        g = self.grant
        self.assertEqual(r['role'], 'REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_OWNER_AUTHORIZATION')
        self.assertEqual(r['authorization_state'], 'AUTHORIZED')
        self.assertEqual(r['authorization_scope'], SCOPE)
        self.assertEqual(r['preparation_merge_main_sha'], PREPARATION_MERGE_MAIN)
        self.assertEqual(r['prepared_contract_blob_sha'], PREP_BLOB)
        self.assertEqual(g['role'], 'REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORIZED')
        self.assertEqual(g['authorization_state'], 'AUTHORIZED')
        self.assertEqual(g['authorization_scope'], SCOPE)
        self.assertEqual(g['preparation_merge_main_sha'], PREPARATION_MERGE_MAIN)
        self.assertEqual(g['prepared_contract_blob_sha'], PREP_BLOB)
        self.assertEqual(g['owner_authorization_receipt_blob_sha'], RECEIPT_BLOB)

    def test_only_single_new_planner_derived_issue_create_is_granted(self):
        g = self.grant
        self.assertIs(g['reusable_authority_granted'], True)
        self.assertIs(g['reusable_issue_creation_authority'], True)
        self.assertEqual(g['issue_create_operation_policy'], 'EXACT_SINGLE_NEW_PLANNER_DERIVED_ISSUE_CREATE_ONLY')
        self.assertEqual(g['maximum_new_issues_per_transaction'], 1)
        forbidden = [
            'existing_issue_update_authority',
            'existing_issue_close_authority',
            'unrelated_issue_mutation_authority',
            'branch_mutation_authority',
            'pull_request_mutation_authority',
            'provider_state_write_authority',
            'lease_acquisition_authority',
            'heartbeat_authority',
            'release_authority',
            'autonomous_merge_authority',
            'direct_main_write_authority',
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
            self.assertIs(g[key], False, key)

    def test_per_transaction_fail_closed_guards_are_mandatory(self):
        g = self.grant
        required_true = [
            'frontier_must_be_canonical_on_fresh_current_main',
            'frontier_blob_sha_must_be_recorded_per_transaction',
            'per_transaction_fresh_current_main_required',
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
            self.assertIs(g[key], True, key)
        self.assertEqual(g['duplicate_or_ambiguous_work_unit_behavior'], 'BLOCK_FAIL_CLOSED')
        self.assertEqual(g['stale_or_unknown_provider_state_behavior'], 'BLOCK_FAIL_CLOSED')
        self.assertEqual(g['immutable_anchor_drift_behavior'], 'BLOCK_FAIL_CLOSED')
        self.assertEqual(g['revocation_behavior'], 'BLOCK_FAIL_CLOSED')

    def test_frontier_is_dynamic_not_lifetime_authority_anchor(self):
        r = self.receipt
        g = self.grant
        self.assertEqual(r['frontier_blob_sha_at_authorization'], FRONTIER_BLOB_AT_AUTHORIZATION)
        self.assertIs(r['frontier_is_dynamic_governed_input'], True)
        self.assertIs(r['frontier_blob_is_lifetime_authority_anchor'], False)
        self.assertEqual(g['frontier_semantics'], 'DYNAMIC_GOVERNED_INPUT_REVALIDATED_EVERY_TRANSACTION')
        self.assertIs(g['frontier_blob_is_lifetime_authority_anchor'], False)

    def test_preparation_remains_historical_default_deny(self):
        p = self.prep
        self.assertEqual(p['preparation_state'], 'WAITING_EXPLICIT_OWNER_AUTHORIZATION')
        self.assertIs(p['generic_continuation_counts_as_authorization'], False)
        self.assertIs(p['owner_authorization_present'], False)
        self.assertIs(p['owner_authorization_binding_complete'], False)
        self.assertIs(p['reusable_authority_granted'], False)
        self.assertIs(p['reusable_issue_creation_authority'], False)
        self.assertIs(p['issue_update_authority'], False)
        self.assertIs(p['issue_close_authority'], False)
        self.assertIs(p['branch_mutation_authority'], False)
        self.assertIs(p['pull_request_mutation_authority'], False)
        self.assertIs(p['provider_state_write_authority'], False)
        self.assertIs(p['lease_acquisition_authority'], False)
        self.assertIs(p['autonomous_merge_authority'], False)
        self.assertIs(p['reserve_1080_lifecycle_mutation_authority'], False)
        self.assertIs(p['primary_1081_lifecycle_mutation_authority'], False)

    def test_owner_receipt_matches_requested_exclusions(self):
        e = self.receipt['exclusions']
        for key, value in e.items():
            self.assertIs(value, True, key)
        self.assertEqual(self.receipt['grants'], {'reusable_single_planner_derived_issue_create': True})
        self.assertEqual(self.receipt['maximum_new_issues_per_transaction'], 1)


if __name__ == '__main__':
    unittest.main()
