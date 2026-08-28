#!/usr/bin/env python3
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
decision_path = ROOT / '.pncc-dev/attestations/promotion-decision-rc14.39.json'
receipt_path = ROOT / '.pncc-dev/attestations/runtime-qualification-rc14.39.json'
request_path = ROOT / '.pncc-dev/requests/runtime-qualification-rc14.39.json'
policy_path = ROOT / '.pncc-dev/contracts/runtime-qualification-policy.json'

allowed = {
 'schema_version','contract_id','request_id','candidate_id','source_sha',
 'artifact_filename','artifact_sha256','artifact_size_bytes','runtime_receipt_path',
 'runtime_final_result_sha256','runtime_qualification_state','pass_scope_count',
 'runtime_authority','promotion_eligible','promotion_state','artifact_rebuilt',
 'artifact_substituted','tag_created','release_created','stable_declared',
 'hosted_ci_runtime_source','next_transaction'
}

def load(p):
    with p.open('r', encoding='utf-8-sig') as f: return json.load(f)

def fail(msg):
    print('PROMOTION_DECISION=BLOCKED')
    print('ERROR=' + msg)
    print('CAN_PROMOTE=false')
    print('RELEASE_CREATED=false')
    print('STABLE_DECLARED=false')
    raise SystemExit(2)

try:
    d, r, q, p = load(decision_path), load(receipt_path), load(request_path), load(policy_path)
except Exception as e:
    fail('load_failed:' + type(e).__name__)

if set(d) != allowed: fail('decision_key_set')
if d.get('schema_version') != 1 or d.get('contract_id') != 'PNCC_PROMOTION_DECISION_V1': fail('decision_contract')
if d.get('runtime_receipt_path') != '.pncc-dev/attestations/runtime-qualification-rc14.39.json': fail('receipt_path')
if r.get('contract_id') != 'PNCC_SANITIZED_RUNTIME_QUALIFICATION_RECEIPT_V1': fail('receipt_contract')
if r.get('source_plane') != p.get('trusted_result_source_plane'): fail('runtime_source_plane')
if r.get('qualification_contract_id') != p.get('result_contract_id'): fail('runtime_contract')
if r.get('qualification_state') != 'PASS' or r.get('pass_scope_count') != 9: fail('runtime_not_9_of_9')
if r.get('runtime_authority') is not True or r.get('promotion_eligible') is not True: fail('runtime_authority')
for key in ('request_id','candidate_id','source_sha','artifact_filename','artifact_sha256','artifact_size_bytes'):
    rv = r.get(key)
    if d.get(key) != rv: fail('decision_receipt_identity_' + key)
    if key in q.get('candidate', {}) and rv != q['candidate'][key]: fail('request_identity_' + key)
if d.get('request_id') != q.get('request_id'): fail('request_id')
if d.get('runtime_final_result_sha256') != r.get('final_result_sha256'): fail('runtime_result_hash')
if d.get('runtime_qualification_state') != 'PASS' or d.get('pass_scope_count') != 9: fail('decision_runtime_state')
if d.get('runtime_authority') is not True or d.get('promotion_eligible') is not True: fail('decision_authority')
if d.get('promotion_state') != 'ELIGIBLE_NOT_PROMOTED': fail('promotion_state')
for key in ('artifact_rebuilt','artifact_substituted','tag_created','release_created','stable_declared','hosted_ci_runtime_source'):
    if d.get(key) is not False: fail('forbidden_true_' + key)
if d.get('next_transaction') != 'SEPARATE_GOVERNED_RELEASE_PROMOTION_WORK_UNIT': fail('next_transaction')
print('PROMOTION_DECISION=ELIGIBLE_NOT_PROMOTED')
print('CAN_PROMOTE=true')
print('RUNTIME_VERIFIED=true')
print('PASS_SCOPES=9')
print('ARTIFACT_REBUILT=false')
print('RELEASE_CREATED=false')
print('STABLE_DECLARED=false')
print('HOSTED_CI_RUNTIME_SOURCE=false')
