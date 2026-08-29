from pathlib import Path
import hashlib
import json
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev/contracts/reusable-writer-lease-bounded-branch-authority-preparation.json'
VALIDATOR = ROOT / '.pncc-dev/scripts/validate_reusable_writer_lease_bounded_branch_authority_preparation.py'


def git_blob_sha(path):
    data = Path(path).read_bytes()
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


class ReusableLifecyclePreparationTests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads(CONTRACT.read_text(encoding='utf-8'))

    def test_validator_passes_exact_repository_state(self):
        cp = subprocess.run(['python3', str(VALIDATOR)], text=True, capture_output=True)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn('PREPARATION=PASS', cp.stdout)

    def test_exact_anchor_blobs(self):
        pairs = [
            ('lifecycle_policy_path', 'lifecycle_policy_blob_sha'),
            ('claim_admission_policy_path', 'claim_admission_policy_blob_sha'),
            ('registry_topology_path', 'registry_topology_blob_sha'),
            ('selector_path', 'selector_blob_sha'),
            ('claim_evaluator_path', 'claim_evaluator_blob_sha'),
            ('lifecycle_evaluator_path', 'lifecycle_evaluator_blob_sha'),
            ('state_validator_path', 'state_validator_blob_sha'),
            ('historical_work_unit_scoped_grant_path', 'historical_work_unit_scoped_grant_blob_sha'),
        ]
        for path_key, sha_key in pairs:
            self.assertEqual(git_blob_sha(ROOT / self.c[path_key]), self.c[sha_key], path_key)

    def test_preparation_is_default_deny(self):
        false_fields = [k for k in self.c if k.endswith('_authority') or k in {
            'owner_authorization_present', 'owner_authorization_binding_complete', 'reusable_authority_granted'
        }]
        self.assertTrue(false_fields)
        for key in false_fields:
            self.assertIs(self.c[key], False, key)

    def test_old_wu098_grant_is_explicitly_non_reusable(self):
        old = json.loads((ROOT / self.c['historical_work_unit_scoped_grant_path']).read_text(encoding='utf-8'))
        self.assertEqual(old['work_unit_id'], 'PIPE-WU-098')
        self.assertEqual(self.c['historical_work_unit_scoped_grant_work_unit_id'], 'PIPE-WU-098')
        self.assertIs(self.c['historical_work_unit_scoped_grant_reuse_forbidden'], True)

    def test_reusable_scope_excludes_merge_close_and_runtime(self):
        self.assertEqual(self.c['future_scope'], 'REUSABLE_WRITER_LEASE_LIFECYCLE_AND_BOUNDED_BRANCH_EXECUTION_ONLY')
        for key in [
            'direct_main_write_authority', 'autonomous_merge_authority', 'autonomous_issue_close_authority',
            'runtime_action_authority', 'product_runtime_mutation_authority',
            'adwf_binding_mutation_authority', 'promotion_release_tag_authority',
            'ruleset_policy_mutation_authority', 'private_evidence_publication_authority',
            'reserve_1080_lifecycle_mutation_authority', 'primary_1081_lifecycle_mutation_authority',
        ]:
            self.assertIs(self.c[key], False, key)

    def test_per_transaction_fail_closed_guards(self):
        for key in [
            'per_transaction_fresh_provider_truth_required',
            'per_transaction_deterministic_work_unit_selection_required',
            'per_transaction_selected_work_unit_must_be_executable',
            'per_transaction_runtime_required_must_be_false',
            'per_transaction_claim_eligible_required',
            'per_transaction_no_conflicting_active_unexpired_lease_required',
            'per_transaction_exact_holder_work_unit_domain_base_branch_binding_required',
            'all_registry_writes_require_fresh_cas', 'force_ref_update_forbidden',
            'silent_lease_steal_forbidden', 'historical_lease_reuse_forbidden',
            'heartbeat_requires_exact_owned_active_unexpired_lease',
            'release_requires_exact_owned_active_unexpired_lease',
            'work_unit_branch_must_be_non_main', 'work_unit_branch_must_match_selected_work_unit',
            'work_unit_branch_base_must_equal_selected_fresh_main',
            'pull_request_head_must_match_work_unit_branch', 'pull_request_base_must_be_main',
            'unrelated_branch_or_pull_request_mutation_forbidden',
        ]:
            self.assertIs(self.c[key], True, key)
        self.assertEqual(self.c['registry_cas_tokens'], ['EXPECTED_REGISTRY_BLOB_SHA', 'OBSERVED_STATE_BRANCH_HEAD_SHA'])
        self.assertEqual(self.c['anchor_drift_or_revocation_behavior'], 'BLOCK_FAIL_CLOSED')

    def test_generic_continuation_is_not_authorization(self):
        self.assertIs(self.c['generic_continuation_counts_as_authorization'], False)
        self.assertEqual(self.c['preparation_state'], 'WAITING_EXPLICIT_OWNER_AUTHORIZATION')


if __name__ == '__main__':
    unittest.main()
