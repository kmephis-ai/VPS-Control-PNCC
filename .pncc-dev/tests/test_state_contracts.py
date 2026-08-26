from __future__ import annotations

from pathlib import Path
import copy
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pncc_state_validator", ROOT / ".pncc-dev/scripts/validate_state.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class DurableStateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        examples = ROOT / ".pncc-dev/examples"
        cls.work = mod.load_json(examples / "work-unit.valid.json")
        cls.checkpoint = mod.load_json(examples / "session-checkpoint.valid.json")
        cls.runtime = mod.load_json(examples / "runtime-ledger.valid.json")
        cls.evidence = mod.load_json(examples / "evidence-index.valid.json")

    def assertBlocked(self, callable_):
        with self.assertRaises(mod.ContractError):
            callable_()

    def test_valid_examples_and_schema_documents(self):
        mod.validate_examples(ROOT)

    def test_done_work_unit_requires_exact_subject_and_evidence(self):
        value = copy.deepcopy(self.work)
        value["state"] = "DONE"
        self.assertBlocked(lambda: mod.validate_work_unit(value))
        value["subject_sha"] = "3" * 40
        self.assertBlocked(lambda: mod.validate_work_unit(value))
        value["evidence_refs"] = ["evidence-1"]
        mod.validate_work_unit(value)

    def test_stale_checkpoint_head_fails_closed(self):
        provider = {
            "head_known": True,
            "head_sha": "9" * 40,
            "branch": self.checkpoint["branch"],
            "pr": self.checkpoint["pr"],
            "pr_state": "OPEN",
            "checks": dict(self.checkpoint["provider_snapshot"]["checks"]),
        }
        result = mod.reconcile_checkpoint(self.checkpoint, provider)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("STALE_CHECKPOINT_HEAD", result["reasons"])

    def test_unknown_provider_head_fails_closed(self):
        provider = {
            "head_known": False,
            "head_sha": self.checkpoint["recorded_subject_sha"],
            "branch": self.checkpoint["branch"],
            "pr": self.checkpoint["pr"],
            "pr_state": "OPEN",
            "checks": dict(self.checkpoint["provider_snapshot"]["checks"]),
        }
        result = mod.reconcile_checkpoint(self.checkpoint, provider)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PROVIDER_HEAD_UNKNOWN", result["reasons"])

    def test_fresh_provider_truth_allows_resume(self):
        provider = {
            "head_known": True,
            "head_sha": self.checkpoint["recorded_subject_sha"],
            "branch": self.checkpoint["branch"],
            "pr": self.checkpoint["pr"],
            "pr_state": self.checkpoint["provider_snapshot"]["pr_state"],
            "checks": dict(self.checkpoint["provider_snapshot"]["checks"]),
        }
        self.assertEqual(mod.reconcile_checkpoint(self.checkpoint, provider)["status"], "RESUME_ALLOWED")

    def test_changed_provider_check_blocks_resume(self):
        provider = {
            "head_known": True,
            "head_sha": self.checkpoint["recorded_subject_sha"],
            "branch": self.checkpoint["branch"],
            "pr": self.checkpoint["pr"],
            "pr_state": self.checkpoint["provider_snapshot"]["pr_state"],
            "checks": dict(self.checkpoint["provider_snapshot"]["checks"]),
        }
        provider["checks"]["repo-integrity"] = "FAILURE"
        result = mod.reconcile_checkpoint(self.checkpoint, provider)
        self.assertIn("CHECKPOINT_CHECK_STALE:repo-integrity", result["reasons"])

    def test_github_hosted_cannot_claim_runtime_verified(self):
        value = copy.deepcopy(self.runtime)
        value["entries"][0]["status"] = "RUNTIME_VERIFIED"
        value["entries"][0]["source_plane"] = "GITHUB_HOSTED"
        self.assertBlocked(lambda: mod.validate_runtime_ledger(value))

    def test_runtime_verified_requires_evidence(self):
        value = copy.deepcopy(self.runtime)
        value["entries"][1]["evidence_refs"] = []
        self.assertBlocked(lambda: mod.validate_runtime_ledger(value))

    def test_github_evidence_cannot_support_runtime_verified(self):
        value = copy.deepcopy(self.evidence)
        value["entries"][0]["supports_claims"] = ["RUNTIME_VERIFIED"]
        self.assertBlocked(lambda: mod.validate_evidence_index(value))

    def test_duplicate_evidence_ids_fail_closed(self):
        value = copy.deepcopy(self.evidence)
        value["entries"].append(copy.deepcopy(value["entries"][0]))
        self.assertBlocked(lambda: mod.validate_evidence_index(value))


if __name__ == "__main__":
    unittest.main()
