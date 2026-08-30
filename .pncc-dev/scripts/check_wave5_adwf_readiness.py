#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BINDING = ROOT / '.adwf-consumer' / 'external-binding.json'
READINESS = ROOT / '.adwf-consumer' / 'wave5-readiness.json'
STABLE = ROOT / '.pncc-dev' / 'attestations' / 'stable-v7.0.1-completion.json'
ADWF_WORKFLOW = ROOT / '.github' / 'workflows' / 'adwf-binding.yml'
PACK_MARKER = ROOT / '.adwf-powershell.json'

EXPECTED_ADWF = '8253701aa261d6ddcdfece15f355e407a2de44ef'
EXPECTED_PACK = 'fbe69c4e93ff8b07e7d0dc6f0cbd1f9ceb80617f472f1fbe5a1ce181279a0c8c'
EXPECTED_PACK_BLOB = 'b4ad2f2459079039a59c3e687ea269d2c6ca73fe'
EXPECTED_SCHEMA_BLOB = 'c3762053920076ea1ac9ba1865cbfacb6fdcf0c0'
EXPECTED_STABLE = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
EXPECTED_BINDING_SHA = '51602edd8b2a6ee5c5a4e201b46d6b4edfa150600f1e333d474043b456518dc0'
EXPECTED_BINDING_BLOB = 'ede4882b81ba631d45c25be9541fcaed4228fef0'
EXPECTED_GATES = ['repo-integrity', 'powershell-static', 'truth-contract']


def fail(msg):
    print('WAVE5_ADWF_READINESS=BLOCKED')
    print('ERROR=' + msg)
    print('MUTATION_AUTHORITY=NONE_BINDING_IS_PROOF_ONLY')
    print('AUTONOMY_ENABLED=false')
    raise SystemExit(2)


def load(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception as exc:
        fail(path.name + '_load_' + type(exc).__name__)
    if not isinstance(value, dict):
        fail(path.name + '_object_required')
    return value


def canonical_sha(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


if (ROOT / '.adwf').exists():
    fail('managed_surface_forbidden')

binding = load(BINDING)
readiness = load(READINESS)
stable = load(STABLE)
marker = load(PACK_MARKER)
workflow = ADWF_WORKFLOW.read_text(encoding='utf-8-sig')

if stable.get('stable_version') != '7.0.1' or stable.get('state') != 'STABLE_COMPLETE' or stable.get('runtime_authority') is not True:
    fail('stable_completion_missing')
if stable.get('artifact_filename') != 'VPS-Control-v7.0.1.zip' or stable.get('artifact_sha256') != EXPECTED_STABLE or stable.get('artifact_size_bytes') != 701893:
    fail('stable_artifact_identity')
if stable.get('physical_startup_acceptance') != 'PASS' or stable.get('fresh_nine_scope_reconcile') != 'PASS':
    fail('stable_physical_evidence')
if stable.get('release_asset_verified') is not True or stable.get('promotion_state') != 'PROMOTED' or stable.get('stable_declared') is not True:
    fail('stable_release_authority')
if stable.get('next_frontier') != 'WAVE5_ADWF_AUTONOMOUS_EXECUTION':
    fail('stable_next_frontier')
for key in ('artifact_rebuilt','artifact_substituted','runtime_mutation','product_bytes_mutated','runtime_bytes_mutated','private_runtime_payload_published','reserve_1080_lifecycle_mutation','primary_1081_lifecycle_mutation'):
    if stable.get(key) is not False:
        fail('stable_forbidden_' + key)

if binding.get('role') != 'EXTERNAL_CONSUMER_BINDING' or binding.get('schema_version') != 1:
    fail('binding_contract')
if binding.get('framework') != {'repository': 'kmephis-ai/AI-Development-Framework', 'source_sha': EXPECTED_ADWF}:
    fail('framework_pin')
if binding.get('consumer') != {'repository': 'kmephis-ai/VPS-Control-PNCC', 'default_branch': 'main'}:
    fail('consumer_identity')
if binding.get('project_pack') != {'id': 'powershell', 'digest': EXPECTED_PACK}:
    fail('project_pack')
if binding.get('safety') != {'monetary_budget_usd': 0, 'secrets': 'FORBIDDEN'}:
    fail('binding_safety')
if binding.get('mutation_authority') != 'NONE_BINDING_IS_PROOF_ONLY':
    fail('binding_mutation_authority')

unsigned = {k: v for k, v in binding.items() if k != 'binding_sha256'}
if canonical_sha(unsigned) != EXPECTED_BINDING_SHA or binding.get('binding_sha256') != EXPECTED_BINDING_SHA:
    fail('binding_digest')

for phase in ('pr', 'main'):
    gates = binding.get('native_gates', {}).get(phase)
    if not isinstance(gates, list):
        fail('native_gates_' + phase)
    names = [item.get('check_name') for item in gates]
    if names != EXPECTED_GATES:
        fail('native_gates_' + phase + '_drift')
    for item in gates:
        if item.get('app_slug') != 'github-actions' or item.get('app_id') != 15368:
            fail('native_gate_app_identity')

if marker != {'schema_version': 1, 'role': 'ADWF_PROJECT_PACK_MARKER', 'project_pack': 'powershell'}:
    fail('pack_marker')

if readiness.get('role') != 'PNCC_WAVE5_ADWF_PROOF_READINESS' or readiness.get('state') != 'WAVE5_ADWF_PROOF_BASELINE_READY':
    fail('readiness_state')
expected_baseline = {
    'version': '7.0.1',
    'completion_attestation': '.pncc-dev/attestations/stable-v7.0.1-completion.json',
    'completion_state': 'STABLE_COMPLETE',
    'runtime_authority': True,
    'artifact_filename': 'VPS-Control-v7.0.1.zip',
    'artifact_sha256': EXPECTED_STABLE,
    'artifact_size_bytes': 701893,
}
if readiness.get('stable_baseline') != expected_baseline:
    fail('readiness_stable_baseline')
if readiness.get('framework', {}).get('source_sha') != EXPECTED_ADWF:
    fail('readiness_framework_pin')
if readiness.get('framework', {}).get('powershell_pack_blob_sha') != EXPECTED_PACK_BLOB:
    fail('readiness_pack_blob')
if readiness.get('framework', {}).get('external_binding_schema_blob_sha') != EXPECTED_SCHEMA_BLOB:
    fail('readiness_schema_blob')
if readiness.get('consumer', {}).get('project_pack_digest') != EXPECTED_PACK:
    fail('readiness_pack_digest')
if readiness.get('consumer', {}).get('mutation_authority') != 'NONE_BINDING_IS_PROOF_ONLY':
    fail('readiness_mutation_authority')
if readiness.get('consumer', {}).get('managed_surface_adopted') is not False:
    fail('managed_surface_adoption')
if readiness.get('framework', {}).get('provider_ops_stage1_present') is not True:
    fail('provider_ops_visibility')
if readiness.get('framework', {}).get('provider_ops_consumer_authority_granted') is not False:
    fail('provider_ops_authority')

snapshot = readiness.get('provider_ruleset_snapshot', {})
if snapshot.get('ruleset_id') != 21585301 or snapshot.get('enforcement') != 'active':
    fail('ruleset_snapshot_identity')
if snapshot.get('required_status_checks') != EXPECTED_GATES:
    fail('ruleset_snapshot_gates')
if snapshot.get('adwf_binding_required') is not False or snapshot.get('adwf_binding_required_tracking_issue') != 15:
    fail('ruleset_adwf_binding_boundary')

safety = readiness.get('safety', {})
if safety.get('monetary_budget_usd') != 0 or safety.get('secrets') != 'FORBIDDEN':
    fail('readiness_safety')
for key in (
    'autonomous_branch_mutation', 'autonomous_merge', 'autonomous_issue_close',
    'runtime_action_authority', 'promotion_authority', 'release_or_tag_authority',
    'ruleset_or_policy_mutation'
):
    if safety.get(key) is not False:
        fail('forbidden_authority_' + key)

if readiness.get('next_boundary') != 'BOUNDED_PROVIDER_TRUTH_READ_ONLY_ORCHESTRATION_DESIGN':
    fail('next_boundary')

if workflow.count(EXPECTED_ADWF) != 2:
    fail('adwf_workflow_pin')
if workflow.count(EXPECTED_PACK_BLOB) != 1:
    fail('adwf_workflow_pack_blob_pin')
if workflow.count(EXPECTED_SCHEMA_BLOB) != 1:
    fail('adwf_workflow_schema_blob_pin')
if 'contents: read' not in workflow:
    fail('adwf_workflow_read_permission')
for token in ('contents: write', 'git push', 'git tag', 'gh release'):
    if token in workflow.lower():
        fail('adwf_workflow_forbidden_' + token.replace(' ', '_'))

print('WAVE5_ADWF_READINESS=PASS')
print('STATE=WAVE5_ADWF_PROOF_BASELINE_READY')
print('STABLE_VERSION=7.0.1')
print('STABLE_ARTIFACT_SHA256=' + EXPECTED_STABLE)
print('PHYSICAL_STARTUP_ACCEPTANCE=PASS')
print('FRESH_NINE_SCOPE_RECONCILE=PASS')
print('ADWF_SOURCE_SHA=' + EXPECTED_ADWF)
print('PROJECT_PACK=powershell')
print('EXTERNAL_BINDING_EXPECTED_BLOB=' + EXPECTED_BINDING_BLOB)
print('MUTATION_AUTHORITY=NONE_BINDING_IS_PROOF_ONLY')
print('AUTONOMY_ENABLED=false')
print('PROVIDER_OPS_CONSUMER_AUTHORITY=false')
print('NEXT_BOUNDARY=BOUNDED_PROVIDER_TRUTH_READ_ONLY_ORCHESTRATION_DESIGN')
