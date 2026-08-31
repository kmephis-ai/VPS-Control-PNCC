import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/wave5-autonomous-continuation-execution-admission.yml"
WU108_WORKFLOW = ROOT / ".github/workflows/wave5-autonomous-continuation-control-loop.yml"


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class WU140TerminalValidatorRegressionTests(unittest.TestCase):
    def test_wu109_policy_evaluator_and_tests_are_byte_identical(self):
        expected = {
            ".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json": "406d78da6250c452bfc7706b57dc51a18ca48977",
            ".pncc-dev/scripts/evaluate_autonomous_continuation_execution_admission.py": "cde13515632717b81cef77876e53e9ceef0c46bf",
            ".pncc-dev/tests/test_autonomous_continuation_execution_admission_wu109.py": "790ad4cab98a707a438b53bdbfe03267589adc15",
        }
        for rel, sha in expected.items():
            self.assertEqual(blob_sha(ROOT / rel), sha, rel)

    def test_wu108_post_wu139_harness_is_unchanged_by_wu140(self):
        self.assertEqual(blob_sha(WU108_WORKFLOW), "37a9ef9ddfaa74884b5a2ec8e949f11ff715a07e")
        self.assertEqual(blob_sha(ROOT / ".pncc-dev/contracts/autonomous-continuation-control-loop-policy.json"), "822bcd1833ff4843b6bd176337b3ef3b742275de")
        self.assertEqual(blob_sha(ROOT / ".pncc-dev/scripts/evaluate_autonomous_continuation_control_loop.py"), "1f794892cfec466505a1a6c38b271492f9759127")

    def test_historical_exact_anchor_step_is_branch_gated(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        marker = "      - name: Assert exact admission anchors\n        if: github.event_name == 'pull_request' && startsWith(github.head_ref, 'agent/PIPE-WU-109-')\n"
        self.assertIn(marker, text)

    def test_successor_pr_still_runs_non_mutating_admission_validation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Run WU-109 adversarial admission tests", text)
        self.assertIn("Assert upstream live control-loop harness is Work-Unit generic", text)
        self.assertIn("Assert workflow and admission remain read only", text)
        self.assertIn("Assert repository remains clean", text)

    def test_pre_wu140_workflow_reconstructs_exact_baseline_blob(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        inserted_test = "\n      - name: Run WU140 terminal-validator regression\n        run: python3 -m unittest discover -s .pncc-dev/tests -p 'test_autonomous_continuation_execution_admission_terminal_validator_wu140.py' -v\n"
        inserted_if = "        if: github.event_name == 'pull_request' && startsWith(github.head_ref, 'agent/PIPE-WU-109-')\n"
        self.assertIn(inserted_test, text)
        self.assertIn(inserted_if, text)
        baseline = text.replace(inserted_test, "", 1).replace(inserted_if, "", 1).encode("utf-8")
        sha = hashlib.sha1(f"blob {len(baseline)}\0".encode("ascii") + baseline).hexdigest()
        self.assertEqual(sha, "61cbf382ad96016db377e34bc08f5bf7c2feb15c")

    def test_permissions_and_mutation_authority_are_not_broadened(self):
        text = WORKFLOW.read_text(encoding="utf-8").lower()
        for token in (
            "contents: write", "actions: write", "issues: write", "pull-requests: write",
            "git push", "gh pr merge", "gh issue close", "--method post", "--method patch",
            "--method put", "--method delete",
        ):
            self.assertNotIn(token, text, token)


if __name__ == "__main__":
    unittest.main()
