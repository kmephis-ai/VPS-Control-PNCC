#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / '.pncc-dev' / 'attestations' / 'stable-v7.0.1-completion.json'
PROMOTION = ROOT / '.pncc-dev' / 'attestations' / 'stable-release-tag-promotion-v7.0.1.json'
PUBLICATION = ROOT / '.pncc-dev' / 'attestations' / 'stable-release-tag-publication-v7.0.1.json'
HISTORICAL = ROOT / '.pncc-dev' / 'attestations' / 'stable-v7.0.0-completion.json'
HISTORICAL_DEFECT = ROOT / '.pncc-dev' / 'attestations' / 'stable-v7.0.0-startup-defect.json'
README = ROOT / 'README.md'
ROADMAP = ROOT / 'docs' / 'roadmap' / 'PNCC_PIPELINE_ROADMAP.md'
LICENSE_DECISION = ROOT / 'LICENSE_DECISION_REQUIRED.md'

EXPECTED = {
    'stable_version': '7.0.1',
    'state': 'STABLE_COMPLETE',
    'runtime_authority': True,
    'tag': 'v7.0.1',
    'tag_target_commit': '41e8c9c8bed2cc37423c33750d0748c49ff941b7',
    'release_name': 'VPS Control PNCC v7.0.1',
    'release_id': 379032537,
    'artifact_filename': 'VPS-Control-v7.0.1.zip',
    'artifact_sha256': '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72',
    'artifact_size_bytes': 701893,
    'release_asset_id': 535416506,
    'release_asset_server_digest': 'sha256:22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72',
    'release_asset_verified': True,
    'physical_startup_acceptance': 'PASS',
    'fresh_nine_scope_reconcile': 'PASS',
    'promotion_state': 'PROMOTED',
    'stable_declared': True,
    'publication_receipt_contract': 'PNCC_STABLE_RELEASE_TAG_PUBLICATION_RECEIPT_V1',
    'stable_main': '0ec71fbac0b2017d19aaa44a7835a3fd6d6604bf',
    'artifact_rebuilt': False,
    'artifact_substituted': False,
    'runtime_mutation': False,
    'product_bytes_mutated': False,
    'runtime_bytes_mutated': False,
    'private_runtime_payload_published': False,
    'reserve_1080_lifecycle_mutation': False,
    'primary_1081_lifecycle_mutation': False,
    'next_frontier': 'WAVE5_ADWF_AUTONOMOUS_EXECUTION',
}


def fail(msg):
    print('POST_STABLE_TRUTH=BLOCKED')
    print('ERROR=' + msg)
    raise SystemExit(2)


def load(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception as exc:
        fail('load_' + path.name + '_' + type(exc).__name__)


def require(text, needle, label):
    if needle not in text:
        fail('missing_' + label)


def forbid(text, needle, label):
    if needle in text:
        fail('stale_' + label)


current = load(CURRENT)
promotion = load(PROMOTION)
publication = load(PUBLICATION)
historical = load(HISTORICAL)
defect = load(HISTORICAL_DEFECT)

for key, value in EXPECTED.items():
    if current.get(key) != value:
        fail('current_' + key)

if promotion.get('promotion_state') != 'PROMOTED' or promotion.get('stable_declared') is not True:
    fail('promotion_not_final')
if promotion.get('target_tag') != EXPECTED['tag'] or promotion.get('target_tag_commit') != EXPECTED['tag_target_commit']:
    fail('promotion_target_identity')
if promotion.get('release_asset_server_digest') != EXPECTED['release_asset_server_digest']:
    fail('promotion_digest')

if publication.get('contract_id') != EXPECTED['publication_receipt_contract'] or publication.get('publication_state') != 'VERIFIED':
    fail('publication_receipt')
if publication.get('release_id') != EXPECTED['release_id'] or publication.get('release_asset_id') != EXPECTED['release_asset_id']:
    fail('publication_provider_identity')
if publication.get('release_asset_server_digest') != EXPECTED['release_asset_server_digest']:
    fail('publication_digest')
if publication.get('independent_download_sha256') != EXPECTED['artifact_sha256'] or publication.get('independent_download_size_bytes') != EXPECTED['artifact_size_bytes']:
    fail('publication_independent_download')
for key in ('artifact_rebuilt','artifact_substituted','runtime_mutation','product_bytes_mutated','runtime_bytes_mutated','private_runtime_payload_published','reserve_1080_lifecycle_mutation','primary_1081_lifecycle_mutation'):
    if publication.get(key) is not False:
        fail('publication_forbidden_' + key)

# Preserve historical truth: v7.0.0 was a real immutable Stable publication, later found to have a startup defect.
if historical.get('stable_version') != '7.0.0' or historical.get('state') != 'STABLE_COMPLETE' or historical.get('tag') != 'v7.0.0':
    fail('historical_v700_completion')
if defect.get('release_version') != '7.0.0' or defect.get('release_history_state') != 'PUBLISHED_IMMUTABLE_KNOWN_STARTUP_DEFECT':
    fail('historical_v700_defect')
if defect.get('supersession_target') != '7.0.1' or defect.get('functional_ui_startup_accepted') is not False:
    fail('historical_v700_supersession')

readme = README.read_text(encoding='utf-8-sig')
roadmap = ROADMAP.read_text(encoding='utf-8-sig')
license_text = LICENSE_DECISION.read_text(encoding='utf-8-sig')

for needle, label in [
    ('Stable v7.0.1 released / physically qualified / current Stable.', 'readme_status'),
    ('`v7.0.1`', 'readme_tag'),
    (EXPECTED['artifact_sha256'], 'readme_sha'),
    ('`701893` bytes', 'readme_size'),
    ('physical startup acceptance: `PASS`', 'readme_startup'),
    ('L4 — Artifact + Runtime Truth', 'readme_l4'),
    ('Wave 5', 'readme_wave5'),
    ('current development frontier', 'readme_frontier'),
]:
    require(readme, needle, label)
for needle, label in [
    ('patch remediation active', 'readme_patch_active'),
    ('expected patch lineage is v7.0.1', 'readme_patch_pending'),
    ('writer-authority expansion is temporarily paused', 'readme_writer_pause'),
]:
    forbid(readme.lower(), needle.lower(), label)

for needle, label in [
    ('Provider-truth reconciliation: 2026-08-29 after Stable v7.0.1 promotion', 'roadmap_reconcile'),
    ('Stable v7.0.1 completed the patch recovery lifecycle', 'roadmap_v701'),
    ('`VPS-Control-v7.0.1.zip`', 'roadmap_artifact'),
    (EXPECTED['artifact_sha256'], 'roadmap_sha'),
    ('ACTIVE / NEXT_FRONTIER', 'roadmap_wave5_active'),
    ('L4 Artifact + Runtime Truth       COMPLETE', 'roadmap_l4'),
    ('L5 Autonomous Work Units          NEXT FRONTIER / Wave 5', 'roadmap_l5'),
]:
    require(roadmap, needle, label)
for needle, label in [
    ('after startup remediation', 'roadmap_after_remediation'),
    ('patch remediation active', 'roadmap_patch_active'),
]:
    forbid(roadmap.lower(), needle.lower(), label)

require(license_text, 'project-wide open-source license is intentionally **not selected yet**', 'license_decision_open')

print('POST_STABLE_TRUTH=PASS')
print('STABLE_VERSION=7.0.1')
print('STABLE_STATE=STABLE_COMPLETE')
print('RUNTIME_AUTHORITY=true')
print('PHYSICAL_STARTUP_ACCEPTANCE=PASS')
print('FRESH_NINE_SCOPE_RECONCILE=PASS')
print('PROMOTION_STATE=PROMOTED')
print('STABLE_DECLARED=true')
print('RELEASE_ASSET_VERIFIED=true')
print('HISTORICAL_V7_0_0_DEFECT_PRESERVED=true')
print('MATURITY=L4_ARTIFACT_RUNTIME_TRUTH')
print('NEXT_FRONTIER=WAVE5_ADWF_AUTONOMOUS_EXECUTION')
print('LICENSE_REVIEW=OPEN')
