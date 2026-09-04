from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev/contracts/wave6-wu202-wu200-output-transport-reproducibility-guard.json'
SCRIPT = ROOT / '.pncc-dev/scripts/wu200_reproducible_installer_artifact.ps1'
WU200_WORKFLOW = ROOT / '.github/workflows/wave6-wu200-reproducible-installer-artifact.yml'
WU201_WORKFLOW = ROOT / '.github/workflows/wave6-wu201-wu200-output-handoff-remediation.yml'

class Wu202Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
        cls.script = SCRIPT.read_text(encoding='utf-8-sig')
        cls.wu200 = WU200_WORKFLOW.read_text(encoding='utf-8')
        cls.wu201 = WU201_WORKFLOW.read_text(encoding='utf-8')

    def test_contract_records_exact_observed_failure_and_no_publication_authority(self):
        c = self.contract
        self.assertEqual(c['work_unit_id'], 'PIPE-WU-202')
        self.assertEqual(c['source_main_sha'], 'ceb649ae1f5c4c65614fb9db02d716ea71087b7c')
        self.assertEqual(c['observed_run_id'], 33899651324)
        self.assertEqual(c['observed_nonreproducible_candidate']['size_bytes'], 2230934)
        self.assertEqual(c['observed_nonreproducible_candidate']['sha256'], 'b2a7cd7e00d5e8861255680c2b5e79f241d8721ac8636a2e6f5c542ed0f11851')
        self.assertFalse(c['observed_nonreproducible_candidate']['artifact_uploaded'])
        self.assertTrue(all(v is False for v in c['authority'].values()))
        self.assertEqual(len(c['allowed_mutations']), 8)

    def test_output_transport_is_four_distinct_ascii_lines(self):
        self.assertIn('[System.IO.File]::AppendAllText', self.script)
        self.assertIn('[System.Text.Encoding]::ASCII', self.script)
        self.assertIn('[Environment]::NewLine', self.script)
        self.assertNotIn("@('candidate_path='", self.script)
        for key in ('candidate_path','candidate_sha256','candidate_size','wu199_byte_identical'):
            self.assertEqual(self.script.count("Write-GitHubOutputLine '" + key + "'"), 1)

    def test_mismatch_is_deleted_then_fails_closed(self):
        self.assertIn("if (-not $byteIdentical)", self.script)
        self.assertIn("Remove-Item -LiteralPath $outputDir -Recurse -Force", self.script)
        self.assertIn("WU199_REPRODUCIBILITY_MISMATCH", self.script)
        self.assertIn("artifact_upload_authorized = $byteIdentical", self.script)

    def test_upload_has_exact_identity_guards(self):
        guard = "if: steps.build.outputs.wu199_byte_identical == 'true' && steps.build.outputs.candidate_size == '2230935' && steps.build.outputs.candidate_sha256 == '13ea7db85ce1c997f1bcc9566c615c1000eeaf33909a208ab6207f4e5ba22f06'"
        self.assertIn(guard, self.wu200)
        self.assertIn("WU199_BYTE_IDENTITY_NOT_PROVEN", self.wu200)
        self.assertIn("WU199_SIZE_IDENTITY_NOT_PROVEN", self.wu200)
        self.assertIn("WU199_SHA256_IDENTITY_NOT_PROVEN", self.wu200)
        self.assertEqual(self.wu200.count('uses: actions/upload-artifact@'), 1)

    def test_cleanup_is_always_and_maintenance_gates_are_scoped(self):
        self.assertIn("- name: Delete local candidate and ephemeral compiler state\n        if: always()", self.wu200)
        self.assertIn("WU200_ORIGINAL_BOUNDED_DIFF_MISMATCH", self.wu200)
        self.assertIn("WU201_ORIGINAL_BOUNDED_DIFF_MISMATCH", self.wu201)
        self.assertIn("agent/PIPE-WU-201-wu200-output-handoff-remediation", self.wu201)

    def test_identity_and_forbidden_surfaces_unchanged(self):
        combined = self.script + '\n' + self.wu200 + '\n' + self.wu201
        self.assertIn("$ExpectedCompilerSha256 = '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f'", self.script)
        self.assertIn("$ExpectedIssBlob = 'd30a158aef3535a9066608495b45abcf41112926'", self.script)
        for needle in ('gh release','git tag','src/windows-v7/', '127.0.0.1:1080', '127.0.0.1:1081', 'self-hosted', 'actions/cache@'):
            self.assertNotIn(needle, combined)

if __name__ == '__main__':
    unittest.main()
