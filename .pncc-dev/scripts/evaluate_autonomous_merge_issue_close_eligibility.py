#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

POLICY_PATH = Path('.pncc-dev/contracts/autonomous-merge-issue-close-eligibility-policy.json')


def _require_bool(obj, key, errors, expected=True):
    if obj.get(key) is not expected:
        errors.append(f'{key} must be {expected}')


def evaluate(snapshot, policy):
    errors = []
    if policy.get('role') != 'AUTONOMOUS_MERGE_ISSUE_CLOSE_ELIGIBILITY_POLICY':
        errors.append('invalid policy role')
    if policy.get('mode') != 'READ_ONLY_ADVISORY':
        errors.append('policy mode must remain READ_ONLY_ADVISORY')

    mutation_authority_fields = [
        'autonomous_merge_authority',
        'autonomous_issue_close_authority',
        'direct_main_write_authority',
        'provider_state_write_authority',
        'lease_acquisition_authority',
        'heartbeat_authority',
        'release_authority',
        'runtime_action_authority',
        'product_runtime_mutation_authority',
        'adwf_binding_mutation_authority',
        'promotion_release_tag_authority',
        'ruleset_policy_mutation_authority',
        'private_evidence_publication_authority',
        'reserve_1080_lifecycle_mutation_authority',
        'primary_1081_lifecycle_mutation_authority',
    ]
    for field in mutation_authority_fields:
        if policy.get(field) is not False:
            errors.append(f'{field} must remain false in design-only policy')

    required = [
        'provider_truth_fresh', 'selected_work_unit', 'work_unit_active',
        'runtime_not_required', 'current_main_matches_work_unit_base',
        'pr_base_matches_current_main', 'pr_head_matches_selected_head',
        'pr_open', 'pr_mergeable', 'current_head_full_ci_success',
        'no_pending_checks', 'bounded_execution_receipt_valid',
        'released_writer_lease_exact', 'provider_state_release_head_exact',
        'registry_release_blob_exact', 'provider_state_unchanged_since_release',
        'head_unchanged_since_ci', 'no_protected_surface_violation',
    ]
    for key in required:
        _require_bool(snapshot, key, errors)

    explicit_merge_authority = snapshot.get('explicit_merge_authority') is True
    merge_completed = snapshot.get('merge_completed') is True

    if not errors and explicit_merge_authority and not merge_completed:
        return {'decision': 'MERGE_ELIGIBLE', 'reasons': []}

    if merge_completed:
        close_errors = list(errors)
        _require_bool(snapshot, 'actual_merge_sha_readback', close_errors)
        _require_bool(snapshot, 'current_main_equals_actual_merge_sha', close_errors)
        _require_bool(snapshot, 'exact_work_unit_issue', close_errors)
        if snapshot.get('explicit_issue_close_authority') is not True:
            close_errors.append('explicit_issue_close_authority must be true')
        if not close_errors:
            return {'decision': 'CLOSE_ELIGIBLE', 'reasons': []}
        return {'decision': 'BLOCKED', 'reasons': close_errors}

    if not explicit_merge_authority:
        errors.append('explicit_merge_authority must be true')
    return {'decision': 'BLOCKED', 'reasons': errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--policy', default=str(POLICY_PATH))
    args = parser.parse_args()
    policy = json.loads(Path(args.policy).read_text(encoding='utf-8'))
    snapshot = json.loads(Path(args.input).read_text(encoding='utf-8'))
    result = evaluate(snapshot, policy)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['decision'] != 'BLOCKED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
