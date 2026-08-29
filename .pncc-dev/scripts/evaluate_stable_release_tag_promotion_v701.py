#!/usr/bin/env python3
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROMOTION = ROOT / '.pncc-dev/attestations/stable-release-tag-promotion-v7.0.1.json'
AUTH = ROOT / '.pncc-dev/attestations/stable-release-tag-owner-authorization-v7.0.1.json'
GRANT = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.1.json'
REQUEST = ROOT / '.pncc-dev/requests/runtime-qualification-v7.0.1.json'

EXPECTED_PREPARATION_MAIN = '41e8c9c8bed2cc37423c33750d0748c49ff941b7'
EXPECTED_PREPARED_BLOB = 'f20891555e6db3a0b5bb57488bac5e8ccf36eb71'
EXPECTED_GRANT_MAIN = 'aecbd06acfde97ef9eae8188b4517ec783a25fa7'
EXPECTED_ARTIFACT_SHA = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
EXPECTED_TARGET_TAG = 'v7.0.1'
EXPECTED_RELEASE_NAME = 'VPS Control PNCC v7.0.1'
EXPECTED_PROVIDER_ARTIFACT_ID = 9711822972
EXPECTED_PROVIDER_ARTIFACT_DIGEST = 'sha256:47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5'
EXPECTED_PROVIDER_BUILD_RUN_ID = 33242642394

PROMOTION_KEYS = {
    'schema_version','contract_id','stable_version','preparation_base_main',
    'stable_artifact_filename','stable_artifact_sha256','stable_artifact_size_bytes',
    'request_id','candidate_id','source_sha','runtime_authority_grant_contract_id',
    'runtime_authority_grant_main','wu087_state','wu088_decision_state','wu089_grant_state',
    'runtime_authority','target_tag','target_release_name','target_tag_commit_policy',
    'target_tag_commit','target_tag_observed_absent_at_preparation',
    'target_release_observed_absent_at_preparation','owner_release_authorization_present',
    'owner_release_authorization_binding_complete','owner_release_authorization_scope',
    'promotion_state','promotion_eligible','release_or_tag_authorized','tag_created',
    'release_created','release_asset_verified','release_asset_server_digest','stable_declared',
    'artifact_rebuilt','artifact_substituted','runtime_mutation','product_bytes_mutated',
    'runtime_bytes_mutated','private_runtime_payload_published','overwrite_existing_tag_forbidden',
    'overwrite_existing_release_forbidden','next_transaction'
}

AUTH_KEYS = {
    'schema_version','contract_id','stable_version','authorized_preparation_main',
    'authorized_prepared_promotion_contract_blob_sha','stable_artifact_filename',
    'stable_artifact_sha256','stable_artifact_size_bytes','request_id','candidate_id','source_sha',
    'target_tag','target_release_name','target_tag_commit','owner_release_authorization_scope',
    'owner_release_authorization_present','owner_release_authorization_binding_complete',
    'promotion_eligibility_authorized','tag_creation_authorized','release_creation_authorized',
    'release_asset_upload_authorized','release_asset_server_digest_verification_required',
    'stable_declaration_authorized','provider_artifact_id','provider_artifact_digest',
    'provider_build_run_id','overwrite_existing_tag_forbidden','move_existing_tag_forbidden',
    'overwrite_existing_release_forbidden','artifact_rebuild_authorized',
    'artifact_substitution_authorized','product_bytes_mutation_authorized',
    'runtime_bytes_mutation_authorized','private_runtime_payload_publication_authorized',
    'reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized'
}


def fail(msg):
    print('V701_RELEASE_TAG_PROMOTION=BLOCKED')
    print('ERROR=' + msg)
    raise SystemExit(2)


def load(path):
    try:
        with path.open('r', encoding='utf-8-sig') as fh:
            return json.load(fh)
    except Exception as exc:
        fail('load_failed:' + path.name + ':' + type(exc).__name__)


promotion = load(PROMOTION)
auth = load(AUTH)
grant = load(GRANT)
request = load(REQUEST)
candidate = request.get('candidate', {})

if set(promotion) != PROMOTION_KEYS:
    fail('promotion_key_set')
if set(auth) != AUTH_KEYS:
    fail('authorization_key_set')
if promotion.get('schema_version') != 2 or promotion.get('contract_id') != 'PNCC_STABLE_RELEASE_TAG_PROMOTION_V2':
    fail('promotion_contract')
if auth.get('schema_version') != 1 or auth.get('contract_id') != 'PNCC_STABLE_RELEASE_TAG_OWNER_AUTHORIZATION_V1':
    fail('authorization_contract')
if promotion.get('stable_version') != '7.0.1' or auth.get('stable_version') != '7.0.1':
    fail('stable_version')
if promotion.get('preparation_base_main') != EXPECTED_GRANT_MAIN:
    fail('promotion_preparation_base_main')
if promotion.get('runtime_authority_grant_main') != EXPECTED_GRANT_MAIN:
    fail('runtime_authority_grant_main')
if auth.get('authorized_preparation_main') != EXPECTED_PREPARATION_MAIN:
    fail('authorized_preparation_main')
if auth.get('authorized_prepared_promotion_contract_blob_sha') != EXPECTED_PREPARED_BLOB:
    fail('authorized_prepared_blob')

identity = {
    'stable_artifact_filename': candidate.get('artifact_filename'),
    'stable_artifact_sha256': candidate.get('artifact_sha256'),
    'stable_artifact_size_bytes': candidate.get('artifact_size_bytes'),
    'request_id': request.get('request_id'),
    'candidate_id': candidate.get('candidate_id'),
    'source_sha': candidate.get('source_sha'),
}
for key, expected in identity.items():
    if promotion.get(key) != expected or auth.get(key) != expected:
        fail('identity_' + key)
if promotion.get('stable_artifact_sha256') != EXPECTED_ARTIFACT_SHA:
    fail('artifact_sha')

if candidate.get('provider_artifact_id') != EXPECTED_PROVIDER_ARTIFACT_ID:
    fail('request_provider_artifact_id')
if 'sha256:' + str(candidate.get('provider_artifact_digest')) != EXPECTED_PROVIDER_ARTIFACT_DIGEST:
    fail('request_provider_artifact_digest')
if candidate.get('provider_build_run_id') != EXPECTED_PROVIDER_BUILD_RUN_ID:
    fail('request_provider_build_run_id')
if auth.get('provider_artifact_id') != EXPECTED_PROVIDER_ARTIFACT_ID:
    fail('auth_provider_artifact_id')
if auth.get('provider_artifact_digest') != EXPECTED_PROVIDER_ARTIFACT_DIGEST:
    fail('auth_provider_artifact_digest')
if auth.get('provider_build_run_id') != EXPECTED_PROVIDER_BUILD_RUN_ID:
    fail('auth_provider_build_run_id')

if grant.get('contract_id') != 'PNCC_STABLE_RUNTIME_AUTHORITY_OWNER_GRANT_V2':
    fail('grant_contract')
for key in ('stable_artifact_filename','stable_artifact_sha256','stable_artifact_size_bytes','request_id','candidate_id','source_sha'):
    if promotion.get(key) != grant.get(key):
        fail('grant_identity_' + key)
if grant.get('grant_state') != 'RUNTIME_AUTHORITY_GRANTED' or grant.get('runtime_authority') is not True:
    fail('runtime_authority_missing')
if grant.get('owner_authorization_present') is not True or grant.get('owner_authorization_binding_complete') is not True:
    fail('runtime_authority_owner_binding')
if grant.get('promotion_eligible') is not False or grant.get('release_or_tag_authorized') is not False:
    fail('grant_release_authority_transfer')

if promotion.get('wu087_state') != 'V701_NINE_SCOPE_OWNER_QUALIFICATION_PASS':
    fail('wu087_state')
if promotion.get('wu088_decision_state') != 'ELIGIBLE_FOR_OWNER_RUNTIME_AUTHORITY_DECISION':
    fail('wu088_state')
if promotion.get('wu089_grant_state') != 'RUNTIME_AUTHORITY_GRANTED':
    fail('wu089_state')
if promotion.get('runtime_authority') is not True:
    fail('runtime_authority')

for obj_name, obj in (('promotion', promotion), ('authorization', auth)):
    if obj.get('target_tag') != EXPECTED_TARGET_TAG:
        fail(obj_name + '_target_tag')
    if obj.get('target_release_name') != EXPECTED_RELEASE_NAME:
        fail(obj_name + '_target_release_name')
if promotion.get('target_tag_commit_policy') != 'PREPARATION_MERGE_SHA_ONLY':
    fail('target_tag_commit_policy')
if promotion.get('target_tag_commit') != EXPECTED_PREPARATION_MAIN or auth.get('target_tag_commit') != EXPECTED_PREPARATION_MAIN:
    fail('target_tag_commit')
if promotion.get('target_tag_observed_absent_at_preparation') is not True or promotion.get('target_release_observed_absent_at_preparation') is not True:
    fail('preparation_namespace_observation')

if auth.get('owner_release_authorization_scope') != 'RELEASE_TAG_STABLE_PROMOTION_ONLY':
    fail('authorization_scope')
if promotion.get('owner_release_authorization_scope') != auth.get('owner_release_authorization_scope'):
    fail('promotion_authorization_scope')
for key in (
    'owner_release_authorization_present','owner_release_authorization_binding_complete',
    'promotion_eligibility_authorized','tag_creation_authorized','release_creation_authorized',
    'release_asset_upload_authorized','release_asset_server_digest_verification_required',
    'stable_declaration_authorized','overwrite_existing_tag_forbidden','move_existing_tag_forbidden',
    'overwrite_existing_release_forbidden'
):
    if auth.get(key) is not True:
        fail('authorization_required_true_' + key)
for key in (
    'artifact_rebuild_authorized','artifact_substitution_authorized','product_bytes_mutation_authorized',
    'runtime_bytes_mutation_authorized','private_runtime_payload_publication_authorized',
    'reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized'
):
    if auth.get(key) is not False:
        fail('authorization_forbidden_true_' + key)

if promotion.get('owner_release_authorization_present') is not True or promotion.get('owner_release_authorization_binding_complete') is not True:
    fail('promotion_owner_authorization_binding')
if promotion.get('promotion_state') != 'AUTHORIZED_PENDING_EXECUTION':
    fail('promotion_state')
if promotion.get('promotion_eligible') is not True or promotion.get('release_or_tag_authorized') is not True:
    fail('promotion_authority_flags')
for key in (
    'tag_created','release_created','release_asset_verified','stable_declared','artifact_rebuilt',
    'artifact_substituted','runtime_mutation','product_bytes_mutated','runtime_bytes_mutated',
    'private_runtime_payload_published'
):
    if promotion.get(key) is not False:
        fail('premature_or_forbidden_true_' + key)
if promotion.get('release_asset_server_digest') is not None:
    fail('premature_release_asset_digest')
if promotion.get('overwrite_existing_tag_forbidden') is not True or promotion.get('overwrite_existing_release_forbidden') is not True:
    fail('overwrite_guard')
if promotion.get('next_transaction') != 'CREATE_EXACT_TAG_AND_RELEASE_NO_OVERWRITE':
    fail('next_transaction')

print('V701_RELEASE_TAG_PROMOTION=AUTHORIZED_PENDING_EXECUTION')
print('RUNTIME_AUTHORITY=true')
print('OWNER_RELEASE_AUTHORIZATION_PRESENT=true')
print('OWNER_RELEASE_AUTHORIZATION_BINDING_COMPLETE=true')
print('PROMOTION_ELIGIBLE=true')
print('RELEASE_OR_TAG_AUTHORIZED=true')
print('TARGET_TAG=' + EXPECTED_TARGET_TAG)
print('TARGET_TAG_COMMIT=' + EXPECTED_PREPARATION_MAIN)
print('TAG_CREATED=false')
print('RELEASE_CREATED=false')
print('RELEASE_ASSET_VERIFIED=false')
print('STABLE_DECLARED=false')
print('RUNTIME_MUTATION=false')
