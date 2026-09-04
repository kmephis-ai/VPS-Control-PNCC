from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.pncc-dev/scripts/wu200_reproducible_installer_artifact.ps1'
CONTRACT = ROOT / '.pncc-dev/contracts/wave6-wu201-wu200-output-handoff-remediation.json'
WU200_WORKFLOW = ROOT / '.github/workflows/wave6-wu200-reproducible-installer-artifact.yml'


class Wu201OutputHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding='utf-8-sig')
        cls.contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
        cls.wu200_workflow = WU200_WORKFLOW.read_text(encoding='utf-8')

    def test_contract_is_bounded_harness_remediation(self):
        self.assertEqual(self.contract['work_unit_id'], 'PIPE-WU-201')
        self.assertEqual(self.contract['failure_class'], 'HARNESS_OUTPUT_HANDOFF_DEFECT')
        self.assertEqual(self.contract['target']['required_encoding'], 'ASCII_BOM_FREE')
        self.assertEqual(len(self.contract['allowed_mutations']), 5)
        self.assertTrue(all(v is False for v in self.contract['authority'].values()))

    def test_github_output_uses_ascii_encoding(self):
        lines = [line for line in self.script.splitlines() if 'Add-Content' in line and '$githubOutput' in line]
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], r'-Encoding\s+ascii(?:\s|$)')
        self.assertNotRegex(lines[0], r'-Encoding\s+utf8(?:\s|$)')

    def test_all_four_output_keys_remain_present(self):
        for key in ('candidate_path=', 'candidate_sha256=', 'candidate_size=', 'wu199_byte_identical='):
            self.assertEqual(self.script.count(key), 1)

    def test_no_scope_expansion_in_executor(self):
        self.assertIn("$ExpectedCompilerSha256 = '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f'", self.script)
        self.assertIn("$ExpectedIssBlob = 'd30a158aef3535a9066608495b45abcf41112926'", self.script)
        self.assertIn("$CandidateName = 'VPS-Control-PNCC-v7.0.2-setup.exe'", self.script)
        self.assertNotIn('actions/upload-artifact', self.script)

    def test_wu200_exact_diff_is_scoped_to_original_branch(self):
        self.assertIn("github.event.pull_request.head.ref", self.wu200_workflow)
        self.assertIn("agent/PIPE-WU-200-reproducible-installer-artifact", self.wu200_workflow)
        self.assertIn("WU200_ORIGINAL_BOUNDED_DIFF_MISMATCH", self.wu200_workflow)
        self.assertIn("FORBIDDEN_PATH_MUTATION", self.wu200_workflow)
        self.assertIn("UPLOAD_ACTION_COUNT_NOT_ONE", self.wu200_workflow)


if __name__ == '__main__':
    unittest.main()
