#!/usr/bin/env python3
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.pncc-dev/contracts/reusable-autonomous-continuation-executor-first-transaction-wu112.json'
TRANSITION = ROOT / '.pncc-dev/contracts/governed-frontier-transition-pipe-wu-112.json'
GRANT = ROOT / '.pncc-dev/contracts/reusable-autonomous-continuation-executor-authorized.json'
OWNER = ROOT / '.pncc-dev/attestations/reusable-autonomous-continuation-executor-owner-authorization-wu111.json'
WRITER = ROOT / '.pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json'
CONTROL_POLICY = ROOT / '.pncc-dev/contracts/autonomous-continuation-control-loop-policy.json'
CONTROL_EVAL = ROOT / '.pncc-dev/scripts/evaluate_autonomous_continuation_control_loop.py'
ADMISSION_POLICY = ROOT / '.pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json'
ADMISSION_EVAL = ROOT / '.pncc-dev/scripts/evaluate_autonomous_continuation_execution_admission.py'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def blob_sha(path):
    data = path.read_bytes()
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


class ReusableAutonomousContinuationExecutorFirstTransactionWU112(unittest.TestCase):
    def test_executor_and_delegated_authority_anchors_are_exact(self):
        self.assertEqual(blob_sha(GRANT), '2c62780720dace54b220cedd42f77f834886e62a')
        self.assertEqual(blob_sha(OWNER), '143723fee62a2955817e95e4cca48794769a0b46')
        self.assertEqual(blob_sha(WRITER), '717e1f9081915f40fad2e0620c64245a650ca235')
        self.assertEqual(blob_sha(CONTROL_POLICY), '822bcd1833ff4843b6bd176337b3ef3b742275de')
        self.assertEqual(blob_sha(CONTROL_EVAL), '1f794892cfec466505a1a6c38b271492f9759127')
        self.assertEqual(blob_sha(ADMISSION_POLICY), '406d78da6250c452bfc7706b57dc51a18ca48977')
        self.assertEqual(blob_sha(ADMISSION_EVAL), 'cde13515632717b81cef77876e53e9ceef0c46bf')
        g = load(GRANT)
        self.assertTrue(g['reusable_autonomous_continuation_executor_authority'])
        self.assertTrue(g['delegated_existing_authority_execution_authority'])
        self.assertTrue(g['authority_expansion_forbidden'])

    def test_first_transaction_evidence_is_exact_and_single(self):
        e = load(EVIDENCE)
        self.assertEqual(e['role'], 'REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_FIRST_TRANSACTION_EVIDENCE')
        self.assertEqual(e['evidence_state'], 'RECORDED')
        self.assertEqual(e['work_unit_id'], 'PIPE-WU-112')
        self.assertEqual(e['issue_number'], 271)
        self.assertEqual(e['base_main_sha'], '598472b1443c67719cc646cb726c96e8bed4384b')
        self.assertEqual(e['executor_grant_blob_sha'], blob_sha(GRANT))
        self.assertEqual(e['delegated_authority_grant_blob_sha'], blob_sha(WRITER))
        self.assertEqual(e['control_loop_decision'], 'PLAN_EXISTING_WRITER_LEASE_ACQUISITION')
        self.assertEqual(e['execution_admission_decision'], 'ADMIT_EXISTING_WRITER_LEASE_AUTHORITY')
        self.assertEqual(e['delegated_authority_identity'], 'EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY')
        self.assertEqual(e['target_action'], 'WRITER_LEASE_ACQUIRE')
        self.assertEqual(e['executor_transaction_sequence'], 1)
        self.assertEqual(e['executor_transaction_count'], 1)
        self.assertEqual(e['executor_transaction_limit'], 1)
        self.assertTrue(e['fresh_provider_readback_completed'])
        self.assertTrue(e['readback_matches_expected_transaction'])
        self.assertTrue(e['executor_stopped_after_first_transaction_readback'])
        self.assertFalse(e['second_executor_admission_requested'])
        self.assertFalse(e['second_executor_transaction_performed'])

    def test_provider_state_transition_and_lease_binding_are_exact(self):
        e = load(EVIDENCE)
        self.assertEqual(e['provider_state_before'], {
            'state_branch_head_sha': '28b7c812cb567bddd5a305be6d499a7486313b8d',
            'registry_blob_sha': 'df25d7e882548bd0eac58fbe7701a4ab64f7ef9f',
            'registry_generation': 19,
        })
        self.assertEqual(e['provider_state_after'], {
            'state_branch_head_sha': '36b4b06fae5c0217fd718dd8adfe5bfa50d82a6a',
            'registry_blob_sha': 'b85c0f9cfde8d6d034624e608a92bea29ff383ea',
            'registry_generation': 20,
        })
        lease = e['writer_lease_result']
        self.assertEqual(lease['lease_id'], 'c0147eaa-96d4-4f65-96b7-2d17c83b9fa5')
        self.assertEqual(lease['branch'], 'agent/PIPE-WU-112-controlled-first-reusable-autonomous-continuation-transaction')
        self.assertEqual(lease['state'], 'ACTIVE')
        self.assertEqual(lease['generation'], 20)
        self.assertEqual(lease['acquired_at'], '2026-08-30T12:20:48Z')
        self.assertEqual(lease['heartbeat_at'], '2026-08-30T12:20:48Z')
        self.assertEqual(lease['expires_at'], '2026-08-30T13:20:48Z')
        self.assertEqual(e['selected_work_unit']['work_unit_id'], 'PIPE-WU-112')
        self.assertEqual(e['selected_work_unit']['issue_number'], 271)
        self.assertFalse(e['selected_work_unit']['runtime_required'])

    def test_no_authority_broadening_or_forbidden_surface_mutation(self):
        e = load(EVIDENCE)
        self.assertTrue(e['bootstrap_materialization_precedes_work_unit_execution'])
        self.assertFalse(e['bootstrap_materialization_counted_as_executor_transaction'])
        self.assertFalse(e['completion_lifecycle_uses_executor'])
        self.assertTrue(e['completion_lifecycle_may_use_existing_direct_grants_only'])
        for key in (
            'wait_only_path_mutation_authority', 'stop_only_path_mutation_authority',
            'blocked_path_mutation_authority', 'separate_authority_required_path_mutation_authority',
            'product_runtime_mutation_performed', 'runtime_action_performed',
            'adwf_binding_or_repository_mutation_performed', 'release_tag_promotion_performed',
            'ruleset_policy_mutation_performed', 'private_evidence_publication_performed',
            'reserve_1080_lifecycle_mutation_performed', 'primary_1081_lifecycle_mutation_performed',
            'authority_broadening_performed'):
            self.assertFalse(e[key], key)

    def test_historical_transition_records_first_transaction_without_pinning_live_frontier(self):
        t = load(TRANSITION)
        self.assertEqual(t['role'], 'GOVERNED_FRONTIER_TRANSITION')
        self.assertEqual(t['work_unit_id'], 'PIPE-WU-112')
        self.assertEqual(t['issue_number'], 271)
        self.assertEqual(t['base_sha'], '598472b1443c67719cc646cb726c96e8bed4384b')
        self.assertEqual(t['predecessor_frontier']['frontier_id'], 'CONTROLLED_FIRST_REUSABLE_AUTONOMOUS_CONTINUATION_TRANSACTION')
        self.assertEqual(t['predecessor_frontier']['blob_sha'], '5ff880fbf150a0aa89204954a6c795fea4aa147d')
        self.assertEqual(t['successor_frontier']['frontier_id'], 'REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE')
        self.assertEqual(t['successor_frontier']['blob_sha'], 'c85064b96f0a8ffb540d75be28ad647a870ff8a0')
        self.assertEqual(t['provider_truth_observed']['first_transaction_evidence_blob_sha'], blob_sha(EVIDENCE))
        self.assertEqual(t['provider_truth_observed']['first_executor_transaction_count'], 1)


if __name__ == '__main__':
    unittest.main()
