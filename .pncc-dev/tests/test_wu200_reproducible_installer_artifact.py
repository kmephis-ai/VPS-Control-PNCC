import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev/contracts/wave6-wu200-reproducible-installer-artifact.json'
SCRIPT = ROOT / '.pncc-dev/scripts/wu200_reproducible_installer_artifact.ps1'
WORKFLOW = ROOT / '.github/workflows/wave6-wu200-reproducible-installer-artifact.yml'

class WU200Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
        cls.script = SCRIPT.read_text(encoding='utf-8-sig')
        cls.workflow = WORKFLOW.read_text(encoding='utf-8')

    def test_exact_identity_and_single_payload(self):
        c = self.contract
        self.assertEqual(c['work_unit_id'], 'PIPE-WU-200')
        self.assertEqual(c['source_main_sha'], '411fd33de7a96e43add073a1fe3c9574e3301176')
        self.assertEqual(c['compiler']['sha256'], '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f')
        self.assertEqual(c['installer_definition']['git_blob_sha'], 'd30a158aef3535a9066608495b45abcf41112926')
        self.assertEqual(c['artifact']['payload_count'], 1)
        self.assertEqual(c['artifact']['payload_filename'], 'VPS-Control-PNCC-v7.0.2-setup.exe')
        self.assertEqual(c['artifact']['retention_days'], 1)

    def test_forbidden_authority_remains_false(self):
        a = self.contract['authority']
        for key in ('release','tag','promotion','stable_transition','product_runtime_mutation','self_hosted_runner','reserve_1080_lifecycle_mutation','primary_1081_lifecycle_mutation','v631_mutation','ruleset_or_security_weakening','force_or_bypass'):
            self.assertFalse(a[key], key)

    def test_execution_is_postmerge_issue_only(self):
        self.assertIn("github.event_name == 'issues'", self.workflow)
        self.assertIn('github.event.issue.number == 450', self.workflow)
        self.assertIn('PNCC-WU200-ARTIFACT-BUILD-EXECUTE', self.workflow)
        self.assertNotIn('workflow_dispatch:', self.workflow)

    def test_upload_is_single_exact_file_and_pinned(self):
        self.assertEqual(self.workflow.count('uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'), 1)
        self.assertIn('VPS-Control-PNCC-v7.0.2-setup.exe', self.workflow)
        self.assertIn('retention-days: 1', self.workflow)
        self.assertIn('compression-level: 0', self.workflow)
        self.assertNotIn('path: ${{ env.RUNNER_TEMP }}', self.workflow)
        self.assertNotIn('actions/cache@', self.workflow)

    def test_script_guards_marker_hash_and_single_output(self):
        for needle in ('EXECUTION_MARKER_AMBIGUOUS','COMPILER_SHA256_MISMATCH','INSTALLER_DEFINITION_BLOB_MISMATCH','ARTIFACT_PAYLOAD_NOT_SINGLE_EXACT_CANDIDATE','WU199_REPRODUCIBILITY_MISMATCH'):
            self.assertIn(needle, self.script)

    def test_github_output_transport_is_distinct_ascii_lines(self):
        self.assertIn('[System.IO.File]::AppendAllText', self.script)
        self.assertIn('[System.Text.Encoding]::ASCII', self.script)
        self.assertIn('[Environment]::NewLine', self.script)
        self.assertNotIn("@('candidate_path='", self.script)
        for name in ('candidate_path','candidate_sha256','candidate_size','wu199_byte_identical'):
            self.assertEqual(self.script.count("Write-GitHubOutputLine '" + name + "'"), 1)

    def test_reproducibility_is_required_before_upload(self):
        self.assertIn("steps.build.outputs.wu199_byte_identical == 'true'", self.workflow)
        self.assertIn("steps.build.outputs.candidate_size == '2230935'", self.workflow)
        self.assertIn("steps.build.outputs.candidate_sha256 == '13ea7db85ce1c997f1bcc9566c615c1000eeaf33909a208ab6207f4e5ba22f06'", self.workflow)
        self.assertIn("artifact_upload_authorized = $byteIdentical", self.script)
        self.assertIn("if: always()", self.workflow)

    def test_no_release_or_runtime_write_paths(self):
        combined = self.script + '\n' + self.workflow
        for needle in ('gh release','git tag','src/windows-v7/', '127.0.0.1:1080', '127.0.0.1:1081'):
            self.assertNotIn(needle, combined)

if __name__ == '__main__':
    unittest.main()
