#!/usr/bin/env python3
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROMOTION = ROOT / '.pncc-dev/attestations/stable-release-tag-promotion-v7.0.1.json'
GRANT = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.1.json'
REQUEST = ROOT / '.pncc-dev/requests/runtime-qualification-v7.0.1.json'

EXPECTED_BASE_MAIN = 'aecbd06acfde97ef9eae8188b4517ec783a25fa7'
EXPECTED_ARTIFACT_SHA = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
EXPECTED_TARGET_TAG = 'v7.0.1'
EXPECTED_RELEASE_NAME = 'VPS Control PNCC v7.0.1'

REQUIRED_KEYS = {
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


def fail(msg):
    print('V701_RELEASE_TAG_PROMOTION=BLOCKED')
    print('ERROR=' + msg)
    print('RUNTIME_AUTHORITY=true')
    print('OWNER_RELEASE_AUTHORIZATION_PRESENT=false')
    print('PROMOTION_ELIGIBLE=false')
    print('RELEASE_OR_TAG_AUTHORIZED=false')
    print('TAG_CREATED=false')
    print('RELEASE_CREATED=false')
    print('STABLE_DECLARED=false')
    raise SystemExit(2)


def load(path):
    try:
        with path.open('r', encoding='utf-8-sig') as fh:
            return json.load(fh)
    except Exception as exc:
        fail('load_failed:' + path.name + ':' + type(exc).__name__)


promotion = load(PROMOTION)
grant = load(GRANT)
request = load(REQUEST)

if set(promotion) != REQUIRED_KEYS:
    fail('promotion_key_set')
if promotion.get('schema_version') != 2:
    fail('schema_version')
if promotion.get('contract_id') != 'PNCC_STABLE_RELEASE_TAG_PROMOTION_V2':
    fail('contract')
if promotion.get('stable_version') != '7.0.1':
    fail('stable_version')
if promotion.get('preparation_base_main') != EXPECTED_BASE_MAIN:
    fail('preparation_base_main')

candidate = request.get('candidate', {})
identity_pairs = (
    ('request_id', request.get('request_id')),
    ('candidate_id', candidate.get('candidate_id')),
    ('source_sha', candidate.get('source_sha')),
    ('stable_artifact_filename', candidate.get('artifact_filename')),
    ('stable_artifact_sha256', candidate.get('artifact_sha256')),
    ('stable_artifact_size_bytes', candidate.get('artifact_size_bytes')),
)
for key, expected in identity_pairs:
    if promotion.get(key) != expected:
        fail('identity_' + key)
if promotion.get('stable_artifact_sha256') != EXPECTED_ARTIFACT_SHA:
    fail('artifact_sha')

if grant.get('contract_id') != 'PNCC_STABLE_RUNTIME_AUTHORITY_OWNER_GRANT_V2':
    fail('grant_contract')
if promotion.get('runtime_authority_grant_contract_id') != grant.get('contract_id'):
    fail('grant_contract_binding')
if promotion.get('runtime_authority_grant_main') != EXPECTED_BASE_MAIN:
    fail('grant_main_binding')
for key in ('stable_artifact_filename','stable_artifact_sha256','stable_artifact_size_bytes','request_id','candidate_id','source_sha'):
    if promotion.get(key) != grant.get(key):
        fail('grant_identity_' + key)
if grant.get('wu087_state') != 'V701_NINE_SCOPE_OWNER_QUALIFICATION_PASS':
    fail('grant_wu087')
if grant.get('wu088_decision_state') != 'ELIGIBLE_FOR_OWNER_RUNTIME_AUTHORITY_DECISION':
    fail('grant_wu088')
if grant.get('grant_state') != 'RUNTIME_AUTHORITY_GRANTED':
    fail('grant_state')
if grant.get('owner_authorization_present') is not True or grant.get('owner_authorization_binding_complete') is not True:
    fail('runtime_authority_owner_binding')
if grant.get('runtime_authority') is not True:
    fail('runtime_authority_missing')
if grant.get('promotion_eligible') is not False or grant.get('release_or_tag_authorized') is not False:
    fail('runtime_grant_release_boundary')
if grant.get('tag_created') is not False or grant.get('release_created') is not False or grant.get('stable_declared') is not False:
    fail('runtime_grant_publication_already_true')

if promotion.get('wu087_state') != 'V701_NINE_SCOPE_OWNER_QUALIFICATION_PASS':
    fail('wu087_state')
if promotion.get('wu088_decision_state') != 'ELIGIBLE_FOR_OWNER_RUNTIME_AUTHORITY_DECISION':
    fail('wu088_state')
if promotion.get('wu089_grant_state') != 'RUNTIME_AUTHORITY_GRANTED':
    fail('wu089_state')
if promotion.get('runtime_authority') is not True:
    fail('runtime_authority')

if promotion.get('target_tag') != EXPECTED_TARGET_TAG:
    fail('target_tag')
if promotion.get('target_release_name') != EXPECTED_RELEASE_NAME:
    fail('target_release_name')
if promotion.get('target_tag_commit_policy') != 'PREPARATION_MERGE_SHA_ONLY':
    fail('target_tag_commit_policy')
if promotion.get('target_tag_commit') is not None:
    fail('premature_target_tag_commit')
if promotion.get('target_tag_observed_absent_at_preparation') is not True:
    fail('target_tag_preflight')
if promotion.get('target_release_observed_absent_at_preparation') is not True:
    fail('target_release_preflight')

if promotion.get('owner_release_authorization_present') is not False:
    fail('unexpected_owner_release_authorization')
if promotion.get('owner_release_authorization_binding_complete') is not False:
    fail('unexpected_owner_release_binding')
if promotion.get('owner_release_authorization_scope') != 'RELEASE_TAG_STABLE_PROMOTION_ONLY':
    fail('owner_release_scope')
if promotion.get('promotion_state') != 'WAITING_OWNER_RELEASE_AUTHORIZATION':
    fail('promotion_state')

for key in (
    'promotion_eligible','release_or_tag_authorized','tag_created','release_created',
    'release_asset_verified','stable_declared','artifact_rebuilt','artifact_substituted',
    'runtime_mutation','product_bytes_mutated','runtime_bytes_mutated',
    'private_runtime_payload_published'
):
    if promotion.get(key) is not False:
        fail('forbidden_true_' + key)
if promotion.get('release_asset_server_digest') is not None:
    fail('premature_release_asset_digest')
if promotion.get('overwrite_existing_tag_forbidden') is not True:
    fail('overwrite_tag_guard')
if promotion.get('overwrite_existing_release_forbidden') is not True:
    fail('overwrite_release_guard')
if promotion.get('next_transaction') != 'EXPLICIT_OWNER_RELEASE_AUTHORIZATION_BOUND_TO_PREPARATION_MERGE_REQUIRED':
    fail('next_transaction')

print('V701_RELEASE_TAG_PROMOTION=WAITING_OWNER_RELEASE_AUTHORIZATION')
print('RUNTIME_AUTHORITY=true')
print('TARGET_TAG=' + EXPECTED_TARGET_TAG)
print('OWNER_RELEASE_AUTHORIZATION_PRESENT=false')
print('OWNER_RELEASE_AUTHORIZATION_BINDING_COMPLETE=false')
print('PROMOTION_ELIGIBLE=false')
print('RELEASE_OR_TAG_AUTHORIZED=false')
print('TAG_CREATED=false')
print('RELEASE_CREATED=false')
print('RELEASE_ASSET_VERIFIED=false')
print('STABLE_DECLARED=false')
print('RUNTIME_MUTATION=false')
