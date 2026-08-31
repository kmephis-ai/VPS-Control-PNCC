import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WU136 = ROOT / ".github/workflows/wave6-hbe-periodic-health-drift-proposal-wu136.yml"
WU137 = ROOT / ".github/workflows/wave6-hbe-periodic-health-drift-wu137.yml"

WU136_BASELINE_BLOB = "c2c9bf4e8cac667ba073c140f7d0b9d601b9c4e5"
WU137_BASELINE_BLOB = "4ba1ed5abf2b0e25239415290cb147bd97dafaf4"

WU136_BRANCH = "agent/PIPE-WU-136-wave6-hbe-periodic-health-drift-authority-proposal-preparation"
WU137_BRANCH = "agent/PIPE-WU-137-wave6-hbe-periodic-health-drift-activation"
WU138_BRANCH = "agent/PIPE-WU-138-terminal-workflow-branch-gating-ci-noise-remediation"

WU136_GATE = f"    if: github.head_ref == '{WU136_BRANCH}'\n"
WU137_OLD_IF = "    if: github.event_name == 'pull_request'\n"
WU137_GATE = f"    if: github.event_name == 'pull_request' && github.head_ref == '{WU137_BRANCH}'\n"

WU136_SUCCESSOR_JOB = f"""
  successor-pr-regression:
    if: github.head_ref != '{WU136_BRANCH}'
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - name: Checkout exact successor PR head
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
          persist-credentials: false

      - name: Run WU138 branch-gating regression when canonical
        shell: bash
        run: |
          set -euo pipefail
          test_path='.pncc-dev/tests/test_wave6_terminal_workflow_branch_gating_wu138.py'
          if [ -f "$test_path" ]; then
            python3 -m unittest discover -s .pncc-dev/tests -p 'test_wave6_terminal_workflow_branch_gating_wu138.py' -v
          else
            echo 'WU138 regression is not present on this historical successor; terminal WU136 validator is correctly non-applicable.'
          fi
"""

WU137_SUCCESSOR_JOB = f"""  successor-pr-noop:
    if: github.event_name == 'pull_request' && github.head_ref != '{WU137_BRANCH}'
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - name: Confirm terminal WU137 validator is not applicable
        run: echo 'WU137 terminal activation validator is branch-gated; scheduled health/drift monitoring is unchanged.'

"""


def git_blob_sha(text: str) -> str:
    payload = text.encode("utf-8")
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


class TerminalWorkflowBranchGatingWU138Tests(unittest.TestCase):
    def test_wu136_only_changes_are_gate_and_successor_regression_job(self):
        text = WU136.read_text(encoding="utf-8")
        self.assertEqual(text.count(WU136_GATE), 1)
        self.assertEqual(text.count("  successor-pr-regression:\n"), 1)
        restored = text.replace(WU136_GATE, "", 1).replace(WU136_SUCCESSOR_JOB, "", 1)
        self.assertEqual(git_blob_sha(restored), WU136_BASELINE_BLOB)

    def test_wu137_only_changes_are_gate_and_successor_noop_job(self):
        text = WU137.read_text(encoding="utf-8")
        self.assertEqual(text.count(WU137_GATE), 1)
        self.assertEqual(text.count("  successor-pr-noop:\n"), 1)
        restored = text.replace(WU137_GATE, WU137_OLD_IF, 1).replace(WU137_SUCCESSOR_JOB, "", 1)
        self.assertEqual(git_blob_sha(restored), WU137_BASELINE_BLOB)

    def test_successor_prs_finish_successfully_instead_of_skipping_terminal_workflows(self):
        wu136 = WU136.read_text(encoding="utf-8")
        wu137 = WU137.read_text(encoding="utf-8")
        self.assertIn(f"if: github.head_ref != '{WU136_BRANCH}'", wu136)
        self.assertIn("Run WU138 branch-gating regression when canonical", wu136)
        self.assertIn(f"if: github.event_name == 'pull_request' && github.head_ref != '{WU137_BRANCH}'", wu137)
        self.assertIn("Confirm terminal WU137 validator is not applicable", wu137)
        self.assertNotEqual(WU138_BRANCH, WU136_BRANCH)
        self.assertNotEqual(WU138_BRANCH, WU137_BRANCH)

    def test_wu137_periodic_monitor_contract_remains_exact(self):
        text = WU137.read_text(encoding="utf-8")
        self.assertIn("  schedule:\n    - cron: '17 * * * *'\n", text)
        self.assertIn("  contents: read\n  issues: read\n  pull-requests: read\n  actions: read\n  checks: read\n", text)
        self.assertIn("  periodic-health-drift:\n    if: github.event_name == 'schedule'\n", text)
        self.assertNotIn("workflow_dispatch:", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("issues: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("actions: write", text)
        self.assertNotIn("checks: write", text)


if __name__ == "__main__":
    unittest.main()
