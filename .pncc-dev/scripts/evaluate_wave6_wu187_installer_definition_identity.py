#!/usr/bin/env python3
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / '.pncc-dev/contracts/wave6-wu187-installer-definition-identity-policy.json'
SHA40 = re.compile(r'^[0-9a-f]{40}$')
REQUEST_KEYS = {'schema_version', 'source_main_sha', 'installer_definition_identity', 'semantics'}
IDENTITY_KEYS = {'path', 'git_blob_sha'}
SEMANTIC_KEYS = {
    'windows_10_compatible', 'powershell_51_compatible', 'reserve_1080_mode',
    'reserve_1080_automated_lifecycle', 'primary_1081_mode',
    'primary_1081_authority_expansion', 'v631_sha256', 'embed_secrets_or_passwords',
    'putty_plaintext_pw', 'host_key_verification_fail_closed'
}


def result(decision, reasons):
    return {'schema_version': 1, 'work_unit': 'PIPE-WU-187', 'decision': decision,
            'reason_codes': list(reasons), 'authority': 'INSTALLER_DEFINITION_IDENTITY_PREPARATION_ONLY'}


def fail(code):
    raise ValueError(code)


def evaluate(proposal, policy=None):
    try:
        if not isinstance(proposal, dict) or set(proposal) != REQUEST_KEYS:
            fail('PROPOSAL_SHAPE')
        if proposal.get('schema_version') != 1:
            fail('PROPOSAL_SCHEMA_VERSION')
        if policy is None:
            policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
        if not isinstance(policy, dict) or policy.get('work_unit_id') != 'PIPE-WU-187':
            fail('POLICY_IDENTITY')
        source = policy.get('source_identity')
        if not isinstance(source, dict) or set(source) != {'repository', 'main_sha'}:
            fail('SOURCE_POLICY_SHAPE')
        if proposal.get('source_main_sha') != source.get('main_sha'):
            fail('SOURCE_MAIN_SHA_MISMATCH')
        identity = proposal.get('installer_definition_identity')
        if not isinstance(identity, dict) or set(identity) != IDENTITY_KEYS:
            fail('INSTALLER_DEFINITION_IDENTITY_SHAPE')
        if not isinstance(identity.get('path'), str) or not identity['path'].endswith('.iss'):
            fail('INSTALLER_DEFINITION_PATH')
        if not isinstance(identity.get('git_blob_sha'), str) or not SHA40.fullmatch(identity['git_blob_sha']):
            fail('INSTALLER_DEFINITION_GIT_BLOB_SHA')
        expected_identity = policy.get('installer_definition_identity')
        if expected_identity is None:
            fail('INSTALLER_DEFINITION_IDENTITY_NOT_AUTHORIZED')
        if not isinstance(expected_identity, dict) or set(expected_identity) != IDENTITY_KEYS:
            fail('INSTALLER_DEFINITION_POLICY_SHAPE')
        if identity != expected_identity:
            fail('INSTALLER_DEFINITION_IDENTITY_MISMATCH')
        semantics = proposal.get('semantics')
        required = policy.get('required_semantics')
        if not isinstance(semantics, dict) or set(semantics) != SEMANTIC_KEYS:
            fail('SEMANTICS_SHAPE')
        if not isinstance(required, dict) or set(required) != SEMANTIC_KEYS:
            fail('SEMANTICS_POLICY_SHAPE')
        if semantics != required:
            fail('SEMANTICS_MISMATCH')
        return result('ADMITTED', ['SOURCE_IDENTITY_VERIFIED', 'INSTALLER_DEFINITION_IDENTITY_VERIFIED', 'SAFETY_SEMANTICS_VERIFIED'])
    except Exception as exc:
        return result('BLOCKED', [str(exc).strip() or exc.__class__.__name__])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(json.dumps(result('BLOCKED', ['USAGE']), sort_keys=True, separators=(',', ':')))
        return 2
    try:
        proposal = json.loads(pathlib.Path(argv[0]).read_text(encoding='utf-8'))
    except Exception as exc:
        print(json.dumps(result('BLOCKED', ['INPUT_READ_OR_JSON:' + (str(exc).strip() or exc.__class__.__name__)]), sort_keys=True, separators=(',', ':')))
        return 1
    out = evaluate(proposal)
    print(json.dumps(out, sort_keys=True, separators=(',', ':')))
    return 0 if out['decision'] == 'ADMITTED' else 1


if __name__ == '__main__':
    sys.exit(main())
