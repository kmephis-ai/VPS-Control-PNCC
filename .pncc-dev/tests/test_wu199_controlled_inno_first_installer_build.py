import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev/contracts/wave6-wu199-controlled-inno-first-installer-build.json'
SCRIPT = ROOT / '.pncc-dev/scripts/wu199_controlled_inno_first_installer_build.ps1'
WORKFLOW = ROOT / '.github/workflows/wave6-wu199-controlled-inno-first-installer-build.yml'


class WU199ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
        cls.script = SCRIPT.read_text(encoding='utf-8')
        cls.workflow = WORKFLOW.read_text(encoding='utf-8') if WORKFLOW.exists() else ''

    def test_exact_compiler_pin(self):
        c = self.contract['compiler']
        self.assertEqual(c['repository'], 'jrsoftware/issrc')
        self.assertEqual(c['tag'], 'is-7_1_0')
        self.assertEqual(c['release_id'], 369110765)
        self.assertEqual(c['asset_id'], 511336600)
        self.assertEqual(c['size_bytes'], 14304168)
        self.assertEqual(c['sha256'], '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f')

    def test_installer_definition_identity(self):
        d = self.contract['installer_definition']
        self.assertEqual(d['path'], 'installer/windows/VPS-Control-PNCC.iss')
        self.assertEqual(d['git_blob_sha'], 'd30a158aef3535a9066608495b45abcf41112926')
        self.assertEqual(d['expected_output_filename'], 'VPS-Control-PNCC-v7.0.2-setup.exe')

    def test_only_required_authorities_are_true(self):
        authority = self.contract['authority']
        expected_true = {'network_acquisition', 'compiler_installation_ephemeral', 'compiler_execution', 'binary_build'}
        self.assertEqual({k for k, v in authority.items() if v is True}, expected_true)
        for key in ('artifact_upload','cache_write','product_runtime_mutation','release','tag','promotion','stable_transition','ruleset_or_security_weakening','self_hosted_runner','reserve_1080_lifecycle_mutation','primary_1081_lifecycle_mutation','v631_mutation','force_or_bypass'):
            self.assertFalse(authority[key])

    def test_executor_requires_exact_postmerge_marker_and_blob(self):
        self.assertIn('PNCC-WU199-BUILD-EXECUTE', self.script)
        self.assertIn('CHECKOUT_IDENTITY_MISMATCH', self.script)
        self.assertIn('INSTALLER_DEFINITION_BLOB_MISMATCH', self.script)
        self.assertIn('d30a158aef3535a9066608495b45abcf41112926', self.script)
        self.assertNotIn("$ExpectedMain = '4854d6c", self.script)

    def test_executor_deletes_candidate_and_compiler(self):
        self.assertIn('Remove-Item -LiteralPath $candidatePath -Force', self.script)
        self.assertIn('Remove-Item -LiteralPath $compilerSetup -Force', self.script)
        self.assertIn('Remove-Item -LiteralPath $innoDir -Recurse -Force', self.script)
        self.assertIn('candidate_uploaded = $false', self.script)
        self.assertIn('candidate_persisted_after_job = $false', self.script)

    def test_workflow_pr_does_not_build(self):
        if not self.workflow:
            self.skipTest('workflow added after this commit')
        self.assertIn("if: github.event_name == 'pull_request'", self.workflow)
        self.assertIn("if: github.event_name == 'issues'", self.workflow)
        self.assertIn('runs-on: windows-2025', self.workflow)
        self.assertNotRegex(self.workflow, r'uses:\s*actions/upload-artifact@')
        self.assertNotRegex(self.workflow, r'uses:\s*actions/cache@')
        self.assertNotRegex(self.workflow, r'^\s*contents:\s*write\s*$', re.MULTILINE)


if __name__ == '__main__':
    unittest.main()
