#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

DEFAULT_CONTRACT = Path('.pncc-dev/contracts/reusable-autonomous-merge-close-authority-preparation.json')

FORBIDDEN_AUTHORITY_FIELDS = [
    'reusable_authority_granted',
    'reusable_autonomous_merge_authority',
    'reusable_autonomous_issue_close_authority',
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
    'force_ref_update_authority',
    'silent_lease_steal_authority',
]

REQUIRED_TRUE_FIELDS = [
    'per_transaction_fresh_provider_truth_required',
    'per_transaction_deterministic_work_unit_selection_required',
    'per_transaction_runtime_required_must_be_false',
    'per_transaction_exact_non_main_work_unit_branch_required',
    'per_transaction_exact_released_writer_lease_required',
    'per_transaction_exact_pr_base_and_head_required',
    'per_transaction_current_head_full_ci_success_required',
    'per_transaction_no_pending_checks_required',
    'per_transaction_no_provider_state_drift_after_release_required',
    'per_transaction_no_head_drift_after_ci_required',
    'per_transaction_no_protected_surface_violation_required',
    'per_transaction_merge_eligible_decision_required',
    'post_merge_fresh_readback_required',
    'post_merge_current_main_must_equal_actual_merge_sha',
    'per_transaction_close_eligible_decision_required',
    'unrelated_pr_or_issue_mutation_forbidden',
]


def validate(contract, root=Path('.'), check_git_blob=True):
    errors = []
    expected = {
        'role': 'REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY_PREPARATION',
        'preparation_state': 'WAITING_EXPLICIT_OWNER_AUTHORIZATION',
        'future_scope': 'REUSABLE_BOUNDED_AUTONOMOUS_MERGE_CLOSE_ONLY',
        'preparation_main_sha': '86bca8694f8663d5d116b8f66f39d25434b1a0f0',
        'eligibility_policy_blob_sha': '8999f027e47e2b6da04f30a12ae9414cb3b7d05c',
        'eligibility_policy_role': 'AUTONOMOUS_MERGE_ISSUE_CLOSE_ELIGIBILITY_POLICY',
        'eligibility_policy_mode': 'READ_ONLY_ADVISORY',
        'merge_operation_policy': 'PINNED_EXPECTED_HEAD_PR_MERGE_ONLY',
        'merge_target_policy': 'EXACT_SELECTED_WORK_UNIT_PR_ONLY',
        'issue_close_policy': 'EXACT_SELECTED_WORK_UNIT_ISSUE_ONLY_AFTER_CLOSE_ELIGIBLE',
        'policy_drift_behavior': 'BLOCK_FAIL_CLOSED',
        'grant_drift_or_revocation_behavior': 'BLOCK_FAIL_CLOSED',
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            errors.append(f'{key} must equal {value}')

    if contract.get('owner_authorization_present') is not False:
        errors.append('owner_authorization_present must remain false')
    if contract.get('owner_authorization_binding_complete') is not False:
        errors.append('owner_authorization_binding_complete must remain false')

    for field in FORBIDDEN_AUTHORITY_FIELDS:
        if contract.get(field) is not False:
            errors.append(f'{field} must remain false in preparation')
    for field in REQUIRED_TRUE_FIELDS:
        if contract.get(field) is not True:
            errors.append(f'{field} must be true')

    policy_path = root / contract.get('eligibility_policy_path', '')
    if not policy_path.is_file():
        errors.append('eligibility policy file missing')
    else:
        policy = json.loads(policy_path.read_text(encoding='utf-8'))
        if policy.get('role') != contract.get('eligibility_policy_role'):
            errors.append('eligibility policy role mismatch')
        if policy.get('mode') != contract.get('eligibility_policy_mode'):
            errors.append('eligibility policy mode mismatch')
        if policy.get('autonomous_merge_authority') is not False or policy.get('autonomous_issue_close_authority') is not False:
            errors.append('eligibility policy must remain advisory with no merge/close grant')

        if check_git_blob:
            try:
                actual = subprocess.check_output(
                    ['git', 'rev-parse', f'HEAD:{contract["eligibility_policy_path"]}'],
                    cwd=root, text=True, stderr=subprocess.STDOUT
                ).strip()
            except Exception as exc:
                errors.append(f'cannot resolve eligibility policy blob: {exc}')
            else:
                if actual != contract.get('eligibility_policy_blob_sha'):
                    errors.append('eligibility policy blob drift')

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--contract', default=str(DEFAULT_CONTRACT))
    parser.add_argument('--no-git-blob-check', action='store_true')
    args = parser.parse_args()
    path = Path(args.contract)
    contract = json.loads(path.read_text(encoding='utf-8'))
    errors = validate(contract, Path('.'), check_git_blob=not args.no_git_blob_check)
    if errors:
        print(json.dumps({'state': 'BLOCKED', 'errors': errors}, sort_keys=True))
        return 2
    print(json.dumps({'state': 'PREPARATION_VALID', 'future_scope': contract['future_scope']}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
