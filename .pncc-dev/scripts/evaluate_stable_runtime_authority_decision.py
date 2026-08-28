#!/usr/bin/env python3
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / '.pncc-dev/attestations/stable-runtime-authority-decision-v7.0.0.json'
EXPECTED_MAIN='363b5e91f43afa7334cd1e8a2ae5c970c48316d4'
EXPECTED_STABLE='1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599'
EXPECTED_ROLLBACK='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
EXPECTED_ENGINE='843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'

def fail(msg):
    print('STABLE_RUNTIME_AUTHORITY_DECISION=BLOCKED')
    print('ERROR='+msg)
    print('RUNTIME_AUTHORITY=false')
    print('PROMOTION_ELIGIBLE=false')
    print('RELEASE_OR_TAG_AUTHORIZED=false')
    raise SystemExit(2)

try:
    with P.open('r',encoding='utf-8-sig') as f: d=json.load(f)
except Exception as e:
    fail('load_failed:'+type(e).__name__)

required={
 'schema_version','contract_id','stable_version','authoritative_main','stable_artifact_filename',
 'stable_artifact_sha256','stable_artifact_size_bytes','rollback_v631_sha256','stable_engine_sha256',
 'wu073_state','pass_scope_count','rc_runtime_truth_used','runtime_mutation','runtime_authority_candidate',
 'runtime_authority','promotion_eligible','release_or_tag_authorized','artifact_rebuilt','artifact_substituted',
 'tag_created','release_created','stable_declared','decision_state','next_transaction'
}
if set(d)!=required: fail('key_set')
if d['schema_version']!=1 or d['contract_id']!='PNCC_STABLE_RUNTIME_AUTHORITY_DECISION_V1': fail('contract')
if d['stable_version']!='7.0.0': fail('version')
if d['authoritative_main']!=EXPECTED_MAIN: fail('main_identity')
if d['stable_artifact_filename']!='VPS-Control-v7.0.0.zip' or d['stable_artifact_sha256']!=EXPECTED_STABLE or d['stable_artifact_size_bytes']!=700897: fail('stable_artifact_identity')
if d['rollback_v631_sha256']!=EXPECTED_ROLLBACK: fail('rollback_identity')
if d['stable_engine_sha256']!=EXPECTED_ENGINE: fail('engine_identity')
if d['wu073_state']!='STABLE_NINE_SCOPE_RECONCILE_PASS' or d['pass_scope_count']!=9: fail('wu073_not_9_of_9')
if d['rc_runtime_truth_used'] is not False: fail('rc_truth_transfer_forbidden')
if d['runtime_mutation'] is not False: fail('runtime_mutation_forbidden')
if d['runtime_authority_candidate'] is not True: fail('authority_candidate_missing')
for k in ('runtime_authority','promotion_eligible','release_or_tag_authorized','artifact_rebuilt','artifact_substituted','tag_created','release_created','stable_declared'):
    if d[k] is not False: fail('forbidden_true_'+k)
if d['decision_state']!='ELIGIBLE_FOR_OWNER_PROMOTION_DECISION': fail('decision_state')
if d['next_transaction']!='SEPARATE_EXPLICIT_OWNER_AUTHORIZED_RUNTIME_AUTHORITY_GRANT': fail('next_transaction')

print('STABLE_RUNTIME_AUTHORITY_DECISION=ELIGIBLE_FOR_OWNER_PROMOTION_DECISION')
print('PASS_SCOPES=9')
print('RC_RUNTIME_TRUTH_USED=false')
print('RUNTIME_AUTHORITY_CANDIDATE=true')
print('RUNTIME_AUTHORITY=false')
print('PROMOTION_ELIGIBLE=false')
print('RELEASE_OR_TAG_AUTHORIZED=false')
print('TAG_CREATED=false')
print('RELEASE_CREATED=false')
print('STABLE_DECLARED=false')
