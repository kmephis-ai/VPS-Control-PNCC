#!/usr/bin/env python3
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
GRANT = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.1.json'
AUTH = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-authorization-v7.0.1.json'
RECEIPT = ROOT / '.pncc-dev/attestations/runtime-qualification-v7.0.1.json'
DECISION = ROOT / '.pncc-dev/attestations/stable-runtime-authority-decision-v7.0.1.json'
REQUEST = ROOT / '.pncc-dev/requests/runtime-qualification-v7.0.1.json'

EXPECTED_PREPARATION_BASE = 'b14c2480bdcd0b3fe89b0aa741810cb9323e36d6'
EXPECTED_AUTHORIZED_MAIN = 'c0b6c2dcbf74c7978ec5e668c06762c677b5d078'
EXPECTED_PREPARED_BLOB = '087bb42e2e21bfa68c25abe921f19944072d3dc4'
EXPECTED_ARTIFACT_SHA = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'

GRANT_KEYS = {
    'schema_version','contract_id','stable_version','preparation_base_main',
    'stable_artifact_filename','stable_artifact_sha256','stable_artifact_size_bytes',
    'request_id','candidate_id','source_sha','runtime_receipt_contract_id',
    'runtime_authority_decision_contract_id','wu087_state','wu088_decision_state',
    'runtime_authority_candidate','owner_authorization_present',
    'owner_authorization_binding_complete','owner_authorization_scope','grant_state',
    'runtime_authority','promotion_eligible','release_or_tag_authorized','tag_created',
    'release_created','stable_declared','artifact_rebuilt','artifact_substituted',
    'runtime_mutation','product_bytes_mutated','runtime_bytes_mutated',
    'private_runtime_payload_published','next_transaction'
}

AUTH_KEYS = {
    'schema_version','contract_id','stable_version','authorized_preparation_main',
    'authorized_prepared_grant_contract_blob_sha','stable_artifact_filename',
    'stable_artifact_sha256','stable_artifact_size_bytes','request_id','candidate_id',
    'source_sha','owner_authorization_scope','owner_authorization_present',
    'owner_authorization_binding_complete','runtime_authority_grant_authorized',
    'promotion_eligible_authorized','release_or_tag_authorized','tag_creation_authorized',
    'release_creation_authorized','stable_declaration_authorized','artifact_rebuild_authorized',
    'artifact_substitution_authorized','product_bytes_mutation_authorized',
    'runtime_bytes_mutation_authorized','private_runtime_payload_publication_authorized',
    'reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized'
}


def fail(msg):
    print('V701_RUNTIME_AUTHORITY_OWNER_GRANT=BLOCKED')
    print('ERROR=' + msg)
    print('RUNTIME_AUTHORITY=false')
    print('PROMOTION_ELIGIBLE=false')
    print('RELEASE_OR_TAG_AUTHORIZED=false')
    raise SystemExit(2)


def load(path):
    with path.open('r', encoding='utf-8-sig') as fh:
        return json.load(fh)


try:
    grant = load(GRANT)
    auth = load(AUTH)
    receipt = load(RECEIPT)
    decision = load(DECISION)
    request = load(REQUEST)
except Exception as exc:
    fail('load_failed:' + type(exc).__name__)

if set(grant) != GRANT_KEYS:
    fail('grant_key_set')
if set(auth) != AUTH_KEYS:
    fail('authorization_key_set')
if grant.get('schema_version') != 2 or grant.get('contract_id') != 'PNCC_STABLE_RUNTIME_AUTHORITY_OWNER_GRANT_V2':
    fail('grant_contract')
if auth.get('schema_version') != 1 or auth.get('contract_id') != 'PNCC_STABLE_RUNTIME_AUTHORITY_OWNER_AUTHORIZATION_V1':
    fail('authorization_contract')
if grant.get('stable_version') != '7.0.1' or auth.get('stable_version') != '7.0.1':
    fail('stable_version')
if grant.get('preparation_base_main') != EXPECTED_PREPARATION_BASE:
    fail('preparation_base_main')
if auth.get('authorized_preparation_main') != EXPECTED_AUTHORIZED_MAIN:
    fail('authorized_preparation_main')
if auth.get('authorized_prepared_grant_contract_blob_sha') != EXPECTED_PREPARED_BLOB:
    fail('authorized_prepared_blob')

candidate = request.get('candidate', {})
identity = {
    'request_id': request.get('request_id'),
    'candidate_id': candidate.get('candidate_id'),
    'source_sha': candidate.get('source_sha'),
    'stable_artifact_filename': candidate.get('artifact_filename'),
    'stable_artifact_sha256': candidate.get('artifact_sha256'),
    'stable_artifact_size_bytes': candidate.get('artifact_size_bytes'),
}
for key, expected in identity.items():
    if grant.get(key) != expected:
        fail('grant_identity_' + key)
    if auth.get(key) != expected:
        fail('authorization_identity_' + key)
if grant.get('stable_artifact_sha256') != EXPECTED_ARTIFACT_SHA:
    fail('artifact_sha')

if grant.get('runtime_receipt_contract_id') != receipt.get('contract_id'):
    fail('receipt_contract')
if grant.get('runtime_authority_decision_contract_id') != decision.get('contract_id'):
    fail('decision_contract')
if receipt.get('qualification_state') != 'RUNTIME_VERIFIED' or receipt.get('pass_scope_count') != 9:
    fail('runtime_truth_not_verified')
if receipt.get('runtime_authority_candidate') is not True:
    fail('receipt_authority_candidate')
if receipt.get('repository_runtime_authority') is not False:
    fail('receipt_historical_boundary_mutated')
if decision.get('decision_state') != 'ELIGIBLE_FOR_OWNER_RUNTIME_AUTHORITY_DECISION':
    fail('wu088_decision_state')
if decision.get('runtime_authority_candidate') is not True:
    fail('decision_authority_candidate')
if decision.get('runtime_authority') is not False:
    fail('decision_historical_boundary_mutated')
if decision.get('promotion_eligible') is not False or decision.get('release_or_tag_authorized') is not False:
    fail('decision_release_boundary')

if grant.get('wu087_state') != 'V701_NINE_SCOPE_OWNER_QUALIFICATION_PASS':
    fail('wu087_state')
if grant.get('wu088_decision_state') != 'ELIGIBLE_FOR_OWNER_RUNTIME_AUTHORITY_DECISION':
    fail('wu088_state')
if grant.get('runtime_authority_candidate') is not True:
    fail('runtime_authority_candidate')
if grant.get('owner_authorization_scope') != 'RUNTIME_AUTHORITY_GRANT_ONLY':
    fail('owner_authorization_scope')
if auth.get('owner_authorization_scope') != 'RUNTIME_AUTHORITY_GRANT_ONLY':
    fail('authorization_scope')
if auth.get('owner_authorization_present') is not True or auth.get('owner_authorization_binding_complete') is not True:
    fail('authorization_missing')
if auth.get('runtime_authority_grant_authorized') is not True:
    fail('runtime_authority_not_authorized')
for key in (
    'promotion_eligible_authorized','release_or_tag_authorized','tag_creation_authorized',
    'release_creation_authorized','stable_declaration_authorized','artifact_rebuild_authorized',
    'artifact_substitution_authorized','product_bytes_mutation_authorized',
    'runtime_bytes_mutation_authorized','private_runtime_payload_publication_authorized',
    'reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized'
):
    if auth.get(key) is not False:
        fail('forbidden_authorization_' + key)

if grant.get('owner_authorization_present') is not True or grant.get('owner_authorization_binding_complete') is not True:
    fail('grant_authorization_missing')
if grant.get('grant_state') != 'RUNTIME_AUTHORITY_GRANTED':
    fail('grant_state')
if grant.get('runtime_authority') is not True:
    fail('runtime_authority_not_granted')
for key in (
    'promotion_eligible','release_or_tag_authorized','tag_created','release_created',
    'stable_declared','artifact_rebuilt','artifact_substituted','runtime_mutation',
    'product_bytes_mutated','runtime_bytes_mutated','private_runtime_payload_published'
):
    if grant.get(key) is not False:
        fail('forbidden_true_' + key)
if grant.get('next_transaction') != 'SEPARATE_EXPLICIT_OWNER_AUTHORIZED_RELEASE_PROMOTION':
    fail('next_transaction')

print('V701_RUNTIME_AUTHORITY_OWNER_GRANT=RUNTIME_AUTHORITY_GRANTED')
print('AUTHORIZED_PREPARATION_MAIN=' + EXPECTED_AUTHORIZED_MAIN)
print('AUTHORIZED_PREPARED_CONTRACT_BLOB=' + EXPECTED_PREPARED_BLOB)
print('OWNER_AUTHORIZATION_PRESENT=true')
print('OWNER_AUTHORIZATION_BINDING_COMPLETE=true')
print('RUNTIME_AUTHORITY=true')
print('PROMOTION_ELIGIBLE=false')
print('RELEASE_OR_TAG_AUTHORIZED=false')
print('TAG_CREATED=false')
print('RELEASE_CREATED=false')
print('STABLE_DECLARED=false')
print('PRODUCT_BYTES_MUTATED=false')
print('RUNTIME_BYTES_MUTATED=false')
print('PRIVATE_RUNTIME_PAYLOAD_PUBLISHED=false')
