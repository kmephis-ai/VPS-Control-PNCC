#!/usr/bin/env python3
import json, pathlib

ROOT=pathlib.Path(__file__).resolve().parents[2]
P=ROOT/'.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.0.json'
EXPECTED_MAIN='b3d75cc353e10b608d58edf1c46104b8a2c39128'
EXPECTED_STABLE='1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599'

def fail(msg):
    print('STABLE_RUNTIME_AUTHORITY_OWNER_GRANT=BLOCKED')
    print('ERROR='+msg)
    print('RUNTIME_AUTHORITY=false')
    print('PROMOTION_ELIGIBLE=false')
    print('RELEASE_OR_TAG_AUTHORIZED=false')
    raise SystemExit(2)

try:
    d=json.load(P.open('r',encoding='utf-8-sig'))
except Exception as e:
    fail('load_failed:'+type(e).__name__)

if d.get('contract_id')!='PNCC_STABLE_RUNTIME_AUTHORITY_OWNER_GRANT_V1': fail('contract')
if d.get('stable_version')!='7.0.0' or d.get('authoritative_main')!=EXPECTED_MAIN: fail('identity')
if d.get('stable_artifact_sha256')!=EXPECTED_STABLE or d.get('stable_artifact_size_bytes')!=700897: fail('artifact_identity')
if d.get('request_id')!='PNCC-RQ-V7.0.0-56F1E3798BE0' or d.get('candidate_id')!='PNCC-V7.0.0-56F1E3798BE0': fail('request_candidate_identity')
if d.get('wu073_state')!='STABLE_NINE_SCOPE_RECONCILE_PASS': fail('wu073_state')
if d.get('wu074_decision_state')!='ELIGIBLE_FOR_OWNER_PROMOTION_DECISION': fail('wu074_state')
if d.get('runtime_authority_candidate') is not True: fail('authority_candidate')
if d.get('owner_authorization_present') is not False or d.get('owner_authorization_binding_complete') is not False: fail('unexpected_owner_authorization')
if d.get('grant_state')!='WAITING_OWNER_AUTHORIZATION': fail('grant_state')
for k in ('runtime_authority','promotion_eligible','release_or_tag_authorized','tag_created','release_created','stable_declared','artifact_rebuilt','artifact_substituted','runtime_mutation'):
    if d.get(k) is not False: fail('forbidden_true_'+k)
if d.get('next_transaction')!='EXPLICIT_OWNER_AUTHORIZATION_REQUIRED': fail('next_transaction')

print('STABLE_RUNTIME_AUTHORITY_OWNER_GRANT=WAITING_OWNER_AUTHORIZATION')
print('RUNTIME_AUTHORITY_CANDIDATE=true')
print('OWNER_AUTHORIZATION_PRESENT=false')
print('RUNTIME_AUTHORITY=false')
print('PROMOTION_ELIGIBLE=false')
print('RELEASE_OR_TAG_AUTHORIZED=false')
