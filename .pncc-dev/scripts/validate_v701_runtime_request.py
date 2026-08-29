#!/usr/bin/env python3
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
REQUEST = ROOT / '.pncc-dev/requests/runtime-qualification-v7.0.1.json'
EXPECTED_FILE_SHA256 = '9aafd2f40203d6a8d45a72cc8de41a85218e8d83524d8eb8ca3c59ae37b0b634'
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
    'artifact_filename': 'VPS-Control-v7.0.1.zip',
    'artifact_sha256': '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72',
    'artifact_size_bytes': 701893,
    'candidate_id': 'PNCC-V7.0.1-D58023321360',
    'provider_artifact_digest': '47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5',
    'provider_artifact_id': 9711822972,
    'provider_build_run_id': 33242642394,
    'source_sha': 'd5802332136087339482c9b3171c1c5c9c18411e',
}
EXPECTED_INVARIANTS = {
    'hostkey_verification_disable_allowed': False,
    'plaintext_pw_allowed': False,
    'primary_auto_port': 1081,
    'putty_password_argument': '-pwfile',
    'reserve_manual_lifecycle': 'MANUAL_ONLY',
    'reserve_manual_port': 1080,
    'v6_3_1_sha256': '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e',
}
EXPECTED_TOP_LEVEL = {
    'candidate', 'contract_id', 'expected_invariants', 'origin_work_unit_id',
    'promotion_eligible', 'request_id', 'required_scopes', 'runtime_authority',
    'schema_version', 'state',
}

def fail(message: str) -> None:
    print('V701_RUNTIME_REQUEST=BLOCKED')
    print('ERROR=' + message)
    print('RUNTIME_AUTHORITY=false')
    print('PROMOTION_ELIGIBLE=false')
    raise SystemExit(2)

raw = REQUEST.read_bytes()
actual_sha = hashlib.sha256(raw).hexdigest()
if actual_sha != EXPECTED_FILE_SHA256:
    fail('provider_request_byte_sha256:' + actual_sha)
try:
    request = json.loads(raw.decode('utf-8-sig'))
except Exception as exc:
    fail('load_failed:' + type(exc).__name__)

if set(request) != EXPECTED_TOP_LEVEL:
    fail('top_level_key_set')
if request.get('schema_version') != 1:
    fail('schema_version')
if request.get('contract_id') != 'PNCC_RUNTIME_QUALIFICATION_REQUEST_V1':
    fail('contract_id')
if request.get('request_id') != 'PNCC-RQ-V7.0.1-D58023321360':
    fail('request_id')
if request.get('origin_work_unit_id') != 'PIPE-WU-082':
    fail('origin_work_unit_id')
if request.get('candidate') != EXPECTED_CANDIDATE:
    fail('candidate_identity')
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

text = raw.decode('utf-8-sig')
for forbidden in (
    'runtime-qualification-rc14.39.json',
    'PNCC-RQ-RC14.39-90C9E8698C64',
    'PNCC-RC14.39-90C9E8698C64',
    '8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3',
):
    if forbidden in text:
        fail('rc14_39_authority_inheritance:' + forbidden)

print('V701_RUNTIME_REQUEST=PASS')
print('REQUEST_FILE_SHA256=' + actual_sha)
print('REQUEST_ID=PNCC-RQ-V7.0.1-D58023321360')
print('PROVIDER_BUILD_RUN_ID=33242642394')
print('REQUIRED_SCOPES=9')
print('STATE=RUNTIME_PENDING')
print('RUNTIME_AUTHORITY=false')
print('PROMOTION_ELIGIBLE=false')
print('RC14_39_AUTHORITY_INHERITED=false')
