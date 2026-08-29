import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / '.pncc-dev/contracts/reusable-writer-lease-bounded-branch-authority-preparation.json'
RECEIPT = ROOT / '.pncc-dev/attestations/reusable-writer-lease-bounded-branch-owner-authorization-wu101.json'
GRANT = ROOT / '.pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json'
HISTORICAL = ROOT / '.pncc-dev/contracts/writer-lease-lifecycle-branch-execution-authorized.json'

PREPARATION_MAIN = 'f82e1f6975d2dcabf4687340809af2b33da38493'
PREP_BLOB = 'b4205fcda942178af66e216f94b75ece1df72247'
RECEIPT_BLOB = '0193ba44ea71ada173edf6a3f7afdb2c0a46bedf'
GRANT_BLOB = '717e1f9081915f40fad2e0620c64245a650ca235'
HISTORICAL_BLOB = '95e9f1ff1548221fca31ebba9c6e8d3432e9345d'
SCOPE = 'REUSABLE_WRITER_LEASE_LIFECYCLE_AND_BOUNDED_BRANCH_EXECUTION_ONLY'
ANCHORS = {
    'lifecycle_policy': ('/.pncc-dev/contracts/writer-lease-lifecycle-autonomous-execution-policy.json'.lstrip('/'), '942492b4ffe2c2a8c4369b15b617ad9f7f795643'),
    'claim_admission_policy': ('/.pncc-dev/contracts/writer-lease-claim-admission-policy.json'.lstrip('/'), 'bf83539899df5c5a4e660734e861653f1d4cc1ee'),
    'registry_topology': ('/.pncc-dev/contracts/writer-lease-registry-topology.json'.lstrip('/'), '2b9dec3f2b28aadb80ac8edbb09bdc9d453115a1'),
    'selector': ('/.pncc-dev/scripts/select_provider_work_unit.py'.lstrip('/'), '8045a97d5344f058064690cb265b30f88973e2b8'),
    'claim_evaluator': ('/.pncc-dev/scripts/evaluate_writer_lease_claim_admission.py'.lstrip('/'), 'f93eae649008c9b1e19cd12e06b43c108881146a'),
    'lifecycle_evaluator': ('/.pncc-dev/scripts/evaluate_writer_lease_lifecycle.py'.lstrip('/'), 'd50eae850b64fa5f3f3f657a10bdb476ad769ce8'),
    'state_validator': ('/.pncc-dev/scripts/validate_state.py'.lstrip('/'), 'e9a2dc4c3e4dcca903c052066cac6ee448c581e7'),
}


def git_blob(path: Path) -> str:
    return subprocess.check_output(['git', 'hash-object', str(path)], cwd=ROOT, text=True).strip()


class ReusableWriterLeaseBoundedBranchOwnerAuthorizationWu101Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prep = json.loads(PREP.read_text(encoding='utf-8'))
        cls.receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
        cls.grant = json.loads(GRANT.read_text(encoding='utf-8'))
        cls.historical = json.loads(HISTORICAL.read_text(encoding='utf-8'))

    def test_exact_primary_blob_anchors(self):
        self.assertEqual(git_blob(PREP), PREP_BLOB)
        self.assertEqual(git_blob(RECEIPT), RECEIPT_BLOB)
        self.assertEqual(git_blob(GRANT), GRANT_BLOB)
        self.assertEqual(git_blob(HISTORICAL), HISTORICAL_BLOB)

    def test_all_seven_bound_anchors_are_exact(self):
        for key, (path, expected_blob) in ANCHORS.items():
            self.assertEqual(git_blob(ROOT / path), expected_blob, key)
            self.assertEqual(self.grant['bound_anchor_paths'][key], path, key)
            self.assertEqual(self.grant['bound_anchor_blobs'][key], expected_blob, key)
            self.assertEqual(self.receipt['bound_anchors'][key], expected_blob, key)

    def test_owner_authorization_binding_is_exact(self):
        r = self.receipt
        g = self.grant
        self.assertEqual(r['role'], 'REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_OWNER_AUTHORIZATION')
        self.assertEqual(r['authorization_state'], 'AUTHORIZED')
        self.assertEqual(r['authorization_scope'], SCOPE)
        self.assertEqual(r['preparation_main_sha'], PREPARATION_MAIN)
        self.assertEqual(r['prepared_contract_blob_sha'], PREP_BLOB)
        self.assertEqual(g['role'], 'REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORIZED')
        self.assertEqual(g['authorization_state'], 'AUTHORIZED')
        self.assertEqual(g['authorization_scope'], SCOPE)
        self.assertEqual(g['preparation_main_sha'], PREPARATION_MAIN)
        self.assertEqual(g['prepared_contract_blob_sha'], PREP_BLOB)
        self.assertEqual(g['owner_authorization_receipt_blob_sha'], RECEIPT_BLOB)

    def test_only_reusable_lifecycle_and_bounded_branch_authority_is_granted(self):
        g = self.grant
        self.assertIs(g['reusable_authority_granted'], True)
        allowed = [
            'reusable_lease_acquisition_authority',
            'reusable_provider_state_write_authority',
            'reusable_heartbeat_authority',
            'reusable_release_authority',
            'reusable_work_unit_branch_create_authority',
            'reusable_work_unit_branch_update_authority',
            'reusable_pull_request_create_authority',
            'reusable_pull_request_update_authority',
        ]
        self.assertTrue(all(g[key] is True for key in allowed), allowed)
        forbidden = [
            'direct_main_write_authority',
            'runtime_required_work_unit_authority',
            'runtime_action_authority',
            'product_runtime_mutation_authority',
            'autonomous_merge_authority',
            'autonomous_issue_close_authority',
            'adwf_binding_mutation_authority',
            'promotion_release_tag_authority',
            'ruleset_policy_mutation_authority',
            'private_evidence_publication_authority',
            'unrelated_issue_pr_branch_mutation_authority',
            'force_ref_update_authority',
            'silent_lease_steal_authority',
            'reserve_1080_lifecycle_mutation_authority',
            'primary_1081_lifecycle_mutation_authority',
        ]
        self.assertTrue(all(g[key] is False for key in forbidden), forbidden)

    def test_per_transaction_fail_closed_guards_are_mandatory(self):
        g = self.grant
        required_true = [
            'per_transaction_fresh_provider_truth_required',
            'per_transaction_deterministic_work_unit_selection_required',
            'per_transaction_selected_work_unit_must_be_executable',
            'per_transaction_runtime_required_must_be_false',
            'per_transaction_claim_eligible_required_before_new_lease',
            'per_transaction_no_conflicting_active_unexpired_lease_required',
            'per_transaction_exact_holder_work_unit_domain_base_branch_binding_required',
            'all_registry_writes_require_fresh_cas',
            'provider_state_ref_update_force_must_be_false',
            'historical_lease_reuse_forbidden',
            'silent_lease_steal_forbidden',
            'active_lease_generation_must_be_monotonic',
            'heartbeat_requires_exact_owned_active_unexpired_lease',
            'release_requires_exact_owned_active_unexpired_lease',
            'work_unit_branch_must_be_non_main',
            'work_unit_branch_must_match_selected_work_unit',
            'work_unit_branch_base_must_equal_selected_fresh_main',
            'pull_request_head_must_match_work_unit_branch',
            'pull_request_base_must_be_main',
            'unrelated_branch_or_pull_request_mutation_forbidden',
        ]
        for key in required_true:
            self.assertIs(g[key], True, key)
        self.assertEqual(g['registry_cas_tokens'], ['EXPECTED_REGISTRY_BLOB_SHA', 'OBSERVED_STATE_BRANCH_HEAD_SHA'])
        self.assertEqual(g['anchor_drift_behavior'], 'BLOCK_FAIL_CLOSED')
        self.assertEqual(g['revocation_behavior'], 'BLOCK_FAIL_CLOSED')

    def test_historical_wu098_grant_is_explicitly_non_reusable(self):
        g = self.grant
        self.assertEqual(self.historical['work_unit_id'], 'PIPE-WU-098')
        self.assertEqual(g['historical_work_unit_scoped_grant_blob_sha'], HISTORICAL_BLOB)
        self.assertEqual(g['historical_work_unit_scoped_grant_work_unit_id'], 'PIPE-WU-098')
        self.assertIs(g['historical_work_unit_scoped_grant_reuse_forbidden'], True)

    def test_preparation_remains_historical_default_deny(self):
        p = self.prep
        self.assertEqual(p['preparation_state'], 'WAITING_EXPLICIT_OWNER_AUTHORIZATION')
        self.assertIs(p['owner_authorization_present'], False)
        self.assertIs(p['owner_authorization_binding_complete'], False)
        self.assertIs(p['reusable_authority_granted'], False)
        self.assertIs(p['reusable_lease_acquisition_authority'], False)
        self.assertIs(p['reusable_provider_state_write_authority'], False)
        self.assertIs(p['reusable_work_unit_branch_create_authority'], False)
        self.assertIs(p['reusable_pull_request_create_authority'], False)

    def test_wu101_one_time_transition_is_bounded_and_does_not_close_issue(self):
        t = self.receipt['current_wu101_one_time_transition']
        self.assertEqual(t['work_unit_id'], 'PIPE-WU-101')
        self.assertEqual(t['issue_number'], 244)
        self.assertEqual(t['existing_pr_number'], 246)
        self.assertEqual(t['existing_branch'], 'agent/PIPE-WU-101-reusable-merge-close-executor-integration')
        self.assertIs(t['marker_update_authorized_after_authorization_merge'], True)
        self.assertEqual(t['marker_from_state'], 'BLOCKED')
        self.assertEqual(t['marker_from_base'], 'a05b2b1527e12ba5857ed104c275cb2bcfde06a6')
        self.assertEqual(t['marker_to_state'], 'ACTIVE')
        self.assertEqual(t['marker_to_base_policy'], 'EXACT_AUTHORIZATION_MERGE_MAIN')
        self.assertIs(t['issue_close_authorized_by_this_transition'], False)
        self.assertIs(t['non_force_existing_branch_reconciliation_authorized_after_fresh_selection_and_lease'], True)
        self.assertIs(t['single_replacement_branch_and_pr_authorized_if_safe_non_force_reconciliation_impossible'], True)
        self.assertIs(t['bounded_wu101_diff_must_be_preserved'], True)
        self.assertIs(t['after_exact_head_full_green_exact_wu101_lease_release_authorized'], True)
        self.assertIs(t['subsequent_merge_close_uses_separate_wu100_grant_only'], True)


if __name__ == '__main__':
    unittest.main()
