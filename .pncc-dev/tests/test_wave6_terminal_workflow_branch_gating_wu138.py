import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WU136 = ROOT / ".github/workflows/wave6-hbe-periodic-health-drift-proposal-wu136.yml"
WU137 = ROOT / ".github/workflows/wave6-hbe-periodic-health-drift-wu137.yml"

WU136_BASELINE_BLOB = "c2c9bf4e8cac667ba073c140f7d0b9d601b9c4e5"
WU137_BASELINE_BLOB = "4ba1ed5abf2b0e25239415290cb147bd97dafaf4"

WU136_GATE = "    if: github.head_ref == 'agent/PIPE-WU-136-wave6-hbe-periodic-health-drift-authority-proposal-preparation'\n"
WU137_OLD_IF = "    if: github.event_name == 'pull_request'\n"
WU137_GATE = "    if: github.event_name == 'pull_request' && github.head_ref == 'agent/PIPE-WU-137-wave6-hbe-periodic-health-drift-activation'\n"


def git_blob_sha(text: str) -> str:
    payload = text.encode("utf-8")
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


class TerminalWorkflowBranchGatingWU138Tests(unittest.TestCase):
    def test_wu136_only_change_is_exact_terminal_branch_gate(self):
        text = WU136.read_text(encoding="utf-8")
        self.assertEqual(text.count(WU136_GATE), 1)
        restored = text.replace(WU136_GATE, "", 1)
        self.assertEqual(git_blob_sha(restored), WU136_BASELINE_BLOB)

    def test_wu137_only_change_is_exact_terminal_branch_gate(self):
        text = WU137.read_text(encoding="utf-8")
        self.assertEqual(text.count(WU137_GATE), 1)
        restored = text.replace(WU137_GATE, WU137_OLD_IF, 1)
        self.assertEqual(git_blob_sha(restored), WU137_BASELINE_BLOB)

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

    def test_successor_branch_does_not_match_terminal_gates(self):
        successor = "agent/PIPE-WU-138-terminal-workflow-branch-gating-ci-noise-remediation"
        self.assertNotEqual(successor, "agent/PIPE-WU-136-wave6-hbe-periodic-health-drift-authority-proposal-preparation")
        self.assertNotEqual(successor, "agent/PIPE-WU-137-wave6-hbe-periodic-health-drift-activation")


if __name__ == "__main__":
    unittest.main()
