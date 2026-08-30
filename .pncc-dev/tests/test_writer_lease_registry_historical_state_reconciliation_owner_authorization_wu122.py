import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / '.pncc-dev/attestations/writer-lease-registry-historical-state-reconciliation-owner-authorization-wu122.json'
GRANT = ROOT / '.pncc-dev/contracts/writer-lease-registry-historical-state-reconciliation-authorized.json'
FRONTIER = ROOT / '.pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json'
TRANSITION = ROOT / '.pncc-dev/contracts/governed-frontier-transition-pipe-wu-122.json'
SCOPE = 'EXACT_FOUR_STALE_WRITER_LEASE_STATE_FIELDS_ACTIVE_TO_RELEASED_ONLY'
IDS = [
    '3bf7a003-1e8e-4ab2-910d-0c1d4aba9b03',
    'ee8b93cb-c629-4f69-82c6-25793fd10d8f',
    '38a86545-e9b7-47eb-9b6e-3c9974bbd020',
    '9c2dcb40-26dc-4dce-aa4f-c1be79a66983',
]


def load(path):
    return json.loads(path.read_text())


def validate(receipt, grant, frontier, transition):
    assert receipt['authorization_state'] == 'AUTHORIZED'
    assert receipt['authorization_source'] == 'EXPLICIT_OWNER_AUTHORIZATION_IN_CHAT'
    assert receipt['authorization_scope'] == SCOPE
    assert receipt['preparation_merge_main_sha'] == 'badbcec4ce77195283febf5c853b470255565ba9'
    assert receipt['prepared_contract_blob_sha'] == 'e0104e181a814960e30b1734e82770affbbf923c'
    assert receipt['generic_continuation_text_is_authorization'] is False
    assert receipt['authorization_work_unit_provider_state_mutation_authorized'] is False
    assert [x['lease_id'] for x in receipt['exact_historical_set']] == IDS
    assert all(x['expected_pre_state'] == 'ACTIVE' and x['authorized_post_state'] == 'RELEASED' for x in receipt['exact_historical_set'])

    assert grant['authorization_state'] == 'AUTHORIZED'
    assert grant['authorization_scope'] == SCOPE
    assert grant['owner_authorization_receipt_blob_sha'] == 'f1207b8b78081f107bf1f449066554b6693c922f'
    assert grant['prepared_contract_blob_sha'] == 'e0104e181a814960e30b1734e82770affbbf923c'
    assert grant['execution_policy'] == 'SEPARATE_CONTROLLED_EXECUTION_WORK_UNIT_ONLY'
    assert grant['authorization_work_unit_execution_authority'] is False
    assert grant['historical_reconciliation_authority_granted'] is True
    assert grant['historical_reconciliation_provider_state_write_authority'] is True
    assert grant['general_provider_state_write_authority'] is False
    assert grant['current_writer_lease_lifecycle_authority'] is False
    assert grant['all_four_transitions_in_one_atomic_registry_cas_required'] is True
    assert grant['partial_reconciliation_forbidden'] is True
    assert grant['superset_reconciliation_forbidden'] is True
    assert grant['registry_generation_must_remain_unchanged'] is True
    assert grant['entry_count_must_remain_unchanged'] is True
    assert grant['entry_order_must_remain_unchanged'] is True
    assert [x['lease_id'] for x in grant['exact_historical_set']] == IDS

    assert frontier['frontier_id'] == 'CONTROLLED_WRITER_LEASE_REGISTRY_HISTORICAL_STATE_RECONCILIATION_EXECUTION'
    assert frontier['runtime_required'] is False
    assert frontier['authorization_grant']['blob_sha'] == '20fc664e90b1390351a5de70c98563140ef3190d'
    assert frontier['higher_autonomy_authority'] is False

    assert transition['work_unit_id'] == 'PIPE-WU-122'
    assert transition['predecessor_frontier']['blob_sha'] == 'c3c33fd1504400bf2e48f6bc1024a7ad9a174d2c'
    assert transition['successor_frontier']['blob_sha'] == '546ad9e256a838ab7c1ab32abbe037d999ea4b69'
    assert transition['owner_authorization_receipt']['blob_sha'] == 'f1207b8b78081f107bf1f449066554b6693c922f'
    assert transition['authorized_grant']['blob_sha'] == '20fc664e90b1390351a5de70c98563140ef3190d'
    assert transition['provider_state_mutation_performed_in_wu122'] is False
    assert transition['historical_reconciliation_execution_performed_in_wu122'] is False
    assert transition['higher_autonomy_granted'] is False


class WU122OwnerAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.receipt = load(RECEIPT)
        self.grant = load(GRANT)
        self.frontier = load(FRONTIER)
        self.transition = load(TRANSITION)

    def test_canonical_documents_validate(self):
        validate(self.receipt, self.grant, self.frontier, self.transition)

    def test_generic_continuation_cannot_authorize(self):
        x = deepcopy(self.receipt)
        x['authorization_source'] = 'GENERIC_CONTINUATION_TEXT'
        with self.assertRaises(AssertionError):
            validate(x, self.grant, self.frontier, self.transition)

    def test_scope_broadening_fails(self):
        x = deepcopy(self.grant)
        x['authorization_scope'] = 'GENERAL_PROVIDER_STATE_HYGIENE'
        with self.assertRaises(AssertionError):
            validate(self.receipt, x, self.frontier, self.transition)

    def test_partial_set_fails(self):
        x = deepcopy(self.grant)
        x['exact_historical_set'] = x['exact_historical_set'][:-1]
        with self.assertRaises(AssertionError):
            validate(self.receipt, x, self.frontier, self.transition)

    def test_superset_fails(self):
        x = deepcopy(self.grant)
        x['exact_historical_set'].append({'lease_id':'extra','work_unit_id':'PIPE-WU-X','generation':999,'expected_pre_state':'ACTIVE','authorized_post_state':'RELEASED'})
        with self.assertRaises(AssertionError):
            validate(self.receipt, x, self.frontier, self.transition)

    def test_execution_in_authorization_work_unit_fails(self):
        x = deepcopy(self.grant)
        x['authorization_work_unit_execution_authority'] = True
        with self.assertRaises(AssertionError):
            validate(self.receipt, x, self.frontier, self.transition)

    def test_generation_mutation_authority_fails(self):
        x = deepcopy(self.grant)
        x['registry_generation_must_remain_unchanged'] = False
        with self.assertRaises(AssertionError):
            validate(self.receipt, x, self.frontier, self.transition)


if __name__ == '__main__':
    unittest.main()
