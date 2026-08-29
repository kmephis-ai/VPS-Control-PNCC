#!/usr/bin/env python3
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECEIPT = ROOT / '.pncc-dev/attestations/runtime-qualification-v7.0.1.json'
REQUEST = ROOT / '.pncc-dev/requests/runtime-qualification-v7.0.1.json'
POLICY = ROOT / '.pncc-dev/contracts/runtime-qualification-policy.json'

EXPECTED_FINAL_RESULT_SHA = '3ef54c6a7c985ab02e10d7e03cb73a9db931507aa0439dceef38729a8f6bd862'
EXPECTED_PRIVATE_EVIDENCE_SHA = '0a1c3847daa6b13e97adc2c66c37d618d89484340d1bbf33fb88dbcc7cb01163'
EXPECTED_RECEIPT_SHA = '14bd850d8465f1e5de040360a7ee040d9b1224175705c2623c83f10340514456'

REQUIRED_KEYS = {
    'schema_version','contract_id','request_id','candidate_id','source_sha',
    'artifact_filename','artifact_sha256','artifact_size_bytes','source_plane',
    'qualification_contract_id','qualification_state','required_scope_count',
    'pass_scope_count','scopes','reserve_1080_listening','primary_1081_listening',
    'reserve_1080_unchanged','primary_1081_unchanged','runtime_mutation',
    'reserve_1080_mutation','primary_1081_tunnel_mutation',
    'private_result_runtime_authority','runtime_authority_candidate',
    'repository_runtime_authority','promotion_eligible','release_or_tag_authorized',
    'final_result_sha256','private_evidence_bundle_sha256','sanitization','admission_source'
}

def fail(msg):
    print('V701_RUNTIME_RECEIPT_STATE=BLOCKED')
    print('ERROR=' + msg)
    print('RUNTIME_AUTHORITY_CANDIDATE=false')
    print('RUNTIME_AUTHORITY=false')
    print('PROMOTION_ELIGIBLE=false')
    raise SystemExit(2)

def load(path):
    with path.open('r', encoding='utf-8-sig') as fh:
        return json.load(fh)

try:
    receipt_text = RECEIPT.read_text(encoding='utf-8-sig')
    receipt_bytes = RECEIPT.read_bytes()
    receipt = json.loads(receipt_text)
    request = load(REQUEST)
    policy = load(POLICY)
except Exception as exc:
    fail('load_failed:' + type(exc).__name__)

if hashlib.sha256(receipt_bytes).hexdigest() != EXPECTED_RECEIPT_SHA:
    fail('receipt_bytes_sha256')
if set(receipt) != REQUIRED_KEYS:
    fail('receipt_key_set')
if receipt.get('schema_version') != 2:
    fail('schema_version')
if receipt.get('contract_id') != 'PNCC_SANITIZED_RUNTIME_QUALIFICATION_RECEIPT_V2':
    fail('receipt_contract')
if receipt.get('qualification_contract_id') != policy.get('result_contract_id'):
    fail('qualification_contract')
if receipt.get('source_plane') != policy.get('trusted_result_source_plane'):
    fail('source_plane')
if receipt.get('request_id') != request.get('request_id'):
    fail('request_id')

candidate = request.get('candidate', {})
for key in ('candidate_id','source_sha','artifact_filename','artifact_sha256','artifact_size_bytes'):
    if receipt.get(key) != candidate.get(key):
        fail('candidate_identity_' + key)

current = policy.get('current_candidate', {})
for key in ('candidate_id','source_sha','artifact_filename','artifact_sha256','artifact_size_bytes'):
    if candidate.get(key) != current.get(key):
        fail('policy_current_candidate_' + key)

required_scopes = list(policy.get('required_scopes', []))
if len(required_scopes) != 9:
    fail('policy_scope_count')
if request.get('required_scopes') != required_scopes:
    fail('request_scope_order')
if receipt.get('qualification_state') != 'RUNTIME_VERIFIED':
    fail('qualification_state')
if receipt.get('required_scope_count') != 9 or receipt.get('pass_scope_count') != 9:
    fail('scope_count')
scopes = receipt.get('scopes')
if not isinstance(scopes, dict) or list(scopes.keys()) != required_scopes:
    fail('scope_order_or_set')
if any(scopes.get(scope) != 'PASS' for scope in required_scopes):
    fail('scope_result')

for key in ('reserve_1080_listening','primary_1081_listening','reserve_1080_unchanged','primary_1081_unchanged'):
    if receipt.get(key) is not True:
        fail(key)
for key in ('runtime_mutation','reserve_1080_mutation','primary_1081_tunnel_mutation'):
    if receipt.get(key) is not False:
        fail(key)

if receipt.get('private_result_runtime_authority') is not True:
    fail('private_result_runtime_authority')
if receipt.get('runtime_authority_candidate') is not True:
    fail('runtime_authority_candidate')
for key in ('repository_runtime_authority','promotion_eligible','release_or_tag_authorized'):
    if receipt.get(key) is not False:
        fail('forbidden_true_' + key)

if receipt.get('final_result_sha256') != EXPECTED_FINAL_RESULT_SHA:
    fail('final_result_sha256')
if receipt.get('private_evidence_bundle_sha256') != EXPECTED_PRIVATE_EVIDENCE_SHA:
    fail('private_evidence_bundle_sha256')
if receipt.get('sanitization') != 'NO_PRIVATE_PATHS_PIDS_HOST_IDS_IPS_CREDENTIALS_OR_RAW_LOGS':
    fail('sanitization_marker')
if receipt.get('admission_source') != 'OWNER_RETURN_BUNDLE_RECONCILED_BY_CONTROL_PLANE':
    fail('admission_source')

private_markers = (
    r'(?i)yandexdisk|dropbox|localappdata|desktop-|putty_portable\.exe',
    r'(?i)\b[a-z]:\\',
    r'(?<![0-9a-f])(?:\d{1,3}\.){3}\d{1,3}(?![0-9a-f])',
)
for pattern in private_markers:
    if re.search(pattern, receipt_text):
        fail('private_payload_marker')

print('V701_RUNTIME_RECEIPT_STATE=ADMITTED')
print('PASS_SCOPES=9')
print('RUNTIME_AUTHORITY_CANDIDATE=true')
print('RUNTIME_AUTHORITY=false')
print('PROMOTION_ELIGIBLE=false')
print('RELEASE_OR_TAG_AUTHORIZED=false')
print('HOSTED_CI_RUNTIME_SOURCE=false')
