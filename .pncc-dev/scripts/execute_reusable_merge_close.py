#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / '.pncc-dev/contracts/reusable-merge-close-executor-integration.json'


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    hdr = f'blob {len(data)}\0'.encode('utf-8')
    return hashlib.sha1(hdr + data).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_evaluator(path: Path):
    spec = importlib.util.spec_from_file_location('pncc_merge_close_eligibility', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot load eligibility evaluator')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_anchor_map(contract, blob_reader=git_blob_sha):
    anchors = [
        ('authorized_grant_path', 'authorized_grant_blob_sha'),
        ('owner_authorization_receipt_path', 'owner_authorization_receipt_blob_sha'),
        ('preparation_contract_path', 'preparation_contract_blob_sha'),
        ('eligibility_policy_path', 'eligibility_policy_blob_sha'),
        ('eligibility_evaluator_path', 'eligibility_evaluator_blob_sha'),
    ]
    errors = []
    for path_key, sha_key in anchors:
        rel = contract.get(path_key)
        expected = contract.get(sha_key)
        if not rel or not expected:
            errors.append(f'missing anchor {path_key}/{sha_key}')
            continue
        path = ROOT / rel
        if not path.is_file():
            errors.append(f'missing anchor file: {rel}')
            continue
        actual = blob_reader(path)
        if actual != expected:
            errors.append(f'anchor drift: {rel}: expected {expected}, got {actual}')
    return errors


def validate_authority(contract, grant, receipt, preparation, policy):
    errors = []
    if contract.get('role') != 'REUSABLE_MERGE_CLOSE_EXECUTOR_INTEGRATION':
        errors.append('invalid integration contract role')
    if contract.get('mode') != 'PLAN_ONLY_DEFAULT_EXECUTE_EXPLICIT':
        errors.append('invalid integration contract mode')
    if grant.get('role') != 'REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORIZED':
        errors.append('invalid grant role')
    if grant.get('authorization_state') != 'AUTHORIZED':
        errors.append('grant not authorized')
    for key in ['reusable_authority_granted', 'reusable_autonomous_merge_authority', 'reusable_autonomous_issue_close_authority']:
        if grant.get(key) is not True:
            errors.append(f'{key} must be true')
    if receipt.get('role') != 'REUSABLE_AUTONOMOUS_MERGE_CLOSE_OWNER_AUTHORIZATION':
        errors.append('invalid owner authorization receipt role')
    if receipt.get('authorization_state') != 'AUTHORIZED':
        errors.append('owner authorization receipt not authorized')
    if preparation.get('role') != 'REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY_PREPARATION':
        errors.append('invalid preparation role')
    if preparation.get('reusable_authority_granted') is not False:
        errors.append('historical preparation must remain default-deny')
    if policy.get('role') != 'AUTONOMOUS_MERGE_ISSUE_CLOSE_ELIGIBILITY_POLICY':
        errors.append('invalid eligibility policy role')
    if policy.get('mode') != 'READ_ONLY_ADVISORY':
        errors.append('eligibility policy must remain READ_ONLY_ADVISORY')
    if grant.get('prepared_contract_blob_sha') != contract.get('preparation_contract_blob_sha'):
        errors.append('grant/preparation anchor mismatch')
    if grant.get('owner_authorization_receipt_blob_sha') != contract.get('owner_authorization_receipt_blob_sha'):
        errors.append('grant/receipt anchor mismatch')
    if grant.get('eligibility_policy_blob_sha') != contract.get('eligibility_policy_blob_sha'):
        errors.append('grant/policy anchor mismatch')
    forbidden = [
        'direct_main_write_authority', 'runtime_required_work_unit_authority', 'runtime_action_authority',
        'product_runtime_mutation_authority', 'provider_state_write_authority', 'lease_acquisition_authority',
        'heartbeat_authority', 'release_authority', 'adwf_binding_mutation_authority',
        'promotion_release_tag_authority', 'ruleset_policy_mutation_authority',
        'private_evidence_publication_authority', 'unrelated_pr_issue_mutation_authority',
        'force_ref_update_authority', 'silent_lease_steal_authority',
        'reserve_1080_lifecycle_mutation_authority', 'primary_1081_lifecycle_mutation_authority',
    ]
    for key in forbidden:
        if grant.get(key) is not False:
            errors.append(f'forbidden grant authority enabled: {key}')
    return errors


def build_plan(snapshot, contract=None, grant=None, receipt=None, preparation=None, policy=None, evaluator=None, blob_reader=git_blob_sha):
    contract = contract or load_json(CONTRACT_PATH)
    anchor_errors = validate_anchor_map(contract, blob_reader=blob_reader)
    grant = grant or load_json(ROOT / contract['authorized_grant_path'])
    receipt = receipt or load_json(ROOT / contract['owner_authorization_receipt_path'])
    preparation = preparation or load_json(ROOT / contract['preparation_contract_path'])
    policy = policy or load_json(ROOT / contract['eligibility_policy_path'])
    authority_errors = validate_authority(contract, grant, receipt, preparation, policy)
    errors = anchor_errors + authority_errors

    requested_pr = snapshot.get('requested_pr_number')
    selected_pr = snapshot.get('selected_pr_number')
    requested_issue = snapshot.get('requested_issue_number')
    selected_issue = snapshot.get('selected_issue_number')
    if requested_pr != selected_pr:
        errors.append('requested PR is not exact selected PR')
    if requested_issue != selected_issue:
        errors.append('requested Issue is not exact selected Work Unit Issue')
    if snapshot.get('current_main_branch') != contract.get('default_branch'):
        errors.append('current main branch mismatch')
    if not isinstance(selected_pr, int) or selected_pr <= 0:
        errors.append('selected_pr_number must be a positive integer')
    if not isinstance(selected_issue, int) or selected_issue <= 0:
        errors.append('selected_issue_number must be a positive integer')

    if errors:
        return {'decision': 'BLOCKED', 'reasons': errors, 'action': None}

    eval_snapshot = dict(snapshot)
    eval_snapshot['explicit_merge_authority'] = grant['reusable_autonomous_merge_authority'] is True
    eval_snapshot['explicit_issue_close_authority'] = grant['reusable_autonomous_issue_close_authority'] is True
    evaluator = evaluator or load_evaluator(ROOT / contract['eligibility_evaluator_path'])
    result = evaluator.evaluate(eval_snapshot, policy)
    if result.get('decision') == 'MERGE_ELIGIBLE':
        head = snapshot.get('selected_pr_head_sha')
        if not isinstance(head, str) or len(head) != 40:
            return {'decision': 'BLOCKED', 'reasons': ['selected_pr_head_sha must be exact 40-char SHA'], 'action': None}
        return {
            'decision': 'MERGE_ELIGIBLE',
            'reasons': [],
            'action': {
                'type': 'PINNED_EXPECTED_HEAD_PR_MERGE',
                'pr_number': selected_pr,
                'expected_head_sha': head,
            },
        }
    if result.get('decision') == 'CLOSE_ELIGIBLE':
        merge_sha = snapshot.get('actual_merge_sha')
        if not isinstance(merge_sha, str) or len(merge_sha) != 40:
            return {'decision': 'BLOCKED', 'reasons': ['actual_merge_sha must be exact 40-char SHA'], 'action': None}
        return {
            'decision': 'CLOSE_ELIGIBLE',
            'reasons': [],
            'action': {
                'type': 'EXACT_SELECTED_WORK_UNIT_ISSUE_CLOSE',
                'issue_number': selected_issue,
                'actual_merge_sha': merge_sha,
            },
        }
    return {'decision': 'BLOCKED', 'reasons': result.get('reasons', ['eligibility evaluator blocked']), 'action': None}


def _run(cmd, runner=subprocess.run):
    cp = runner(cmd, text=True, capture_output=True)
    if cp.returncode != 0:
        raise RuntimeError(f'command failed: {cmd!r}: {cp.stderr.strip()}')
    return json.loads(cp.stdout or '{}')


def execute_plan(plan, repo, confirmation_token, runner=subprocess.run):
    if confirmation_token != 'EXECUTE_REUSABLE_MERGE_CLOSE_ONLY':
        raise RuntimeError('execute confirmation token mismatch')
    if not isinstance(repo, str) or repo.count('/') != 1:
        raise RuntimeError('repo must be owner/name')
    action = plan.get('action') or {}
    kind = action.get('type')
    if kind == 'PINNED_EXPECTED_HEAD_PR_MERGE' and plan.get('decision') == 'MERGE_ELIGIBLE':
        pr = action['pr_number']
        head = action['expected_head_sha']
        merged = _run(['gh', 'api', '--method', 'PUT', f'repos/{repo}/pulls/{pr}/merge', '-f', f'sha={head}'], runner=runner)
        if merged.get('merged') is not True or not merged.get('sha'):
            raise RuntimeError('GitHub did not confirm merge')
        branch = _run(['gh', 'api', f'repos/{repo}/branches/main'], runner=runner)
        observed = ((branch.get('commit') or {}).get('sha'))
        if observed != merged.get('sha'):
            raise RuntimeError('post-merge main readback mismatch')
        return {'executed': True, 'action': kind, 'merge_sha': observed}
    if kind == 'EXACT_SELECTED_WORK_UNIT_ISSUE_CLOSE' and plan.get('decision') == 'CLOSE_ELIGIBLE':
        issue = action['issue_number']
        closed = _run(['gh', 'api', '--method', 'PATCH', f'repos/{repo}/issues/{issue}', '-f', 'state=closed', '-f', 'state_reason=completed'], runner=runner)
        if closed.get('state') != 'closed':
            raise RuntimeError('GitHub did not confirm Issue close')
        readback = _run(['gh', 'api', f'repos/{repo}/issues/{issue}'], runner=runner)
        if readback.get('state') != 'closed' or readback.get('number') not in (None, issue):
            raise RuntimeError('post-close Issue readback mismatch')
        return {'executed': True, 'action': kind, 'issue_number': issue}
    raise RuntimeError('plan does not contain an allowed executable action')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--contract', default=str(CONTRACT_PATH))
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-token', default='')
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', ''))
    args = parser.parse_args()

    contract = load_json(Path(args.contract))
    snapshot = load_json(Path(args.input))
    plan = build_plan(snapshot, contract=contract)
    if plan['decision'] == 'BLOCKED':
        print(json.dumps(plan, sort_keys=True))
        return 2
    if not args.execute:
        print(json.dumps({'mode': 'PLAN_ONLY', **plan}, sort_keys=True))
        return 0
    result = execute_plan(plan, args.repo, args.confirm_token)
    print(json.dumps({'mode': 'EXECUTE', 'plan': plan, 'result': result}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
