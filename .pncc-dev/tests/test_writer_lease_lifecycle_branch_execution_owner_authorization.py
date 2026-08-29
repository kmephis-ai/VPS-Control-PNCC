from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[2]
RECEIPT=ROOT/'.pncc-dev/attestations/writer-lease-lifecycle-branch-execution-owner-authorization.json'
GRANT=ROOT/'.pncc-dev/contracts/writer-lease-lifecycle-branch-execution-authorized.json'
PREP=ROOT/'.pncc-dev/contracts/writer-lease-lifecycle-branch-execution-authority-preparation.json'

class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.r=json.loads(RECEIPT.read_text(encoding='utf-8'))
        self.g=json.loads(GRANT.read_text(encoding='utf-8'))
        self.p=json.loads(PREP.read_text(encoding='utf-8'))
    def test_exact_binding(self):
        self.assertEqual(self.r['authorization_scope'],'WRITER_LEASE_LIFECYCLE_AND_BOUNDED_BRANCH_EXECUTION_ONLY')
        self.assertEqual(self.r['preparation_main_sha'],'0a5d119d3de2c1d039d3bdfa5f97d4f3821a3e23')
        self.assertEqual(self.r['prepared_contract_blob_sha'],'31245bb0917c57e921994b3ffb37d74758c93fc3')
        self.assertEqual(self.g['preparation_main_sha'],self.r['preparation_main_sha'])
        self.assertEqual(self.g['prepared_contract_blob_sha'],self.r['prepared_contract_blob_sha'])
        self.assertEqual(self.p['future_authorization_scope'],self.r['authorization_scope'])
    def test_only_bounded_grants_true(self):
        allowed=['lease_acquisition_authority','provider_state_write_authority','heartbeat_authority','release_authority','work_unit_branch_create_authority','work_unit_branch_update_authority','pull_request_create_authority','pull_request_update_authority']
        self.assertTrue(all(self.g[k] is True for k in allowed))
        forbidden=['direct_main_write_authority','autonomous_merge_authority','autonomous_issue_close_authority','lease_steal_authority','force_ref_update_authority','runtime_action_authority','adwf_binding_mutation_authority','promotion_release_tag_authority','ruleset_policy_mutation_authority','private_evidence_publication_authority','reserve_1080_lifecycle_mutation_authority','primary_1081_lifecycle_mutation_authority']
        self.assertTrue(all(self.g[k] is False for k in forbidden))
    def test_execution_guards_are_mandatory(self):
        for k in ['fresh_provider_truth_required','deterministic_work_unit_selection_required','claim_eligible_required_before_new_lease','no_conflicting_active_unexpired_lease_required','owned_active_unexpired_lease_required_for_heartbeat_release','exact_holder_work_unit_domain_base_branch_binding_required','work_unit_branch_must_be_non_main','pr_head_must_match_work_unit_branch']:
            self.assertIs(self.g[k],True,k)
        self.assertEqual(self.g['registry_cas_tokens'],['EXPECTED_REGISTRY_BLOB_SHA','OBSERVED_STATE_BRANCH_HEAD_SHA'])
        self.assertEqual(self.g['authorization_state'],'AUTHORIZED_PENDING_EXECUTION')
    def test_preparation_remains_historical_default_deny(self):
        self.assertIs(self.p['owner_authorization_present'],False)
        self.assertIs(self.p['owner_authorization_binding_complete'],False)
        for k in ['heartbeat_authority','release_authority','lease_acquisition_authority','provider_state_write_authority','work_unit_branch_create_authority','work_unit_branch_update_authority','pull_request_create_authority','pull_request_update_authority','direct_main_write_authority','autonomous_merge_authority','autonomous_issue_close_authority']:
            self.assertIs(self.p[k],False,k)

if __name__=='__main__': unittest.main()
