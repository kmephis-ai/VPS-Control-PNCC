#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev/contracts/reusable-writer-lease-bounded-branch-authority-preparation.json'


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f'blob {len(data)}\0'.encode('utf-8') + data).hexdigest()


def fail(message: str):
    raise SystemExit(message)


def main():
    c = json.loads(CONTRACT.read_text(encoding='utf-8'))
    if c.get('schema_version') != 1 or c.get('role') != 'REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY_PREPARATION':
        fail('invalid reusable lifecycle preparation identity')
    if c.get('preparation_state') != 'WAITING_EXPLICIT_OWNER_AUTHORIZATION':
        fail('preparation must wait for explicit Owner Authorization')
    if c.get('future_scope') != 'REUSABLE_WRITER_LEASE_LIFECYCLE_AND_BOUNDED_BRANCH_EXECUTION_ONLY':
        fail('unexpected future scope')
    if c.get('state_branch') != 'pncc-provider-state' or c.get('registry_path') != '.pncc-state/writer-lease-registry.json':
        fail('provider-state topology mismatch')

    anchors = [
        ('lifecycle_policy_path', 'lifecycle_policy_blob_sha'),
        ('claim_admission_policy_path', 'claim_admission_policy_blob_sha'),
        ('registry_topology_path', 'registry_topology_blob_sha'),
        ('selector_path', 'selector_blob_sha'),
        ('claim_evaluator_path', 'claim_evaluator_blob_sha'),
        ('lifecycle_evaluator_path', 'lifecycle_evaluator_blob_sha'),
        ('state_validator_path', 'state_validator_blob_sha'),
        ('historical_work_unit_scoped_grant_path', 'historical_work_unit_scoped_grant_blob_sha'),
    ]
    for path_key, sha_key in anchors:
        path = ROOT / c[path_key]
        if not path.is_file():
            fail(f'missing anchor: {c[path_key]}')
        actual = git_blob_sha(path)
        if actual != c[sha_key]:
            fail(f'anchor drift: {c[path_key]} expected={c[sha_key]} actual={actual}')

    historical = json.loads((ROOT / c['historical_work_unit_scoped_grant_path']).read_text(encoding='utf-8'))
    if historical.get('work_unit_id') != 'PIPE-WU-098':
        fail('historical grant identity changed')
    if c.get('historical_work_unit_scoped_grant_work_unit_id') != 'PIPE-WU-098':
        fail('preparation historical grant binding mismatch')
    if c.get('historical_work_unit_scoped_grant_reuse_forbidden') is not True:
        fail('historical WU-098 grant reuse must be forbidden')

    default_deny = [
        'owner_authorization_present', 'owner_authorization_binding_complete', 'reusable_authority_granted',
        'reusable_lease_acquisition_authority', 'reusable_provider_state_write_authority',
        'reusable_heartbeat_authority', 'reusable_release_authority',
        'reusable_work_unit_branch_create_authority', 'reusable_work_unit_branch_update_authority',
        'reusable_pull_request_create_authority', 'reusable_pull_request_update_authority',
        'direct_main_write_authority', 'autonomous_merge_authority', 'autonomous_issue_close_authority',
        'runtime_action_authority', 'product_runtime_mutation_authority', 'adwf_binding_mutation_authority',
        'promotion_release_tag_authority', 'ruleset_policy_mutation_authority',
        'private_evidence_publication_authority', 'reserve_1080_lifecycle_mutation_authority',
        'primary_1081_lifecycle_mutation_authority',
    ]
    for key in default_deny:
        if c.get(key) is not False:
            fail(f'{key} must remain false in preparation')

    mandatory = [
        'generic_continuation_counts_as_authorization',
        'historical_work_unit_scoped_grant_reuse_forbidden',
        'per_transaction_fresh_provider_truth_required',
        'per_transaction_deterministic_work_unit_selection_required',
        'per_transaction_selected_work_unit_must_be_executable',
        'per_transaction_runtime_required_must_be_false',
        'per_transaction_claim_eligible_required',
        'per_transaction_no_conflicting_active_unexpired_lease_required',
        'per_transaction_exact_holder_work_unit_domain_base_branch_binding_required',
        'all_registry_writes_require_fresh_cas', 'force_ref_update_forbidden',
        'silent_lease_steal_forbidden', 'historical_lease_reuse_forbidden',
        'active_lease_generation_must_be_monotonic',
        'heartbeat_requires_exact_owned_active_unexpired_lease',
        'release_requires_exact_owned_active_unexpired_lease',
        'work_unit_branch_must_be_non_main', 'work_unit_branch_must_match_selected_work_unit',
        'work_unit_branch_base_must_equal_selected_fresh_main', 'pull_request_head_must_match_work_unit_branch',
        'pull_request_base_must_be_main', 'unrelated_branch_or_pull_request_mutation_forbidden',
    ]
    if c.get('generic_continuation_counts_as_authorization') is not False:
        fail('generic continuation must not authorize reusable lifecycle authority')
    for key in mandatory[1:]:
        if c.get(key) is not True:
            fail(f'{key} must be true')
    if c.get('registry_cas_tokens') != ['EXPECTED_REGISTRY_BLOB_SHA', 'OBSERVED_STATE_BRANCH_HEAD_SHA']:
        fail('registry CAS tokens mismatch')
    if c.get('anchor_drift_or_revocation_behavior') != 'BLOCK_FAIL_CLOSED':
        fail('anchor drift behavior must fail closed')
    print('REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY_PREPARATION=PASS')


if __name__ == '__main__':
    main()
