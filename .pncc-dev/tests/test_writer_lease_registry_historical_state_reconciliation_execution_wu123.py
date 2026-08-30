import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.pncc-dev/contracts/writer-lease-registry-historical-state-reconciliation-execution-wu123.json'
GRANT = ROOT / '.pncc-dev/contracts/writer-lease-registry-historical-state-reconciliation-authorized.json'
TRANSITION = ROOT / '.pncc-dev/contracts/governed-frontier-transition-pipe-wu-123.json'
SCOPE = 'EXACT_FOUR_STALE_WRITER_LEASE_STATE_FIELDS_ACTIVE_TO_RELEASED_ONLY'
IDS = [
    '3bf7a003-1e8e-4ab2-910d-0c1d4aba9b03',
    'ee8b93cb-c629-4f69-82c6-25793fd10d8f',
    '38a86545-e9b7-47eb-9b6e-3c9974bbd020',
    '9c2dcb40-26dc-4dce-aa4f-c1be79a66983',
]


def load(path):
    return json.loads(path.read_text())


def validate(e, g, t):
    assert e['evidence_state'] == 'RECORDED'
    assert e['work_unit_id'] == 'PIPE-WU-123'
    assert e['authorization_scope'] == SCOPE
    assert e['authorization_grant']['blob_sha'] == '20fc664e90b1390351a5de70c98563140ef3190d'
    tx = e['historical_reconciliation_transaction']
    assert tx['pre_provider_state_commit_sha'] == '7b48a4701f04b72537f96e60401ed404ef226ea8'
    assert tx['post_provider_state_commit_sha'] == 'c825b7b6b6a84fa2bbf2360b0768eae878c7845a'
    assert tx['pre_registry_blob_sha'] == '2e6ecf0d3c03c4da8bab6bc47ea84ffdc66838ad'
    assert tx['post_registry_blob_sha'] == 'f5b9b45092e46fe3dd2539fcff0187426059233c'
    assert tx['post_readback_provider_state_head_sha'] == tx['post_provider_state_commit_sha']
    assert tx['registry_generation_before'] == tx['registry_generation_after'] == 31
    assert tx['provider_state_commit_count'] == 1
    assert tx['changed_provider_state_files'] == ['.pncc-state/writer-lease-registry.json']
    assert tx['atomic_registry_cas_performed'] is True
    assert tx['fresh_post_transaction_provider_readback_completed'] is True
    assert tx['unknown_provider_outcome'] is False
    assert tx['cas_replay_performed'] is False
    assert [x['lease_id'] for x in e['exact_historical_set']] == IDS
    assert all(x['pre_state'] == 'ACTIVE' and x['post_state'] == 'RELEASED' for x in e['exact_historical_set'])
    for key in ('registry_generation_unchanged','entry_count_unchanged','entry_order_unchanged','immutable_lease_fields_unchanged','unrelated_entries_semantically_identical','current_writer_entry_semantically_identical_during_historical_cas','exact_four_state_fields_only'):
        assert e[key] is True
    for key in ('partial_reconciliation_performed','superset_reconciliation_performed','historical_reactivation_performed','unrelated_provider_state_mutation_performed','higher_autonomy_granted'):
        assert e[key] is False
    assert e['current_writer_lease']['lease_id'] == '184af451-beeb-4447-b729-07799c89e56b'
    assert e['current_writer_lease']['state_during_historical_cas'] == 'ACTIVE'

    assert g['authorization_scope'] == SCOPE
    assert g['historical_reconciliation_provider_state_write_authority'] is True
    assert g['general_provider_state_write_authority'] is False
    assert g['all_four_transitions_in_one_atomic_registry_cas_required'] is True

    # WU-123's successor is immutable in its transition. The repository's live
    # frontier is intentionally advanced by later governed Work Units.
    assert t['work_unit_id'] == 'PIPE-WU-123'
    assert t['predecessor_frontier'] == {
        'state': 'ACTIVE',
        'frontier_id': 'CONTROLLED_WRITER_LEASE_REGISTRY_HISTORICAL_STATE_RECONCILIATION_EXECUTION',
        'blob_sha': '546ad9e256a838ab7c1ab32abbe037d999ea4b69',
    }
    assert t['successor_frontier'] == {
        'state': 'ACTIVE',
        'frontier_id': 'AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_REASSESSMENT_AFTER_LEASE_HYGIENE',
        'blob_sha': '915ccdd52d1a4d742917cd0d1a6f20174af3a34d',
    }
    assert t['execution_evidence']['blob_sha'] == 'b1c3914417ee3d7f12731b6937c11275fe418af8'
    assert t['historical_reconciliation_execution_performed_in_wu123'] is True
    assert t['provider_state_mutation_already_completed_and_evidenced'] is True
    assert t['provider_mutation_authority'] is False
    assert t['higher_autonomy_granted'] is False


class WU123ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.e = load(EVIDENCE)
        self.g = load(GRANT)
        self.t = load(TRANSITION)

    def test_canonical_documents_validate(self):
        validate(self.e, self.g, self.t)

    def test_partial_set_fails(self):
        x = deepcopy(self.e); x['exact_historical_set'] = x['exact_historical_set'][:-1]
        with self.assertRaises(AssertionError): validate(x, self.g, self.t)

    def test_superset_fails(self):
        x = deepcopy(self.e); x['exact_historical_set'].append({'lease_id':'extra','pre_state':'ACTIVE','post_state':'RELEASED'})
        with self.assertRaises(AssertionError): validate(x, self.g, self.t)

    def test_generation_drift_fails(self):
        x = deepcopy(self.e); x['historical_reconciliation_transaction']['registry_generation_after'] = 32
        with self.assertRaises(AssertionError): validate(x, self.g, self.t)

    def test_current_writer_changed_fails(self):
        x = deepcopy(self.e); x['current_writer_entry_semantically_identical_during_historical_cas'] = False
        with self.assertRaises(AssertionError): validate(x, self.g, self.t)

    def test_unknown_outcome_fails(self):
        x = deepcopy(self.e); x['historical_reconciliation_transaction']['unknown_provider_outcome'] = True
        with self.assertRaises(AssertionError): validate(x, self.g, self.t)

    def test_replay_fails(self):
        x = deepcopy(self.e); x['historical_reconciliation_transaction']['cas_replay_performed'] = True
        with self.assertRaises(AssertionError): validate(x, self.g, self.t)

    def test_higher_autonomy_side_effect_fails(self):
        x = deepcopy(self.t); x['higher_autonomy_granted'] = True
        with self.assertRaises(AssertionError): validate(self.e, self.g, x)


if __name__ == '__main__':
    unittest.main()
