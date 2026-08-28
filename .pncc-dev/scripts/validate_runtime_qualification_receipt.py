#!/usr/bin/env python3
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
receipt_path = ROOT / '.pncc-dev/attestations/runtime-qualification-rc14.39.json'
request_path = ROOT / '.pncc-dev/requests/runtime-qualification-rc14.39.json'
policy_path = ROOT / '.pncc-dev/contracts/runtime-qualification-policy.json'

required_scopes = [
    'WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','WATCHDOG_LIFECYCLE',
    'PROXIFIER_DESCENDANT_CLEANUP','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080',
    'CREDENTIAL_HOSTKEY','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY'
]
allowed_keys = {
    'schema_version','contract_id','request_id','candidate_id','source_sha',
    'artifact_filename','artifact_sha256','artifact_size_bytes','source_plane',
    'qualification_contract_id','qualification_state','required_scope_count',
    'pass_scope_count','scopes','reserve_1080_listening','primary_1081_listening',
    'reserve_1080_mutation','runtime_authority','promotion_eligible',
    'final_result_sha256','sanitization','admission_source'
}

def load(path):
    with path.open('r', encoding='utf-8-sig') as f:
        return json.load(f)

def fail(msg):
    print('RUNTIME_RECEIPT_STATE=BLOCKED')
    print('ERROR=' + msg)
    print('RUNTIME_AUTHORITY=false')
    print('PROMOTION_ELIGIBLE=false')
    raise SystemExit(2)

try:
    r, q, p = load(receipt_path), load(request_path), load(policy_path)
except Exception as e:
    fail('load_failed:' + type(e).__name__)

if set(r) != allowed_keys: fail('receipt_key_set')
if r.get('schema_version') != 1: fail('schema_version')
if r.get('contract_id') != 'PNCC_SANITIZED_RUNTIME_QUALIFICATION_RECEIPT_V1': fail('receipt_contract')
if r.get('qualification_contract_id') != p.get('result_contract_id'): fail('qualification_contract')
if r.get('source_plane') != p.get('trusted_result_source_plane'): fail('source_plane')
if r.get('request_id') != q.get('request_id'): fail('request_id')
for key in ('candidate_id','source_sha','artifact_filename','artifact_sha256','artifact_size_bytes'):
    if r.get(key) != q['candidate'].get(key): fail('candidate_identity_' + key)
if r.get('qualification_state') != 'PASS': fail('qualification_state')
if r.get('required_scope_count') != 9 or r.get('pass_scope_count') != 9: fail('scope_count')
scopes = r.get('scopes')
if not isinstance(scopes, dict) or set(scopes) != set(required_scopes): fail('scope_set')
if any(scopes[s] != 'PASS' for s in required_scopes): fail('scope_result')
if not r.get('reserve_1080_listening') or not r.get('primary_1081_listening'): fail('listener_observation')
if r.get('reserve_1080_mutation') is not False: fail('reserve_mutation')
if r.get('runtime_authority') is not True or r.get('promotion_eligible') is not True: fail('authority')
if not re.fullmatch(r'[0-9a-f]{64}', str(r.get('final_result_sha256',''))): fail('result_hash')
if r.get('sanitization') != 'NO_PRIVATE_PATHS_PIDS_HOST_IDS_IPS_CREDENTIALS_OR_RAW_LOGS': fail('sanitization_marker')
if r.get('admission_source') != 'OWNER_RETURN_BUNDLE_RECONCILED_BY_CONTROL_PLANE': fail('admission_source')
print('RUNTIME_RECEIPT_STATE=ADMITTED')
print('PASS_SCOPES=9')
print('RUNTIME_AUTHORITY=true')
print('PROMOTION_ELIGIBLE=true')
print('HOSTED_CI_RUNTIME_SOURCE=false')
