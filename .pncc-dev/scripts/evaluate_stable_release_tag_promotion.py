#!/usr/bin/env python3
import json, pathlib

ROOT=pathlib.Path(__file__).resolve().parents[2]
P=ROOT/'.pncc-dev/attestations/stable-release-tag-promotion-v7.0.0.json'
EXPECTED_MAIN='30e51b6a2af7b1c9821d23873596abf59c0dc01e'
EXPECTED_STABLE='1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599'

def fail(msg):
    print('STABLE_RELEASE_TAG_PROMOTION=BLOCKED')
    print('ERROR='+msg)
    print('PROMOTION_ELIGIBLE=false')
    print('RELEASE_OR_TAG_AUTHORIZED=false')
    raise SystemExit(2)

try:
    d=json.load(P.open('r',encoding='utf-8-sig'))
except Exception as e:
    fail('load_failed:'+type(e).__name__)

if d.get('contract_id')!='PNCC_STABLE_RELEASE_TAG_PROMOTION_V1': fail('contract')
if d.get('stable_version')!='7.0.0' or d.get('authoritative_main')!=EXPECTED_MAIN: fail('identity')
if d.get('stable_artifact_filename')!='VPS-Control-v7.0.0.zip' or d.get('stable_artifact_sha256')!=EXPECTED_STABLE or d.get('stable_artifact_size_bytes')!=700897: fail('artifact_identity')
if d.get('request_id')!='PNCC-RQ-V7.0.0-56F1E3798BE0' or d.get('candidate_id')!='PNCC-V7.0.0-56F1E3798BE0': fail('request_candidate_identity')
if d.get('wu073_state')!='STABLE_NINE_SCOPE_RECONCILE_PASS': fail('wu073_state')
if d.get('wu074_decision_state')!='ELIGIBLE_FOR_OWNER_PROMOTION_DECISION': fail('wu074_state')
if d.get('wu075_grant_state')!='RUNTIME_AUTHORITY_GRANTED' or d.get('runtime_authority') is not True: fail('runtime_authority_missing')
if d.get('target_tag')!='v7.0.0' or d.get('target_release_name')!='VPS Control PNCC v7.0.0': fail('target_identity')
if d.get('owner_release_authorization_present') is not False or d.get('owner_release_authorization_binding_complete') is not False: fail('unexpected_owner_authorization')
if d.get('promotion_state')!='WAITING_OWNER_AUTHORIZATION': fail('promotion_state')
for k in ('promotion_eligible','release_or_tag_authorized','tag_created','release_created','stable_declared','artifact_rebuilt','artifact_substituted','runtime_mutation','product_bytes_mutated','runtime_bytes_mutated'):
    if d.get(k) is not False: fail('forbidden_true_'+k)
for k in ('overwrite_existing_tag_forbidden','overwrite_existing_release_forbidden'):
    if d.get(k) is not True: fail('overwrite_guard_missing_'+k)
if d.get('next_transaction')!='EXPLICIT_OWNER_RELEASE_TAG_AUTHORIZATION_REQUIRED': fail('next_transaction')

print('STABLE_RELEASE_TAG_PROMOTION=WAITING_OWNER_AUTHORIZATION')
print('RUNTIME_AUTHORITY=true')
print('OWNER_RELEASE_AUTHORIZATION_PRESENT=false')
print('PROMOTION_ELIGIBLE=false')
print('RELEASE_OR_TAG_AUTHORIZED=false')
print('TAG_CREATED=false')
print('RELEASE_CREATED=false')
