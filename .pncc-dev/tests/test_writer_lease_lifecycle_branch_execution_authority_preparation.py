import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev' / 'contracts' / 'writer-lease-lifecycle-branch-execution-authority-preparation.json'
POLICY = ROOT / '.pncc-dev' / 'contracts' / 'writer-lease-lifecycle-autonomous-execution-policy.json'


class LifecycleBranchAuthorityPreparationTests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads(CONTRACT.read_text(encoding='utf-8'))
        self.p = json.loads(POLICY.read_text(encoding='utf-8'))

    def test_identity_and_exact_source_binding(self):
        self.assertEqual(self.c['role'], 'WRITER_LEASE_LIFECYCLE_BRANCH_EXECUTION_AUTHORITY_PREPARATION')
        self.assertEqual(self.c['preparation_source_main'], 'ee5ef59a38767bfaa42995931aabc483108cdfa3')
        self.assertEqual(self.c['lifecycle_policy_blob_sha'], '942492b4ffe2c2a8c4369b15b617ad9f7f795643')

    def test_preparation_is_default_deny(self):
        authority_fields = [k for k in self.c if k.endswith('_authority')]
        self.assertTrue(authority_fields)
        self.assertTrue(all(self.c[k] is False for k in authority_fields))
        self.assertFalse(self.c['owner_authorization_present'])
        self.assertFalse(self.c['owner_authorization_binding_complete'])

    def test_generic_continuation_never_authorizes(self):
        self.assertFalse(self.c['generic_continuation_counts_as_authorization'])
        self.assertEqual(self.c['preparation_state'], 'WAITING_EXPLICIT_OWNER_AUTHORIZATION')

    def test_future_scope_is_bounded_and_not_merge_authority(self):
        self.assertEqual(self.c['future_authorization_scope'], 'WRITER_LEASE_LIFECYCLE_AND_BOUNDED_BRANCH_EXECUTION_ONLY')
        self.assertFalse(self.c['direct_main_write_authority'])
        self.assertFalse(self.c['autonomous_merge_authority'])
        self.assertFalse(self.c['autonomous_issue_close_authority'])
        self.assertFalse(self.c['force_ref_update_authority'])
        self.assertFalse(self.c['lease_steal_authority'])

    def test_cas_and_exact_bindings_are_mandatory(self):
        self.assertEqual(self.c['registry_cas_tokens'], ['EXPECTED_REGISTRY_BLOB_SHA', 'OBSERVED_STATE_BRANCH_HEAD_SHA'])
        for key in ('fresh_provider_truth_required','selected_work_unit_required','owned_active_unexpired_lease_required_for_lifecycle_or_branch_execution','exact_holder_binding_required','exact_work_unit_binding_required','exact_conflict_domain_binding_required','exact_base_binding_required','exact_branch_binding_required'):
            self.assertTrue(self.c[key], key)

    def test_historical_wu096_lease_is_not_reused(self):
        self.assertTrue(self.c['historical_lease_reuse_forbidden'])
        self.assertTrue(self.c['wu096_lease_heartbeat_or_release_by_preparation_forbidden'])

    def test_existing_lifecycle_policy_remains_read_only(self):
        self.assertEqual(self.p['mode'], 'READ_ONLY_ADVISORY')
        for key in ('autonomous_execution_authority','heartbeat_authority','release_authority','provider_state_write_authority','autonomous_merge_authority','autonomous_issue_close_authority','runtime_action_authority'):
            self.assertFalse(self.p[key], key)

    def test_sensitive_surfaces_remain_denied(self):
        for key in ('runtime_action_authority','adwf_binding_mutation_authority','promotion_release_tag_authority','ruleset_policy_mutation_authority','private_evidence_publication_authority','reserve_1080_lifecycle_mutation_authority','primary_1081_lifecycle_mutation_authority'):
            self.assertFalse(self.c[key], key)


if __name__ == '__main__':
    unittest.main()
