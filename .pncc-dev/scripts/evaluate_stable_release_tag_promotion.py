#!/usr/bin/env python3
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
P=ROOT/'.pncc-dev/attestations/stable-release-tag-promotion-v7.0.0.json'
EXPECTED_MAIN='d889b52879fd21612f639cb2441fbd1ff8bc3f02'
EXPECTED_STABLE='1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599'

def fail(msg):
    print('STABLE_RELEASE_TAG_PROMOTION=BLOCKED')
    print('ERROR='+msg)
    raise SystemExit(2)

d=json.load(P.open('r',encoding='utf-8-sig'))
if d.get('contract_id')!='PNCC_STABLE_RELEASE_TAG_PROMOTION_V1': fail('contract')
if d.get('stable_version')!='7.0.0' or d.get('authoritative_main')!=EXPECTED_MAIN: fail('identity')
if d.get('stable_artifact_filename')!='VPS-Control-v7.0.0.zip' or d.get('stable_artifact_sha256')!=EXPECTED_STABLE or d.get('stable_artifact_size_bytes')!=700897: fail('artifact_identity')
if d.get('wu073_state')!='STABLE_NINE_SCOPE_RECONCILE_PASS': fail('wu073')
if d.get('wu074_decision_state')!='ELIGIBLE_FOR_OWNER_PROMOTION_DECISION': fail('wu074')
if d.get('wu075_grant_state')!='RUNTIME_AUTHORITY_GRANTED' or d.get('runtime_authority') is not True: fail('runtime_authority')
if d.get('owner_release_authorization_present') is not True or d.get('owner_release_authorization_binding_complete') is not True: fail('owner_authorization')
if d.get('promotion_state')!='PROMOTED': fail('promotion_state')
for k in ('promotion_eligible','release_or_tag_authorized','tag_created','release_created','release_asset_verified','stable_declared'):
    if d.get(k) is not True: fail('required_true_'+k)
for k in ('artifact_rebuilt','artifact_substituted','runtime_mutation','product_bytes_mutated','runtime_bytes_mutated'):
    if d.get(k) is not False: fail('forbidden_true_'+k)
if d.get('tag_target_commit')!=EXPECTED_MAIN: fail('tag_target')
if d.get('release_asset_server_digest')!='sha256:'+EXPECTED_STABLE: fail('server_digest')
if d.get('next_transaction')!='STABLE_V7_0_0_COMPLETE': fail('next_transaction')
print('STABLE_RELEASE_TAG_PROMOTION=PROMOTED')
print('RUNTIME_AUTHORITY=true')
print('TAG_CREATED=true')
print('RELEASE_CREATED=true')
print('RELEASE_ASSET_VERIFIED=true')
print('STABLE_DECLARED=true')
