#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pncc_wu133_validator",
    ROOT / ".pncc-dev/scripts/validate_wave5_terminal_maturity_reconciliation_wu133.py",
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class Wave5TerminalMaturityReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(mod.EVIDENCE.read_text(encoding="utf-8"))

    def test_evidence_is_fully_valid(self):
        self.assertEqual(mod.validate(self.data), [])

    def test_all_five_exit_criteria_are_proven(self):
        criteria = self.data["wave5_exit_criteria"]
        self.assertEqual({item["id"] for item in criteria}, mod.EXPECTED_CRITERIA)
        self.assertTrue(all(item["status"] == "PROVEN" for item in criteria))

    def test_waiting_runtime_is_proven_without_runtime_action(self):
        criterion = next(item for item in self.data["wave5_exit_criteria"] if item["id"] == "DURABLE_WAITING_RUNTIME")
        self.assertIn("no-mutation", criterion["fact"])
        continuation = json.loads((ROOT / ".pncc-dev/contracts/provider-truth-continuation-policy.json").read_text(encoding="utf-8"))
        self.assertEqual(continuation["waiting_runtime_policy"], "WAIT_WITHOUT_MUTATION")
        self.assertIn("WAITING_RUNTIME", continuation["decisions"])
        self.assertFalse(continuation["runtime_action_authority"])

    def test_higher_authority_is_not_inferred_from_wave5_completion(self):
        self.assertFalse(self.data["authority_granted"])
        self.assertFalse(self.data["higher_autonomy_authorized"])
        proposal = self.data["post_wave5_frontier_proposal"]
        self.assertEqual(proposal["proposal_state"], "NON_AUTHORIZING_PROPOSAL_ONLY")
        self.assertFalse(proposal["materialized"])
        self.assertFalse(proposal["authority_granted"])
        self.assertTrue(proposal["requires_explicit_owner_authorization"])

    def test_terminal_frontier_and_immutable_anchors_remain_exact(self):
        provider = self.data["provider_truth"]
        frontier = ROOT / provider["frontier_path"]
        self.assertEqual(json.loads(frontier.read_text(encoding="utf-8")), mod.EXPECTED_FRONTIER)
        self.assertEqual(mod.git_blob_sha(frontier), provider["frontier_blob_sha"])
        for rel, expected in self.data["anchor_impact"]["immutable_anchor_expectations"].items():
            self.assertEqual(mod.git_blob_sha(ROOT / rel), expected)

    def test_product_runtime_and_sensitive_boundaries_remain_untouched(self):
        self.assertFalse(self.data["runtime_authority_claimed"])
        self.assertFalse(self.data["stable_or_promotion_claimed"])
        self.assertTrue(all(value is False for value in self.data["forbidden_mutations"].values()))


if __name__ == "__main__":
    unittest.main()
