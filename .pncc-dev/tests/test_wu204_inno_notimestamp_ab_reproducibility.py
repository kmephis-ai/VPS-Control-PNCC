import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'contracts' / 'wave6-wu204-inno-notimestamp-ab-reproducibility.json'
SCRIPT = ROOT / 'scripts' / 'wu204_inno_notimestamp_ab_reproducibility.ps1'
WORKFLOW = ROOT.parent / '.github' / 'workflows' / 'wave6-wu204-inno-notimestamp-ab-reproducibility.yml'


def test_contract_is_exact_and_least_authority():
    c = json.loads(CONTRACT.read_text(encoding='utf-8'))
    assert c['work_unit_id'] == 'PIPE-WU-204'
    assert c['source_main_sha'] == '62bd3570e1cd1ed1e5db367b7606c9d675ca6bb9'
    assert c['compiler']['tag'] == 'is-7_1_0'
    assert c['compiler']['size_bytes'] == 14304168
    assert c['compiler']['sha256'] == '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f'
    assert c['installer_definition']['git_blob_sha'] == 'd30a158aef3535a9066608495b45abcf41112926'
    assert c['installer_definition']['canonical_mutation_allowed'] is False
    assert c['experiment']['source_mtime_a_utc'] != c['experiment']['source_mtime_b_utc']
    assert c['experiment']['builds'] == ['baseline_a', 'baseline_b', 'treatment_a', 'treatment_b']
    allowed = {
        'network_acquisition', 'compiler_ephemeral_installation', 'compiler_execution',
        'installer_candidate_build', 'controlled_source_mtime_mutation_in_runner_temp',
        'ephemeral_treatment_definition_materialization'
    }
    for key, value in c['authority'].items():
        assert value is (key in allowed), key


def test_script_binds_exact_marker_and_compiler_identity():
    s = SCRIPT.read_text(encoding='utf-8-sig')
    assert 'PNCC-WU204-AB-EXECUTE' in s
    assert 'RUNNER_ENVIRONMENT' in s and 'github-hosted' in s
    assert '14304168' in s
    assert '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f' in s
    assert 'd30a158aef3535a9066608495b45abcf41112926' in s
    assert 'COMPILER_SIZE_MISMATCH' in s and 'COMPILER_SHA256_MISMATCH' in s


def test_treatment_is_ephemeral_single_change_and_four_builds_are_measured():
    s = SCRIPT.read_text(encoding='utf-8-sig')
    assert "$TreatmentFilesLine = $CanonicalFilesLine + ' notimestamp'" in s
    assert 'TREATMENT_HAS_EXTRA_SEMANTIC_CHANGE' in s
    assert 'CANONICAL_INSTALLER_DEFINITION_MUTATED' in s
    for name in ('baseline-a', 'baseline-b', 'treatment-a', 'treatment-b'):
        assert name in s
    for field in ('source_file_count', 'source_mtime_utc', 'candidate_size_bytes', 'candidate_sha256'):
        assert field in s
    assert 'NOTIMESTAMP_EXECUTION_PROVEN_CAUSE_AND_REMEDIATION_FOR_CONTROLLED_MTIME_EXPERIMENT' in s
    assert 'NOTIMESTAMP_REMEDIATION_NOT_PROVEN' in s


def test_no_artifact_publication_or_forbidden_surfaces():
    s = SCRIPT.read_text(encoding='utf-8-sig').lower()
    w = WORKFLOW.read_text(encoding='utf-8').lower()
    combined = s + '\n' + w
    assert 'actions/upload-artifact' not in combined
    assert 'actions/cache' not in combined
    assert 'self-hosted' not in w
    assert 'candidate_uploaded = $false' not in s  # WU204 uses plural receipt field; catches WU199 copy/paste
    assert 'candidates_uploaded = $false' in s
    assert 'git push' not in combined
    assert 'gh release' not in combined


def test_pr_phase_cannot_execute_experiment():
    w = WORKFLOW.read_text(encoding='utf-8')
    assert "github.event_name == 'pull_request'" in w
    assert "github.event_name == 'issues'" in w
    assert 'issue.number == 458' in w
    assert 'PNCC-WU204-AB-EXECUTE' in w
    assert 'wu204_inno_notimestamp_ab_reproducibility.ps1' in w
    assert 'pull_request' in w
