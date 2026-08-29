#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATT = ROOT / '.pncc-dev' / 'attestations' / 'stable-v7.0.0-completion.json'
DEFECT_ATT = ROOT / '.pncc-dev' / 'attestations' / 'stable-v7.0.0-startup-defect.json'
README = ROOT / 'README.md'
ROADMAP = ROOT / 'docs' / 'roadmap' / 'PNCC_PIPELINE_ROADMAP.md'
LICENSE_DECISION = ROOT / 'LICENSE_DECISION_REQUIRED.md'

EXPECTED = {
    'stable_version': '7.0.0',
    'state': 'STABLE_COMPLETE',
    'runtime_authority': True,
    'tag': 'v7.0.0',
    'tag_target_commit': 'd889b52879fd21612f639cb2441fbd1ff8bc3f02',
    'release_name': 'VPS Control PNCC v7.0.0',
    'artifact_filename': 'VPS-Control-v7.0.0.zip',
    'artifact_sha256': '1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599',
    'artifact_size_bytes': 700897,
    'release_asset_verified': True,
    'fresh_nine_scope_reconcile': 'PASS',
    'artifact_rebuilt': False,
    'artifact_substituted': False,
    'runtime_mutation': False,
    'product_bytes_mutated': False,
    'runtime_bytes_mutated': False,
}

EXPECTED_DEFECT = {
    'schema_version': 1,
    'role': 'STABLE_RELEASE_DEFECT_ATTESTATION',
    'release_version': '7.0.0',
    'tag': 'v7.0.0',
    'artifact_filename': 'VPS-Control-v7.0.0.zip',
    'artifact_sha256': '1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599',
    'artifact_size_bytes': 700897,
    'artifact_identity_verified': True,
    'release_history_state': 'PUBLISHED_IMMUTABLE_KNOWN_STARTUP_DEFECT',
    'classification': 'PRODUCT_DEFECT_STARTUP_BLOCKING_FALSE_POSITIVE_CONSISTENCY_GATE',
    'affected_gate': 'CONSISTENCY_MARKER_STRICTMODE_SAFE',
    'root_cause': 'GREEDY_SOURCE_REGEX_CROSSES_CONTAINS_CALL_BOUNDARIES',
    'functional_ui_startup_accepted': False,
    'runtime_engine_evidence_invalidated': False,
    'fresh_nine_scope_runtime_reconcile_historical_result': 'PASS',
    'runtime_mutation_observed': False,
    'reserve_1080_mutation_observed': False,
    'primary_1081_mutation_observed': False,
    'release_asset_mutation_allowed': False,
    'release_tag_retarget_allowed': False,
    'remediation_work_unit': 'PIPE-WU-080',
    'remediation_issue': 190,
    'supersession_target': '7.0.1',
    'patch_startup_acceptance_contract': '.pncc-dev/contracts/patch-release-startup-acceptance-policy.json',
}


def fail(msg):
    print('POST_STABLE_TRUTH=BLOCKED')
    print('ERROR=' + msg)
    raise SystemExit(2)


def require(text, needle, label):
    if needle not in text:
        fail('missing_' + label)


def forbid(text, needle, label):
    if needle in text:
        fail('stale_' + label)


try:
    att = json.loads(ATT.read_text(encoding='utf-8-sig'))
except Exception as exc:
    fail('attestation_load_' + type(exc).__name__)

for key, value in EXPECTED.items():
    if att.get(key) != value:
        fail('attestation_' + key)

try:
    defect = json.loads(DEFECT_ATT.read_text(encoding='utf-8-sig'))
except Exception as exc:
    fail('defect_attestation_load_' + type(exc).__name__)

if set(defect) != set(EXPECTED_DEFECT):
    fail('defect_attestation_schema')
for key, value in EXPECTED_DEFECT.items():
    if defect.get(key) != value:
        fail('defect_attestation_' + key)

readme = README.read_text(encoding='utf-8-sig')
roadmap = ROADMAP.read_text(encoding='utf-8-sig')
license_text = LICENSE_DECISION.read_text(encoding='utf-8-sig')

for needle, label in [
    ('Stable v7.0.0 released / immutable / known startup UI defect; patch remediation active.', 'readme_stable_status'),
    ('`v7.0.0`', 'readme_tag'),
    (EXPECTED['artifact_sha256'], 'readme_sha'),
    ('`700897` bytes', 'readme_size'),
    ('KNOWN_DEFECT / FAIL', 'readme_startup_defect'),
    ('L4 — Artifact + Runtime Truth', 'readme_l4'),
    ('Wave 5', 'readme_wave5'),
    ('expected patch lineage is v7.0.1', 'readme_patch_line'),
]:
    require(readme, needle, label)

for needle, label in [
    ('Public bootstrap / migration in progress.', 'readme_bootstrap'),
    ('Current migration candidate tracked outside GitHub source import', 'readme_old_candidate'),
]:
    forbid(readme, needle, label)

for needle, label in [
    ('COMPLETE / ARTIFACT_TRUTH_PROVEN', 'roadmap_wave3_complete'),
    ('COMPLETE / L4_ARTIFACT_RUNTIME_TRUTH', 'roadmap_wave4_complete'),
    ('ACTIVE / NEXT_FRONTIER', 'roadmap_wave5_active'),
    ('L4 Artifact + Runtime Truth       COMPLETE', 'roadmap_l4_current'),
    (EXPECTED['artifact_sha256'], 'roadmap_sha'),
    ('Project-wide license selection remains deferred', 'roadmap_license_residual'),
]:
    require(roadmap, needle, label)

for needle, label in [
    ('ACTIVE / BUILD_INPUT_READINESS', 'roadmap_old_wave3_state'),
    ('L3 Tested Engineering Pipeline ← current verified maturity', 'roadmap_old_maturity'),
]:
    forbid(roadmap, needle, label)

require(license_text, 'project-wide open-source license is intentionally **not selected yet**', 'license_decision_open')

print('POST_STABLE_TRUTH=PASS')
print('STABLE_VERSION=7.0.0')
print('RUNTIME_AUTHORITY=true')
print('V7_0_0_UI_STARTUP_ACCEPTED=false')
print('V7_0_0_RELEASE_HISTORY=PUBLISHED_IMMUTABLE_KNOWN_STARTUP_DEFECT')
print('PATCH_TARGET=7.0.1')
print('WAVE3=COMPLETE')
print('WAVE4=COMPLETE')
print('MATURITY=L4_ARTIFACT_RUNTIME_TRUTH')
print('NEXT_FRONTIER=WAVE5_ADWF_AUTONOMOUS_EXECUTION_AFTER_STARTUP_REMEDIATION')
print('LICENSE_REVIEW=OPEN')
