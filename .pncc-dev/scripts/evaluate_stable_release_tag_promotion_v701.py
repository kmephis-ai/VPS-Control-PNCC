#!/usr/bin/env python3
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
PROMOTION=ROOT/'.pncc-dev/attestations/stable-release-tag-promotion-v7.0.1.json'
PUBLICATION=ROOT/'.pncc-dev/attestations/stable-release-tag-publication-v7.0.1.json'
AUTH=ROOT/'.pncc-dev/attestations/stable-release-tag-owner-authorization-v7.0.1.json'
GRANT=ROOT/'.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.1.json'
REQUEST=ROOT/'.pncc-dev/requests/runtime-qualification-v7.0.1.json'
def load(p):
    with p.open('r',encoding='utf-8-sig') as f:return json.load(f)
def fail(msg):
    print('V701_RELEASE_TAG_PROMOTION=BLOCKED');print('ERROR='+msg);raise SystemExit(2)
p=load(PROMOTION); r=load(PUBLICATION); a=load(AUTH); g=load(GRANT); q=load(REQUEST); c=q['candidate']
name='VPS-Control-v7.0.1.zip'; sha='22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'; size=701893
request='PNCC-RQ-V7.0.1-D58023321360'; candidate='PNCC-V7.0.1-D58023321360'; source='d5802332136087339482c9b3171c1c5c9c18411e'; target='41e8c9c8bed2cc37423c33750d0748c49ff941b7'
if p.get('contract_id')!='PNCC_STABLE_RELEASE_TAG_PROMOTION_V2' or p.get('stable_version')!='7.0.1':fail('promotion_contract')
if r.get('contract_id')!='PNCC_STABLE_RELEASE_TAG_PUBLICATION_RECEIPT_V1' or r.get('publication_state')!='VERIFIED':fail('publication_receipt')
if a.get('owner_release_authorization_scope')!='RELEASE_TAG_STABLE_PROMOTION_ONLY' or a.get('owner_release_authorization_present') is not True or a.get('owner_release_authorization_binding_complete') is not True:fail('owner_authorization')
if g.get('grant_state')!='RUNTIME_AUTHORITY_GRANTED' or g.get('runtime_authority') is not True:fail('runtime_authority')
for obj in (p,a,g):
    if obj.get('stable_artifact_filename')!=name or obj.get('stable_artifact_sha256')!=sha or obj.get('stable_artifact_size_bytes')!=size or obj.get('request_id')!=request or obj.get('candidate_id')!=candidate or obj.get('source_sha')!=source:fail('governed_identity')
if r.get('release_asset_name')!=name or r.get('release_asset_size_bytes')!=size or r.get('request_id')!=request or r.get('candidate_id')!=candidate or r.get('source_sha')!=source:fail('publication_identity')
if c.get('artifact_filename')!=name or c.get('artifact_sha256')!=sha or c.get('artifact_size_bytes')!=size:fail('request_candidate_identity')
if p.get('target_tag')!='v7.0.1' or p.get('target_release_name')!='VPS Control PNCC v7.0.1' or p.get('target_tag_commit')!=target:fail('target_identity')
if r.get('target_tag')!='v7.0.1' or r.get('target_tag_commit')!=target or r.get('release_id')!=379032537 or r.get('release_asset_id')!=535416506:fail('provider_publication_identity')
if r.get('release_asset_server_digest')!='sha256:'+sha or r.get('independent_download_sha256')!=sha or r.get('independent_download_size_bytes')!=size:fail('release_asset_identity')
if r.get('release_draft') is not False or r.get('release_prerelease') is not False:fail('release_visibility')
if p.get('promotion_state')!='PROMOTED' or p.get('promotion_eligible') is not True or p.get('release_or_tag_authorized') is not True:fail('promotion_state')
for k in ('tag_created','release_created','release_asset_verified','stable_declared'):
    if p.get(k) is not True:fail('promotion_true_'+k)
if p.get('release_asset_server_digest')!='sha256:'+sha:fail('promotion_digest')
for obj_name,obj in (('promotion',p),('publication',r)):
    for k in ('artifact_rebuilt','artifact_substituted','runtime_mutation','product_bytes_mutated','runtime_bytes_mutated','private_runtime_payload_published'):
        if obj.get(k) is not False:fail(obj_name+'_forbidden_'+k)
if r.get('reserve_1080_lifecycle_mutation') is not False or r.get('primary_1081_lifecycle_mutation') is not False:fail('tunnel_lifecycle_mutation')
if p.get('next_transaction')!='POST_STABLE_CLOSEOUT':fail('next_transaction')
print('V701_RELEASE_TAG_PROMOTION=PROMOTED');print('STABLE_DECLARED=true');print('TAG_CREATED=true');print('RELEASE_CREATED=true');print('RELEASE_ASSET_VERIFIED=true');print('TARGET_TAG_COMMIT='+target);print('RELEASE_ASSET_SERVER_DIGEST=sha256:'+sha);print('RUNTIME_MUTATION=false')
