import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSESSMENT = ROOT / '.pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-reassessment-wu124.json'
RUBRIC = ROOT / '.pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-rubric.json'
WU119 = ROOT / '.pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-assessment-wu119.json'
WU120 = ROOT / '.pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-decision-wu120.json'
WU123 = ROOT / '.pncc-dev/contracts/writer-lease-registry-historical-state-reconciliation-execution-wu123.json'
TRANSITION = ROOT / '.pncc-dev/contracts/governed-frontier-transition-pipe-wu-124.json'

EXPECTED_CRITERIA = {
    'PROVIDER_TRUTH_FRESH',
    'BOUNDED_SINGLE_TRANSACTION',
    'POST_TRANSACTION_READBACK',
    'EXACT_HEAD_CI_CLASSIFICATION',
    'CLEAN_MULTI_SESSION_RESUME',
    'PROVIDER_READBACK_PENDING',
    'UNKNOWN_TRANSACTION_OUTCOME',
    'CLASSIFIED_FAILURE',
    'EXPIRED_ACTIVE_LEASE_HISTORY',
    'STALE_LEASE_HYGIENE_REMEDIATION',
    'RUNTIME_NODE_UNAVAILABLE',
    'PHYSICAL_RUNTIME_OR_PRODUCT_MUTATION',
    'RELEASE_TAG_RULESET_SECURITY_ADWF',
}


def load(path):
    return json.loads(path.read_text())


def validate(a, r, old_a, old_d, execution, t):
    assert r['mode'] == 'ASSESSMENT_ONLY_FAIL_CLOSED'
    assert r['principles']['assessment_success_never_grants_authority'] is True
    assert a['assessment_state'] == 'COMPLETE_READY_WITH_EXISTING_AUTHORITY_ONLY'
    assert a['readiness_verdict'] == 'READY_WITH_EXISTING_AUTHORITY_ONLY'
    assert a['decision_boundary_ready'] is True
    assert a['authority_granted'] is False
    assert a['higher_autonomy_authorized'] is False
    assert a['work_unit']['work_unit_id'] == 'PIPE-WU-124'
    assert a['work_unit']['base_sha'] == '74706de37286567eaf689337707666ca187e81c3'
    assert a['rubric_input']['blob_sha'] == '8a75facb79773cadd786fd4384324ba984896ee7'
    assert a['pre_hygiene_assessment']['blob_sha'] == 'ad147299e65cec74f3fc5ef0365376f50f1485aa'
    assert a['pre_hygiene_decision']['blob_sha'] == 'a014f81efa52671bf3f637f7a16dc6332a70091b'
    assert a['post_hygiene_execution']['blob_sha'] == 'b1c3914417ee3d7f12731b6937c11275fe418af8'
    assert old_a['readiness_verdict'] == 'NOT_READY_FOR_HIGHER_AUTONOMY'
    assert len(old_a['stale_active_history']) == 4
    assert old_d['decision_outcome'] == 'DEFER_AND_REMEDIATE'
    assert old_d['decision_constraints']['higher_autonomy_must_be_reassessed_after_reconciliation'] is True
    assert execution['historical_reconciliation_transaction']['atomic_registry_cas_performed'] is True
    assert execution['historical_reconciliation_transaction']['cas_replay_performed'] is False

    p = a['provider_snapshot']
    assert p['state_branch_head_sha'] == '025420c99dc3feec3af37e71b5aa3513de695ea7'
    assert p['registry_blob_sha'] == '29eff68e8aaef1d1f5265cdbaa6deaecf47c10a9'
    assert p['registry_generation'] == 32
    current = a['current_writer']
    assert current['lease_id'] == 'b98a246b-d009-4a64-a798-668feb679ebd'
    assert current['work_unit_id'] == 'PIPE-WU-124'
    assert current['generation'] == 32
    assert current['state'] == 'ACTIVE'
    assert current['current_ownership_eligible'] is True

    h = a['historical_hygiene_recomputation']
    assert h['stale_active_history_count'] == 0
    assert h['expired_active_history_count'] == 0
    assert len(h['prior_blocking_lease_ids']) == 4
    assert h['prior_blocking_lease_states'] == ['RELEASED'] * 4
    assert h['wu123_writer_lease_state'] == 'RELEASED'
    assert h['only_active_entry_is_current_wu124_writer'] is True
    assert h['stale_active_history_blocker_removed'] is True
    assert h['provider_truth_contradictory'] is False

    criteria = {x['id']: x for x in a['criterion_results']}
    assert set(criteria) == EXPECTED_CRITERIA
    for cid in ('PROVIDER_TRUTH_FRESH','BOUNDED_SINGLE_TRANSACTION','POST_TRANSACTION_READBACK','EXACT_HEAD_CI_CLASSIFICATION','CLEAN_MULTI_SESSION_RESUME'):
        assert criteria[cid]['status'] == 'PASS'
    assert criteria['EXPIRED_ACTIVE_LEASE_HISTORY']['status'] == 'BLOCKER_REMOVED'
    assert criteria['STALE_LEASE_HYGIENE_REMEDIATION']['status'] == 'SATISFIED_BY_WU121_WU122_WU123'
    for cid in ('PROVIDER_READBACK_PENDING','UNKNOWN_TRANSACTION_OUTCOME','CLASSIFIED_FAILURE','RUNTIME_NODE_UNAVAILABLE','PHYSICAL_RUNTIME_OR_PRODUCT_MUTATION','RELEASE_TAG_RULESET_SECURITY_ADWF'):
        assert criteria[cid]['status'] == 'BOUNDARY_PRESERVED'

    assert a['residual_blockers'] == []
    assert a['readiness_reasoning']['all_autonomous_safe_criteria_satisfied'] is True
    assert a['readiness_reasoning']['prior_stale_history_blocker_removed'] is True
    assert a['readiness_reasoning']['intentional_owner_and_wait_stop_boundaries_preserved'] is True
    assert a['readiness_reasoning']['contradictory_provider_truth'] is False
    assert a['readiness_reasoning']['readiness_is_not_authority'] is True
    assert all(v is False for v in a['assessment_output_authority'].values())

    assert t['work_unit_id'] == 'PIPE-WU-124'
    assert t['predecessor_frontier']['blob_sha'] == '915ccdd52d1a4d742917cd0d1a6f20174af3a34d'
    assert t['successor_frontier']['blob_sha'] == '15b4985175af740ac1e7f2234b0bd94a59c891a3'
    assert t['reassessment']['blob_sha'] == 'b63c89ef5b1cd785bbbab934a3ab87cb45e5245a'
    assert t['assessment_ready_with_existing_authority_only'] is True
    assert t['assessment_authority_granted'] is False
    assert t['provider_state_mutation_performed_in_wu124'] is False
    assert t['historical_writer_lease_mutation_performed_in_wu124'] is False
    assert t['provider_state_mutation_authority'] is False
    assert t['merge_authority'] is False
    assert t['higher_autonomy_granted'] is False


class WU124ReassessmentTests(unittest.TestCase):
    def setUp(self):
        self.a = load(ASSESSMENT)
        self.r = load(RUBRIC)
        self.old_a = load(WU119)
        self.old_d = load(WU120)
        self.execution = load(WU123)
        self.t = load(TRANSITION)

    def test_canonical_documents_validate(self):
        validate(self.a, self.r, self.old_a, self.old_d, self.execution, self.t)

    def test_stale_history_reappears_fails(self):
        x = deepcopy(self.a); x['historical_hygiene_recomputation']['stale_active_history_count'] = 1
        with self.assertRaises(AssertionError): validate(x, self.r, self.old_a, self.old_d, self.execution, self.t)

    def test_provider_contradiction_fails(self):
        x = deepcopy(self.a); x['historical_hygiene_recomputation']['provider_truth_contradictory'] = True
        with self.assertRaises(AssertionError): validate(x, self.r, self.old_a, self.old_d, self.execution, self.t)

    def test_wrong_current_writer_fails(self):
        x = deepcopy(self.a); x['current_writer']['work_unit_id'] = 'PIPE-WU-X'
        with self.assertRaises(AssertionError): validate(x, self.r, self.old_a, self.old_d, self.execution, self.t)

    def test_authority_grant_fails(self):
        x = deepcopy(self.a); x['authority_granted'] = True
        with self.assertRaises(AssertionError): validate(x, self.r, self.old_a, self.old_d, self.execution, self.t)

    def test_higher_autonomy_authorization_fails(self):
        x = deepcopy(self.a); x['higher_autonomy_authorized'] = True
        with self.assertRaises(AssertionError): validate(x, self.r, self.old_a, self.old_d, self.execution, self.t)

    def test_owner_boundary_weakening_fails(self):
        x = deepcopy(self.a)
        for item in x['criterion_results']:
            if item['id'] == 'PHYSICAL_RUNTIME_OR_PRODUCT_MUTATION': item['status'] = 'PASS'
        with self.assertRaises(AssertionError): validate(x, self.r, self.old_a, self.old_d, self.execution, self.t)

    def test_transition_higher_authority_fails(self):
        x = deepcopy(self.t); x['higher_autonomy_granted'] = True
        with self.assertRaises(AssertionError): validate(self.a, self.r, self.old_a, self.old_d, self.execution, x)


if __name__ == '__main__':
    unittest.main()
