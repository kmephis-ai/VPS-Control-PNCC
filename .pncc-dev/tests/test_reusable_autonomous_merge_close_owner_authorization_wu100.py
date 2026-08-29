import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / '.pncc-dev/contracts/reusable-autonomous-merge-close-authority-preparation.json'
POLICY = ROOT / '.pncc-dev/contracts/autonomous-merge-issue-close-eligibility-policy.json'
RECEIPT = ROOT / '.pncc-dev/attestations/reusable-autonomous-merge-close-owner-authorization-wu100.json'
GRANT = ROOT / '.pncc-dev/contracts/reusable-autonomous-merge-close-authorized.json'

PREPARATION_MAIN = 'f6d3906ce60a7c44ff9910c0d8475aa81db0702e'
PREP_BLOB = 'd4cfd9d740e8323bc8686f32b46db2bbfaa53f20'
POLICY_BLOB = '8999f027e47e2b6da04f30a12ae9414cb3b7d05c'
RECEIPT_BLOB = '1440aef6a7fffaee06149ef13b86bd17172ecc3e'
GRANT_BLOB = 'baa503d63eaa437545ddcf0a045cf864d1ef36e6'
SCOPE = 'REUSABLE_BOUNDED_AUTONOMOUS_MERGE_CLOSE_ONLY'


def git_blob(path: Path) -> str:
    return subprocess.check_output(['git', 'hash-object', str(path)], cwd=ROOT, text=True).strip()


class ReusableMergeCloseOwnerAuthorizationWu100Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prep = json.loads(PREP.read_text(encoding='utf-8'))
        cls.policy = json.loads(POLICY.read_text(encoding='utf-8'))
        cls.receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
        cls.grant = json.loads(GRANT.read_text(encoding='utf-8'))

    def test_exact_blob_anchors(self):
        self.assertEqual(git_blob(PREP), PREP_BLOB)
        self.assertEqual(git_blob(POLICY), POLICY_BLOB)
        self.assertEqual(git_blob(RECEIPT), RECEIPT_BLOB)
        self.assertEqual(git_blob(GRANT), GRANT_BLOB)

    def test_exact_owner_authorization_binding(self):
        r = self.receipt
        g = self.grant
        self.assertEqual(r['role'], 'REUSABLE_AUTONOMOUS_MERGE_CLOSE_OWNER_AUTHORIZATION')
        self.assertEqual(r['authorization_state'], 'AUTHORIZED')
        self.assertEqual(r['authorization_scope'], SCOPE)
        self.assertEqual(r['preparation_main_sha'], PREPARATION_MAIN)
        self.assertEqual(r['prepared_contract_blob_sha'], PREP_BLOB)
        self.assertEqual(r['eligibility_policy_blob_sha'], POLICY_BLOB)
        self.assertEqual(g['authorization_scope'], SCOPE)
        self.assertEqual(g['preparation_main_sha'], PREPARATION_MAIN)
        self.assertEqual(g['prepared_contract_blob_sha'], PREP_BLOB)
        self.assertEqual(g['eligibility_policy_blob_sha'], POLICY_BLOB)
        self.assertEqual(g['owner_authorization_receipt_blob_sha'], RECEIPT_BLOB)

    def test_only_reusable_merge_and_close_authority_is_granted(self):
        g = self.grant
        self.assertIs(g['reusable_authority_granted'], True)
        self.assertIs(g['reusable_autonomous_merge_authority'], True)
        self.assertIs(g['reusable_autonomous_issue_close_authority'], True)
        forbidden = [
            'direct_main_write_authority',
            'runtime_required_work_unit_authority',
            'runtime_action_authority',
            'product_runtime_mutation_authority',
            'provider_state_write_authority',
            'lease_acquisition_authority',
            'heartbeat_authority',
            'release_authority',
            'adwf_binding_mutation_authority',
            'promotion_release_tag_authority',
            'ruleset_policy_mutation_authority',
            'private_evidence_publication_authority',
            'unrelated_pr_issue_mutation_authority',
            'force_ref_update_authority',
            'silent_lease_steal_authority',
            'reserve_1080_lifecycle_mutation_authority',
            'primary_1081_lifecycle_mutation_authority',
        ]
        self.assertTrue(all(g[k] is False for k in forbidden), forbidden)

    def test_per_transaction_guards_are_mandatory(self):
        g = self.grant
        required_true = [
            'per_transaction_fresh_provider_truth_required',
            'per_transaction_deterministic_work_unit_selection_required',
            'per_transaction_runtime_required_must_be_false',
            'per_transaction_exact_non_main_work_unit_branch_required',
            'per_transaction_exact_released_writer_lease_required',
            'per_transaction_exact_pr_base_and_head_required',
            'per_transaction_current_head_full_ci_success_required',
            'per_transaction_no_pending_checks_required',
            'per_transaction_no_provider_state_drift_after_release_required',
            'per_transaction_no_head_drift_after_ci_required',
            'per_transaction_no_protected_surface_violation_required',
            'per_transaction_merge_eligible_decision_required',
            'post_merge_fresh_readback_required',
            'post_merge_current_main_must_equal_actual_merge_sha',
            'per_transaction_close_eligible_decision_required',
        ]
        for key in required_true:
            self.assertIs(g[key], True, key)
        self.assertEqual(g['merge_operation_policy'], 'PINNED_EXPECTED_HEAD_PR_MERGE_ONLY')
        self.assertEqual(g['merge_target_policy'], 'EXACT_SELECTED_WORK_UNIT_PR_ONLY')
        self.assertEqual(g['issue_close_policy'], 'EXACT_SELECTED_WORK_UNIT_ISSUE_ONLY_AFTER_CLOSE_ELIGIBLE')
        self.assertEqual(g['anchor_drift_behavior'], 'BLOCK_FAIL_CLOSED')
        self.assertEqual(g['revocation_behavior'], 'BLOCK_FAIL_CLOSED')

    def test_preparation_remains_historical_default_deny(self):
        p = self.prep
        self.assertEqual(p['preparation_state'], 'WAITING_EXPLICIT_OWNER_AUTHORIZATION')
        self.assertIs(p['owner_authorization_present'], False)
        self.assertIs(p['owner_authorization_binding_complete'], False)
        self.assertIs(p['reusable_authority_granted'], False)
        self.assertIs(p['reusable_autonomous_merge_authority'], False)
        self.assertIs(p['reusable_autonomous_issue_close_authority'], False)

    def test_bound_eligibility_policy_remains_read_only(self):
        p = self.policy
        self.assertEqual(p['role'], 'AUTONOMOUS_MERGE_ISSUE_CLOSE_ELIGIBILITY_POLICY')
        self.assertEqual(p['mode'], 'READ_ONLY_ADVISORY')
        self.assertEqual(p['unknown_or_stale_state_policy'], 'BLOCK_FAIL_CLOSED')
        self.assertIs(p['autonomous_merge_authority'], False)
        self.assertIs(p['autonomous_issue_close_authority'], False)


if __name__ == '__main__':
    unittest.main()
