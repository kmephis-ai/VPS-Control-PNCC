#!/usr/bin/env python3
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REQUEST = ROOT / '.pncc-dev/requests/runtime-qualification-v7.0.1.json'
EXPECTED_SCOPES = [
    'WINDOWS_BASELINE',
    'PROCESS_OWNERSHIP_BASELINE',
    'WATCHDOG_LIFECYCLE',
    'PROXIFIER_DESCENDANT_CLEANUP',
    'PRIMARY_AUTO_1081',
    'RESERVE_MANUAL_1080',
    'CREDENTIAL_HOSTKEY',
    'NETWORK_QUALIFICATION',
    'ROLLBACK_IDENTITY',
]
EXPECTED_CANDIDATE = {
    'candidate_id': 'PNCC-V7.0.1-D58023321360',
    'source_sha': 'd5802332136087339482c9b3171c1c5c9c18411e',
    'artifact_filename': 'VPS-Control-v7.0.1.zip',
    'artifact_sha256': '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72',
    'artifact_size_bytes': 701893,
    'provider_artifact_id': 9711822972,
    'provider_artifact_digest': '47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5',
}
EXPECTED_INVARIANTS = {
    'primary_auto_port': 1081,
    'reserve_manual_port': 1080,
    'reserve_manual_lifecycle': 'MANUAL_ONLY',
    'v6_3_1_sha256': '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e',
    'putty_password_argument': '-pwfile',
    'plaintext_pw_allowed': False,
    'hostkey_verification_disable_allowed': False,
}
EXPECTED_PHYSICAL = {
    'work_units': ['PIPE-WU-083', 'PIPE-WU-084'],
    'status': 'PASS',
    'owner_return_bundle_sha256': '236a590120fe8a4e9a32069186b6d03aa06c8cdc6ff037143e76c6d16ead9c84',
    'manifest_entries': 31,
    'powershell_ast_files': 23,
    'functional_consistency_checks': 203,
    'functional_consistency_passed': 203,
    'ui_observed': True,
    'clean_exit': True,
    'ports_1080_1081_unchanged': True,
}
ALLOWED_TOP_LEVEL = {
    'schema_version', 'contract_id', 'request_id', 'origin_work_unit_id',
    'candidate', 'physical_acceptance_prerequisite', 'required_scopes',
    'expected_invariants', 'state', 'runtime_authority', 'promotion_eligible',
    'authority_source', 'runtime_receipt_path',
}

def fail(message):
    print('V701_RUNTIME_REQUEST=BLOCKED')
    print('ERROR=' + message)
    print('RUNTIME_AUTHORITY=false')
    print('PROMOTION_ELIGIBLE=false')
    raise SystemExit(2)

try:
    with REQUEST.open('r', encoding='utf-8-sig') as handle:
        request = json.load(handle)
except Exception as exc:
    fail('load_failed:' + type(exc).__name__)

if set(request) != ALLOWED_TOP_LEVEL:
    fail('top_level_key_set')
if request.get('schema_version') != 1:
    fail('schema_version')
if request.get('contract_id') != 'PNCC_RUNTIME_QUALIFICATION_REQUEST_V1':
    fail('contract_id')
if request.get('request_id') != 'PNCC-RQ-V7.0.1-D58023321360':
    fail('request_id')
if request.get('origin_work_unit_id') != 'PIPE-WU-085':
    fail('origin_work_unit_id')
if request.get('candidate') != EXPECTED_CANDIDATE:
    fail('candidate_identity')
if request.get('physical_acceptance_prerequisite') != EXPECTED_PHYSICAL:
    fail('physical_acceptance_prerequisite')
if request.get('required_scopes') != EXPECTED_SCOPES:
    fail('required_scopes')
if len(set(request['required_scopes'])) != 9:
    fail('required_scope_uniqueness')
if request.get('expected_invariants') != EXPECTED_INVARIANTS:
    fail('expected_invariants')
if request.get('state') != 'RUNTIME_PENDING':
    fail('state_must_be_runtime_pending')
if request.get('runtime_authority') is not False:
    fail('runtime_authority_must_be_false')
if request.get('promotion_eligible') is not False:
    fail('promotion_eligible_must_be_false')
if request.get('authority_source') is not None:
    fail('authority_source_must_be_null')
if request.get('runtime_receipt_path') is not None:
    fail('runtime_receipt_path_must_be_null')

# Explicit non-inheritance guard: old RC14.39 authority may coexist in the repo,
# but this request must never point at or consume it as v7.0.1 authority.
raw = REQUEST.read_text(encoding='utf-8-sig')
for forbidden in (
    'runtime-qualification-rc14.39.json',
    'PNCC-RQ-RC14.39-90C9E8698C64',
    'PNCC-RC14.39-90C9E8698C64',
    '8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3',
):
    if forbidden in raw:
        fail('rc14_39_authority_inheritance:' + forbidden)

print('V701_RUNTIME_REQUEST=PASS')
print('REQUEST_ID=PNCC-RQ-V7.0.1-D58023321360')
print('REQUIRED_SCOPES=9')
print('PHYSICAL_ACCEPTANCE=PASS')
print('STATE=RUNTIME_PENDING')
print('RUNTIME_AUTHORITY=false')
print('PROMOTION_ELIGIBLE=false')
print('RC14_39_AUTHORITY_INHERITED=false')
