#!/usr/bin/env python3
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / '.pncc-dev/contracts/reusable-autonomous-continuation-executor-authority-preparation.json'
RECEIPT = ROOT / '.pncc-dev/attestations/reusable-autonomous-continuation-executor-owner-authorization-wu111.json'
GRANT = ROOT / '.pncc-dev/contracts/reusable-autonomous-continuation-executor-authorized.json'
TRANSITION = ROOT / '.pncc-dev/contracts/governed-frontier-transition-pipe-wu-111.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def blob_sha(path):
    data = path.read_bytes()
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


class ReusableAutonomousContinuationExecutorOwnerAuthorizationWU111(unittest.TestCase):
    def test_preparation_anchor_is_exact(self):
        self.assertEqual(blob_sha(PREP), '4050c89d6c79d40649d45b983527924f8dcb5901')
        p = load(PREP)
        self.assertEqual(p['future_scope'], 'REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_ONLY')
        self.assertFalse(p['generic_continuation_text_is_owner_authorization'])

    def test_owner_receipt_is_exact_and_bounded(self):
        r = load(RECEIPT)
        self.assertEqual(r['role'], 'REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_OWNER_AUTHORIZATION')
        self.assertEqual(r['authorization_state'], 'AUTHORIZED')
        self.assertEqual(r['authorization_scope'], 'REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_ONLY')
        self.assertEqual(r['authorization_source'], 'EXPLICIT_OWNER_AUTHORIZATION_IN_CHAT')
        self.assertEqual(r['work_unit_id'], 'PIPE-WU-111')
        self.assertEqual(r['issue_number'], 269)
        self.assertEqual(r['preparation_merge_main_sha'], '5b576a797478e6b873083eba01c6ebc9034085f1')
        self.assertEqual(r['prepared_contract_blob_sha'], '4050c89d6c79d40649d45b983527924f8dcb5901')
        self.assertTrue(r['authorized_scope_exact'])
        self.assertTrue(r['reusable_autonomous_continuation_executor_authorized'])
        self.assertTrue(r['delegation_only_to_existing_canonical_grants'])
        self.assertFalse(r['generic_continuation_text_is_authorization'])
        self.assertFalse(r['first_executor_transaction_authorized_in_this_work_unit'])
        self.assertFalse(r['first_executor_transaction_performed_in_this_work_unit'])
        for key in (
            'product_runtime_mutation_authorized','runtime_action_authorized',
            'adwf_binding_or_repository_mutation_authorized','release_tag_promotion_authorized',
            'ruleset_policy_administration_authorized','private_evidence_publication_authorized',
            'reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized',
            'force_ref_update_authorized','silent_lease_steal_authorized'):
            self.assertFalse(r[key], key)

    def test_grant_binds_receipt_preparation_and_existing_authorities(self):
        g = load(GRANT)
        self.assertEqual(g['role'], 'REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_AUTHORIZED')
        self.assertEqual(g['authorization_state'], 'AUTHORIZED')
        self.assertEqual(g['authorization_scope'], 'REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_ONLY')
        self.assertEqual(g['preparation_merge_main_sha'], '5b576a797478e6b873083eba01c6ebc9034085f1')
        self.assertEqual(g['prepared_contract_blob_sha'], blob_sha(PREP))
        self.assertEqual(g['owner_authorization_receipt_blob_sha'], blob_sha(RECEIPT))
        self.assertEqual(blob_sha(RECEIPT), '143723fee62a2955817e95e4cca48794769a0b46')
        self.assertTrue(g['reusable_authority_granted'])
        self.assertTrue(g['reusable_autonomous_continuation_executor_authority'])
        self.assertTrue(g['delegated_existing_authority_execution_authority'])
        self.assertTrue(g['authority_expansion_forbidden'])
        self.assertEqual(g['delegation_policy']['WAIT_ONLY'], 'NO_MUTATION')
        self.assertEqual(g['delegation_policy']['STOP_ONLY'], 'NO_MUTATION')
        self.assertEqual(g['delegation_policy']['BLOCKED'], 'NO_MUTATION_FAIL_CLOSED')
        self.assertEqual(g['delegation_policy']['SEPARATE_AUTHORITY_REQUIRED'], 'NO_MUTATION_AND_SEPARATE_EXPLICIT_AUTHORITY_REQUIRED')
        expected = {
            'admission_policy': '406d78da6250c452bfc7706b57dc51a18ca48977',
            'admission_evaluator': 'cde13515632717b81cef77876e53e9ceef0c46bf',
            'control_loop_policy': '822bcd1833ff4843b6bd176337b3ef3b742275de',
            'control_loop_evaluator': '1f794892cfec466505a1a6c38b271492f9759127',
            'reusable_materialization_grant': '39db0554b86932b1beb4bb7250d040c06f9371ea',
            'reusable_writer_lease_grant': '717e1f9081915f40fad2e0620c64245a650ca235',
            'reusable_merge_close_grant': 'baa503d63eaa437545ddcf0a045cf864d1ef36e6',
            'merge_close_executor_integration': '220668dc1089aaa123085724db005f3eae9971c8',
        }
        self.assertEqual(g['anchor_blobs'], expected)
        for name, rel in g['anchor_paths'].items():
            self.assertEqual(blob_sha(ROOT / rel), expected[name], name)

    def test_grant_has_no_direct_mutation_or_forbidden_surface_authority(self):
        g = load(GRANT)
        keys = [
            'direct_issue_create_authority','direct_issue_update_authority','direct_issue_close_authority',
            'direct_branch_mutation_authority','direct_pull_request_mutation_authority',
            'direct_provider_state_write_authority','direct_writer_lease_mutation_authority',
            'direct_workflow_rerun_authority','direct_merge_authority','runtime_action_authority',
            'product_runtime_mutation_authority','adwf_binding_mutation_authority',
            'adwf_repository_mutation_authority','release_tag_promotion_authority',
            'ruleset_policy_mutation_authority','private_evidence_publication_authority',
            'force_ref_update_authority','silent_lease_steal_authority',
            'reserve_1080_lifecycle_mutation_authority','primary_1081_lifecycle_mutation_authority',
            'authorization_work_unit_first_executor_transaction_authority']
        for key in keys:
            self.assertFalse(g[key], key)

    def test_historical_transition_records_owner_authorization_boundary_without_pinning_live_frontier(self):
        t = load(TRANSITION)
        self.assertEqual(t['work_unit_id'], 'PIPE-WU-111')
        self.assertEqual(t['issue_number'], 269)
        self.assertEqual(t['base_sha'], '5b576a797478e6b873083eba01c6ebc9034085f1')
        self.assertEqual(t['predecessor_frontier']['blob_sha'], '4b223f336e7f2ce16c189b72b3f258141fbafec6')
        self.assertEqual(t['successor_frontier']['frontier_id'], 'CONTROLLED_FIRST_REUSABLE_AUTONOMOUS_CONTINUATION_TRANSACTION')
        self.assertEqual(t['successor_frontier']['blob_sha'], '5ff880fbf150a0aa89204954a6c795fea4aa147d')
        self.assertEqual(t['provider_truth_observed']['owner_authorization_receipt_blob_sha'], blob_sha(RECEIPT))
        self.assertEqual(t['provider_truth_observed']['reusable_executor_grant_blob_sha'], blob_sha(GRANT))


if __name__ == '__main__':
    unittest.main()
