#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev' / 'contracts' / 'writer-lease-lifecycle-branch-execution-authority-preparation.json'
POLICY = ROOT / '.pncc-dev' / 'contracts' / 'writer-lease-lifecycle-autonomous-execution-policy.json'


def main() -> int:
    c = json.loads(CONTRACT.read_text(encoding='utf-8'))
    p = json.loads(POLICY.read_text(encoding='utf-8'))
    expected = {
        'schema_version': 1,
        'role': 'WRITER_LEASE_LIFECYCLE_BRANCH_EXECUTION_AUTHORITY_PREPARATION',
        'preparation_source_main': 'ee5ef59a38767bfaa42995931aabc483108cdfa3',
        'lifecycle_policy_role': 'WRITER_LEASE_LIFECYCLE_AUTONOMOUS_EXECUTION_POLICY',
        'lifecycle_policy_blob_sha': '942492b4ffe2c2a8c4369b15b617ad9f7f795643',
        'state_branch': 'pncc-provider-state',
        'registry_path': '.pncc-state/writer-lease-registry.json',
        'future_authorization_scope': 'WRITER_LEASE_LIFECYCLE_AND_BOUNDED_BRANCH_EXECUTION_ONLY',
        'preparation_state': 'WAITING_EXPLICIT_OWNER_AUTHORIZATION',
        'next_boundary': 'EXPLICIT_OWNER_AUTHORIZATION_BOUND_TO_PREPARATION_MERGE_AND_CONTRACT_BLOB_REQUIRED',
    }
    for key, value in expected.items():
        assert c.get(key) == value, (key, c.get(key), value)
    required_true = (
        'owner_authorization_binding_requires_preparation_merge_sha',
        'owner_authorization_binding_requires_prepared_contract_blob_sha',
        'fresh_provider_truth_required',
        'selected_work_unit_required',
        'claim_eligible_required_before_new_lease',
        'owned_active_unexpired_lease_required_for_lifecycle_or_branch_execution',
        'exact_holder_binding_required',
        'exact_work_unit_binding_required',
        'exact_conflict_domain_binding_required',
        'exact_base_binding_required',
        'exact_branch_binding_required',
        'work_unit_branch_must_be_non_main',
        'work_unit_branch_must_match_selected_work_unit',
        'pr_head_must_match_work_unit_branch',
        'historical_lease_reuse_forbidden',
        'wu096_lease_heartbeat_or_release_by_preparation_forbidden',
    )
    for key in required_true:
        assert c.get(key) is True, key
    assert c.get('registry_cas_tokens') == ['EXPECTED_REGISTRY_BLOB_SHA', 'OBSERVED_STATE_BRANCH_HEAD_SHA']
    required_false = (
        'generic_continuation_counts_as_authorization',
        'owner_authorization_present',
        'owner_authorization_binding_complete',
        'heartbeat_authority',
        'release_authority',
        'lease_acquisition_authority',
        'provider_state_write_authority',
        'work_unit_branch_create_authority',
        'work_unit_branch_update_authority',
        'pull_request_create_authority',
        'pull_request_update_authority',
        'direct_main_write_authority',
        'autonomous_merge_authority',
        'autonomous_issue_close_authority',
        'lease_steal_authority',
        'force_ref_update_authority',
        'runtime_action_authority',
        'adwf_binding_mutation_authority',
        'promotion_release_tag_authority',
        'ruleset_policy_mutation_authority',
        'private_evidence_publication_authority',
        'reserve_1080_lifecycle_mutation_authority',
        'primary_1081_lifecycle_mutation_authority',
    )
    for key in required_false:
        assert c.get(key) is False, key
    assert p.get('role') == c['lifecycle_policy_role']
    assert p.get('mode') == 'READ_ONLY_ADVISORY'
    for key in (
        'autonomous_execution_authority', 'heartbeat_authority', 'release_authority',
        'lease_acquisition_authority', 'provider_state_write_authority',
        'autonomous_merge_authority', 'autonomous_issue_close_authority', 'runtime_action_authority',
        'adwf_binding_mutation_authority', 'promotion_release_tag_authority',
        'ruleset_policy_mutation_authority', 'private_evidence_publication_authority',
        'reserve_1080_lifecycle_mutation_authority', 'primary_1081_lifecycle_mutation_authority',
    ):
        assert p.get(key) is False, ('policy', key)
    print('WU098_AUTHORITY_PREPARATION=PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
