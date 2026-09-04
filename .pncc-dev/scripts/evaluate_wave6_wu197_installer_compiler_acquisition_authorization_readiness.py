#!/usr/bin/env python3
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / '.pncc-dev/contracts/wave6-wu197-installer-compiler-acquisition-authorization-readiness.json'

EXPECTED_TOP = {
    'schema_version', 'work_unit', 'owner_authorization_state',
    'acquisition_authorized', 'one_time_only', 'runner_class',
    'destination_class', 'target'
}
EXPECTED_TARGET = {
    'repository', 'tag', 'release_id', 'asset_id', 'asset_name',
    'size_bytes', 'sha256'
}


def _blocked(*reasons):
    return {
        'schema_version': 1,
        'work_unit': 'PIPE-WU-197',
        'decision': 'BLOCKED',
        'reason_codes': list(reasons) or ['INVALID_INPUT'],
        'acquisition_authorized': False,
        'authority': 'AUTHORIZATION_READINESS_ONLY'
    }


def evaluate(candidate, policy=None):
    if policy is None:
        try:
            policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
        except Exception:
            return _blocked('POLICY_UNREADABLE')
    if not isinstance(candidate, dict) or not isinstance(policy, dict):
        return _blocked('INVALID_INPUT')
    if set(candidate) != EXPECTED_TOP:
        return _blocked('UNEXPECTED_OR_MISSING_FIELDS')
    target = candidate.get('target')
    if not isinstance(target, dict) or set(target) != EXPECTED_TARGET:
        return _blocked('TARGET_SHAPE_MISMATCH')

    state = policy.get('authorization_state')
    boundary = policy.get('future_execution_boundary')
    expected = policy.get('upstream_target')
    authority = policy.get('authority')
    if not all(isinstance(x, dict) for x in (state, boundary, expected, authority)):
        return _blocked('POLICY_SHAPE_INVALID')
    if state != {
        'owner_authorization_state': 'NOT_GRANTED',
        'acquisition_authorized': False,
        'self_grant_allowed': False,
        'force_allowed': False,
        'bypass_allowed': False
    }:
        return _blocked('POLICY_AUTHORIZATION_DRIFT')
    if any(authority.values()):
        return _blocked('POLICY_AUTHORITY_EXPANSION')
    required_boundary = {
        'runner_class': 'GITHUB_HOSTED',
        'one_time_only': True,
        'destination_class': 'EPHEMERAL_WORKSPACE_ONLY',
        'cache_allowed': False,
        'artifact_upload_allowed': False,
        'persistent_storage_allowed': False,
        'install_allowed': False,
        'execute_allowed': False,
        'build_allowed': False,
        'release_allowed': False
    }
    if boundary != required_boundary:
        return _blocked('POLICY_EXECUTION_BOUNDARY_DRIFT')

    expected_candidate = {
        'schema_version': 1,
        'work_unit': 'PIPE-WU-197',
        'owner_authorization_state': 'NOT_GRANTED',
        'acquisition_authorized': False,
        'one_time_only': True,
        'runner_class': 'GITHUB_HOSTED',
        'destination_class': 'EPHEMERAL_WORKSPACE_ONLY',
        'target': expected
    }
    if candidate != expected_candidate:
        reasons = []
        if candidate.get('owner_authorization_state') != 'NOT_GRANTED' or candidate.get('acquisition_authorized') is not False:
            reasons.append('SELF_GRANT_OR_AUTHORIZATION_PRESENT')
        if candidate.get('runner_class') != 'GITHUB_HOSTED':
            reasons.append('RUNNER_CLASS_NOT_ALLOWED')
        if candidate.get('one_time_only') is not True:
            reasons.append('ONE_TIME_CONSTRAINT_MISSING')
        if candidate.get('destination_class') != 'EPHEMERAL_WORKSPACE_ONLY':
            reasons.append('DESTINATION_NOT_EPHEMERAL')
        if target != expected:
            reasons.append('IMMUTABLE_TARGET_IDENTITY_MISMATCH')
        return _blocked(*(reasons or ['CANDIDATE_MISMATCH']))

    return {
        'schema_version': 1,
        'work_unit': 'PIPE-WU-197',
        'decision': 'READY_FOR_OWNER_GRANT',
        'reason_codes': ['EXACT_TARGET_IDENTITY_VERIFIED', 'ONE_TIME_GITHUB_HOSTED_BOUNDARY_VERIFIED', 'OWNER_GRANT_ABSENT'],
        'acquisition_authorized': False,
        'authority': 'AUTHORIZATION_READINESS_ONLY'
    }


if __name__ == '__main__':
    import sys
    try:
        candidate = json.load(sys.stdin)
    except Exception:
        print(json.dumps(_blocked('INPUT_JSON_INVALID'), sort_keys=True))
        raise SystemExit(2)
    result = evaluate(candidate)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['decision'] == 'READY_FOR_OWNER_GRANT' else 2)
