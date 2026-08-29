#!/usr/bin/env python3
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DECISION = ROOT / '.pncc-dev/attestations/stable-runtime-authority-decision-v7.0.1.json'
RECEIPT = ROOT / '.pncc-dev/attestations/runtime-qualification-v7.0.1.json'
REQUEST = ROOT / '.pncc-dev/requests/runtime-qualification-v7.0.1.json'

EXPECTED_BASIS_MAIN = '548eb34415e64ccfef6bf2b9e1453afe3f768bf1'
EXPECTED_RECEIPT_SHA = '14bd850d8465f1e5de040360a7ee040d9b1224175705c2623c83f10340514456'
EXPECTED_FINAL_RESULT_SHA = '3ef54c6a7c985ab02e10d7e03cb73a9db931507aa0439dceef38729a8f6bd862'
EXPECTED_PRIVATE_EVIDENCE_SHA = '0a1c3847daa6b13e97adc2c66c37d618d89484340d1bbf33fb88dbcc7cb01163'
EXPECTED_ROLLBACK = '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
EXPECTED_ENGINE = '843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'

REQUIRED_KEYS = {
    'schema_version','contract_id','stable_version','authority_basis_main','request_id',
    'candidate_id','source_sha','stable_artifact_filename','stable_artifact_sha256',
    'stable_artifact_size_bytes','runtime_receipt_contract_id','runtime_receipt_sha256',
    'final_result_sha256','private_evidence_bundle_sha256','rollback_v631_sha256',
    'stable_engine_sha256','wu087_state','pass_scope_count','rc_runtime_truth_used',
    'runtime_mutation','runtime_authority_candidate','runtime_authority','promotion_eligible',
    'release_or_tag_authorized','artifact_rebuilt','artifact_substituted','tag_created',
    'release_created','stable_declared','decision_state','next_transaction'
}

def fail(msg):
    print('V701_RUNTIME_AUTHORITY_DECISION=BLOCKED')
    print('ERROR=' + msg)
    print('RUNTIME_AUTHORITY=false')
    print('PROMOTION_ELIGIBLE=false')
    print('RELEASE_OR_TAG_AUTHORIZED=false')
    raise SystemExit(2)

def load(path):
    with path.open('r', encoding='utf-8-sig') as fh:
        return json.load(fh)

try:
    decision = load(DECISION)
    receipt = load(RECEIPT)
    request = load(REQUEST)
except Exception as exc:
    fail('load_failed:' + type(exc).__name__)

if set(decision) != REQUIRED_KEYS:
    fail('key_set')
if decision.get('schema_version') != 2 or decision.get('contract_id') != 'PNCC_STABLE_RUNTIME_AUTHORITY_DECISION_V2':
    fail('contract')
if decision.get('stable_version') != '7.0.1':
    fail('version')
if decision.get('authority_basis_main') != EXPECTED_BASIS_MAIN:
    fail('authority_basis_main')
if decision.get('runtime_receipt_contract_id') != receipt.get('contract_id'):
    fail('receipt_contract')
if hashlib.sha256(RECEIPT.read_bytes()).hexdigest() != EXPECTED_RECEIPT_SHA:
    fail('receipt_bytes_sha256')
if decision.get('runtime_receipt_sha256') != EXPECTED_RECEIPT_SHA:
    fail('decision_receipt_sha256')

candidate = request.get('candidate', {})
pairs = (
    ('request_id', request.get('request_id')),
    ('candidate_id', candidate.get('candidate_id')),
    ('source_sha', candidate.get('source_sha')),
    ('stable_artifact_filename', candidate.get('artifact_filename')),
    ('stable_artifact_sha256', candidate.get('artifact_sha256')),
    ('stable_artifact_size_bytes', candidate.get('artifact_size_bytes')),
)
for key, expected in pairs:
    if decision.get(key) != expected:
        fail('identity_' + key)

if decision.get('final_result_sha256') != EXPECTED_FINAL_RESULT_SHA:
    fail('final_result_sha256')
if decision.get('private_evidence_bundle_sha256') != EXPECTED_PRIVATE_EVIDENCE_SHA:
    fail('private_evidence_bundle_sha256')
if receipt.get('final_result_sha256') != EXPECTED_FINAL_RESULT_SHA:
    fail('receipt_result_hash')
if receipt.get('private_evidence_bundle_sha256') != EXPECTED_PRIVATE_EVIDENCE_SHA:
    fail('receipt_private_bundle_hash')
if decision.get('rollback_v631_sha256') != EXPECTED_ROLLBACK:
    fail('rollback_identity')
if decision.get('stable_engine_sha256') != EXPECTED_ENGINE:
    fail('engine_identity')
if decision.get('wu087_state') != 'V701_NINE_SCOPE_OWNER_QUALIFICATION_PASS':
    fail('wu087_state')
if decision.get('pass_scope_count') != 9 or receipt.get('pass_scope_count') != 9:
    fail('scope_count')
if decision.get('rc_runtime_truth_used') is not False:
    fail('rc_runtime_truth_used')
if decision.get('runtime_mutation') is not False or receipt.get('runtime_mutation') is not False:
    fail('runtime_mutation')
if decision.get('runtime_authority_candidate') is not True or receipt.get('runtime_authority_candidate') is not True:
    fail('runtime_authority_candidate')

for key in (
    'runtime_authority','promotion_eligible','release_or_tag_authorized',
    'artifact_rebuilt','artifact_substituted','tag_created','release_created','stable_declared'
):
    if decision.get(key) is not False:
        fail('forbidden_true_' + key)
if receipt.get('repository_runtime_authority') is not False:
    fail('receipt_repository_runtime_authority')
if receipt.get('promotion_eligible') is not False or receipt.get('release_or_tag_authorized') is not False:
    fail('receipt_promotion_boundary')
if decision.get('decision_state') != 'ELIGIBLE_FOR_OWNER_RUNTIME_AUTHORITY_DECISION':
    fail('decision_state')
if decision.get('next_transaction') != 'SEPARATE_EXPLICIT_OWNER_AUTHORIZED_RUNTIME_AUTHORITY_GRANT':
    fail('next_transaction')

print('V701_RUNTIME_AUTHORITY_DECISION=ELIGIBLE_FOR_OWNER_RUNTIME_AUTHORITY_DECISION')
print('PASS_SCOPES=9')
print('RUNTIME_AUTHORITY_CANDIDATE=true')
print('RUNTIME_AUTHORITY=false')
print('PROMOTION_ELIGIBLE=false')
print('RELEASE_OR_TAG_AUTHORIZED=false')
print('RC_RUNTIME_TRUTH_USED=false')
