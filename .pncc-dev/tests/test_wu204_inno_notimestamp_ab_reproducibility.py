import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'contracts' / 'wave6-wu204-inno-notimestamp-ab-reproducibility.json'
SCRIPT = ROOT / 'scripts' / 'wu204_inno_notimestamp_ab_reproducibility.ps1'
WORKFLOW = ROOT.parent / '.github' / 'workflows' / 'wave6-wu204-inno-notimestamp-ab-reproducibility.yml'


class WU204Tests(unittest.TestCase):
    def test_contract_is_exact_and_least_authority(self):
        c = json.loads(CONTRACT.read_text(encoding='utf-8'))
        self.assertEqual(c['work_unit_id'], 'PIPE-WU-204')
        self.assertEqual(c['source_main_sha'], '62bd3570e1cd1ed1e5db367b7606c9d675ca6bb9')
        self.assertEqual(c['compiler']['tag'], 'is-7_1_0')
        self.assertEqual(c['compiler']['size_bytes'], 14304168)
        self.assertEqual(c['compiler']['sha256'], '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f')
        self.assertEqual(c['installer_definition']['git_blob_sha'], 'd30a158aef3535a9066608495b45abcf41112926')
        self.assertFalse(c['installer_definition']['canonical_mutation_allowed'])
        self.assertNotEqual(c['experiment']['source_mtime_a_utc'], c['experiment']['source_mtime_b_utc'])
        self.assertEqual(c['experiment']['builds'], ['baseline_a', 'baseline_b', 'treatment_a', 'treatment_b'])
        allowed = {'network_acquisition','compiler_ephemeral_installation','compiler_execution','installer_candidate_build','controlled_source_mtime_mutation_in_runner_temp','ephemeral_treatment_definition_materialization'}
        for key, value in c['authority'].items():
            self.assertEqual(value, key in allowed, key)

    def test_script_binds_exact_marker_and_compiler_identity(self):
        s = SCRIPT.read_text(encoding='utf-8-sig')
        for needle in ('PNCC-WU204-AB-EXECUTE','RUNNER_ENVIRONMENT','github-hosted','14304168','0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f','d30a158aef3535a9066608495b45abcf41112926','COMPILER_SIZE_MISMATCH','COMPILER_SHA256_MISMATCH'):
            self.assertIn(needle, s)

    def test_treatment_is_ephemeral_single_change_and_four_builds_are_measured(self):
        s = SCRIPT.read_text(encoding='utf-8-sig')
        self.assertIn("$TreatmentFilesLine = $CanonicalFilesLine + ' notimestamp'", s)
        self.assertIn('TREATMENT_HAS_EXTRA_SEMANTIC_CHANGE', s)
        self.assertIn('CANONICAL_INSTALLER_DEFINITION_MUTATED', s)
        for needle in ('baseline-a','baseline-b','treatment-a','treatment-b','source_file_count','source_mtime_utc','candidate_size_bytes','candidate_sha256','NOTIMESTAMP_EXECUTION_PROVEN_CAUSE_AND_REMEDIATION_FOR_CONTROLLED_MTIME_EXPERIMENT','NOTIMESTAMP_REMEDIATION_NOT_PROVEN'):
            self.assertIn(needle, s)

    def test_no_artifact_publication_or_forbidden_surfaces(self):
        s = SCRIPT.read_text(encoding='utf-8-sig').lower()
        w = WORKFLOW.read_text(encoding='utf-8').lower()
        combined = s + '\n' + w
        self.assertNotIn('actions/upload-artifact', combined)
        self.assertNotIn('actions/cache', combined)
        self.assertNotIn('self-hosted', w)
        self.assertNotIn('candidate_uploaded = $false', s)
        self.assertIn('candidates_uploaded=$false', s.replace(' ', ''))
        self.assertNotIn('git push', combined)
        self.assertNotIn('gh release', combined)

    def test_pr_phase_cannot_execute_experiment(self):
        w = WORKFLOW.read_text(encoding='utf-8')
        for needle in ("github.event_name == 'pull_request'", "github.event_name == 'issues'", 'issue.number == 458', 'PNCC-WU204-AB-EXECUTE', 'wu204_inno_notimestamp_ab_reproducibility.ps1', 'pull_request'):
            self.assertIn(needle, w)


if __name__ == '__main__':
    unittest.main()
