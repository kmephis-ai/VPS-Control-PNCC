#!/usr/bin/env python3
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / '.pncc-dev/contracts/wave6-wu186-installer-build-request-admission-policy.json'
SHA40 = re.compile(r'^[0-9a-f]{40}$')
REQUEST_KEYS = {'schema_version', 'source_main_sha', 'installer_definition', 'compiler_receipt_admission'}
DEF_KEYS = {'path', 'git_blob_sha'}
ADMISSION_KEYS = {'schema_version', 'work_unit', 'decision', 'reason_codes', 'authority'}


def result(value, codes):
    return {
        'schema_version': 1,
        'work_unit': 'PIPE-WU-186',
        'decision': value,
        'reason_codes': list(codes),
        'authority': 'BUILD_REQUEST_ADMISSION_READINESS_ONLY'
    }


def fail(code):
    raise ValueError(code)


def evaluate(request, policy=None):
    try:
        if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
            fail('REQUEST_SHAPE')
        if request.get('schema_version') != 1:
            fail('REQUEST_SCHEMA_VERSION')
        if policy is None:
            policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
        if not isinstance(policy, dict) or policy.get('work_unit_id') != 'PIPE-WU-186':
            fail('POLICY_IDENTITY')

        source = policy.get('source_identity')
        if not isinstance(source, dict) or set(source) != {'repository', 'main_sha'}:
            fail('SOURCE_POLICY_SHAPE')
        expected_main = source.get('main_sha')
        if not isinstance(expected_main, str) or not SHA40.fullmatch(expected_main):
            fail('SOURCE_POLICY_SHA')
        if request.get('source_main_sha') != expected_main:
            fail('SOURCE_MAIN_SHA_MISMATCH')

        expected_def = policy.get('installer_definition')
        if expected_def is None:
            fail('INSTALLER_DEFINITION_NOT_AUTHORIZED')
        if not isinstance(expected_def, dict) or set(expected_def) != DEF_KEYS:
            fail('INSTALLER_DEFINITION_POLICY_SHAPE')
        if not isinstance(expected_def.get('path'), str) or not expected_def['path']:
            fail('INSTALLER_DEFINITION_POLICY_PATH')
        if not isinstance(expected_def.get('git_blob_sha'), str) or not SHA40.fullmatch(expected_def['git_blob_sha']):
            fail('INSTALLER_DEFINITION_POLICY_BLOB')

        definition = request.get('installer_definition')
        if not isinstance(definition, dict) or set(definition) != DEF_KEYS:
            fail('INSTALLER_DEFINITION_REQUEST_SHAPE')
        if definition != expected_def:
            fail('INSTALLER_DEFINITION_IDENTITY_MISMATCH')

        admission = request.get('compiler_receipt_admission')
        if not isinstance(admission, dict) or set(admission) != ADMISSION_KEYS:
            fail('WU185_ADMISSION_SHAPE')
        if admission.get('schema_version') != 1 or admission.get('work_unit') != 'PIPE-WU-185':
            fail('WU185_ADMISSION_IDENTITY')
        if admission.get('authority') != 'RECEIPT_CONSUMER_ADMISSION_ONLY':
            fail('WU185_ADMISSION_AUTHORITY')
        if admission.get('decision') != 'ADMITTED':
            fail('WU185_NOT_ADMITTED')
        if admission.get('reason_codes') != ['WU184_RECEIPT_VERIFIED']:
            fail('WU185_REASON_CODES')

        return result('ADMITTED', ['WU185_RECEIPT_ADMITTED', 'SOURCE_IDENTITY_VERIFIED', 'INSTALLER_DEFINITION_IDENTITY_VERIFIED'])
    except Exception as exc:
        code = str(exc).strip() or exc.__class__.__name__
        return result('BLOCKED', [code])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(json.dumps(result('BLOCKED', ['USAGE']), sort_keys=True, separators=(',', ':')))
        return 2
    try:
        request = json.loads(pathlib.Path(argv[0]).read_text(encoding='utf-8'))
    except Exception as exc:
        code = str(exc).strip() or exc.__class__.__name__
        print(json.dumps(result('BLOCKED', ['INPUT_READ_OR_JSON:' + code]), sort_keys=True, separators=(',', ':')))
        return 1
    decision = evaluate(request)
    print(json.dumps(decision, sort_keys=True, separators=(',', ':')))
    return 0 if decision['decision'] == 'ADMITTED' else 1


if __name__ == '__main__':
    sys.exit(main())
