from __future__ import annotations

from pathlib import Path
import copy
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]

STATE_SPEC = importlib.util.spec_from_file_location("pncc_state_v2", ROOT / ".pncc-dev/scripts/validate_state.py")
state = importlib.util.module_from_spec(STATE_SPEC)
assert STATE_SPEC.loader is not None
STATE_SPEC.loader.exec_module(state)

RESUME_SPEC = importlib.util.spec_from_file_location("pncc_resume", ROOT / ".pncc-dev/scripts/resume_decision.py")
resume = importlib.util.module_from_spec(RESUME_SPEC)
assert RESUME_SPEC.loader is not None
RESUME_SPEC.loader.exec_module(resume)


class ResumeDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        examples = ROOT / ".pncc-dev/examples"
        cls.base_work = state.load_json(examples / "work-unit.valid.json")
        cls.base_checkpoint = state.load_json(examples / "session-checkpoint.valid.json")
        cls.base_lease = state.load_json(examples / "writer-lease.valid.json")
        cls.base_provider = state.load_json(examples / "provider-truth.valid.json")

    def fixture(self):
        work = copy.deepcopy(self.base_work)
        work.update({
            "work_unit_id": "PIPE-WU-002",
            "base_sha": "58d316275a1e3398004f713223479cc420168236",
            "subject_sha": "1" * 40,
            "branch": "agent/example",
            "pr": 42,
            "conflict_domain": "pipeline-durable-state",
            "state": "ACTIVE",
            "required_checks": ["repo-integrity", "pipeline-state"],
            "next_natural_boundary": "CONTINUE_IMPLEMENTATION",
        })
        checkpoint = copy.deepcopy(self.base_checkpoint)
        checkpoint.update({
            "work_unit_id": "PIPE-WU-002",
            "recorded_subject_sha": "1" * 40,
            "branch": "agent/example",
            "pr": 42,
            "runtime_status": "NOT_REQUIRED",
            "next_natural_boundary": "CONTINUE_IMPLEMENTATION",
        })
        checkpoint["provider_snapshot"] = {
            "observed_head_sha": "1" * 40,
            "pr_state": "OPEN",
            "checks": {"repo-integrity": "SUCCESS", "pipeline-state": "SUCCESS"},
            "observed_at": "2030-01-01T00:10:00Z",
        }
        lease = copy.deepcopy(self.base_lease)
        lease.update({
            "work_unit_id": "PIPE-WU-002",
            "conflict_domain": "pipeline-durable-state",
            "holder": "example-writer",
            "base_sha": "58d316275a1e3398004f713223479cc420168236",
            "branch": "agent/example",
        })
        provider = copy.deepcopy(self.base_provider)
        return work, checkpoint, lease, provider

    def decide(self, work, checkpoint, lease, provider, holder="example-writer", now="2030-01-01T00:20:00Z"):
        return resume.decide_for_holder(work, checkpoint, lease, provider, holder=holder, now_iso=now)

    def test_valid_exact_state_allows_resume(self):
        work, checkpoint, lease, provider = self.fixture()
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "RESUME_ALLOWED")
        self.assertEqual(result["next_natural_boundary"], "CONTINUE_IMPLEMENTATION")

    def test_foreign_holder_blocks_resume(self):
        work, checkpoint, lease, provider = self.fixture()
        result = self.decide(work, checkpoint, lease, provider, holder="another-writer")
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("LEASE_HOLDER_MISMATCH", result["reasons"])

    def test_expired_lease_blocks_resume(self):
        work, checkpoint, lease, provider = self.fixture()
        result = self.decide(work, checkpoint, lease, provider, now="2030-01-01T01:00:00Z")
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("LEASE_EXPIRED", result["reasons"])

    def test_conflicting_lease_domain_blocks_resume(self):
        work, checkpoint, lease, provider = self.fixture()
        lease["conflict_domain"] = "another-domain"
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("LEASE_CONFLICT_DOMAIN_MISMATCH", result["reasons"])

    def test_moved_provider_head_blocks_resume(self):
        work, checkpoint, lease, provider = self.fixture()
        provider["branch_head_sha"] = "9" * 40
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("WORK_UNIT_HEAD_MOVED", result["reasons"])

    def test_pending_required_check_waits(self):
        work, checkpoint, lease, provider = self.fixture()
        checkpoint["provider_snapshot"]["checks"]["pipeline-state"] = "PENDING"
        provider["checks"]["pipeline-state"] = "PENDING"
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "WAITING_PROVIDER_CHECKS")
        self.assertIn("REQUIRED_CHECK_NOT_READY:pipeline-state", result["reasons"])

    def test_missing_required_check_waits(self):
        work, checkpoint, lease, provider = self.fixture()
        work["required_checks"].append("future-required-check")
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "WAITING_PROVIDER_CHECKS")
        self.assertIn("REQUIRED_CHECK_NOT_READY:future-required-check", result["reasons"])

    def test_failed_required_check_blocks(self):
        work, checkpoint, lease, provider = self.fixture()
        checkpoint["provider_snapshot"]["checks"]["pipeline-state"] = "FAILURE"
        provider["checks"]["pipeline-state"] = "FAILURE"
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("REQUIRED_CHECK_FAILED:pipeline-state", result["reasons"])

    def test_runtime_required_without_private_proof_waits(self):
        work, checkpoint, lease, provider = self.fixture()
        work["runtime_required"] = True
        checkpoint["runtime_status"] = "NOT_VERIFIED"
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "WAITING_RUNTIME")
        self.assertEqual(result["next_natural_boundary"], "WAIT_FOR_PRIVATE_RUNTIME_EVIDENCE")

    def test_stale_checkpoint_blocks_before_resume(self):
        work, checkpoint, lease, provider = self.fixture()
        checkpoint["recorded_subject_sha"] = "8" * 40
        checkpoint["provider_snapshot"]["observed_head_sha"] = "8" * 40
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("STALE_CHECKPOINT_HEAD", result["reasons"])

    def test_active_subject_unknown_blocks_resume(self):
        work, checkpoint, lease, provider = self.fixture()
        work["subject_sha"] = None
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("ACTIVE_SUBJECT_SHA_UNKNOWN", result["reasons"])

    def test_work_unit_marker_parses_exactly_once(self):
        marker = "<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-002 state=ACTIVE conflict_domain=pipeline-durable-state branch=agent/example base=58d316275a1e3398004f713223479cc420168236 runtime_required=false -->"
        parsed = state.parse_work_unit_marker("header\n" + marker + "\nbody")
        self.assertEqual(parsed["work_unit_id"], "PIPE-WU-002")
        self.assertFalse(parsed["runtime_required"])
        with self.assertRaises(state.ContractError):
            state.parse_work_unit_marker(marker + "\n" + marker)

    def test_provider_missing_branch_blocks_resume(self):
        work, checkpoint, lease, provider = self.fixture()
        provider["branch_exists"] = False
        provider["branch_head_sha"] = None
        result = self.decide(work, checkpoint, lease, provider)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("PROVIDER_BRANCH_UNKNOWN", result["reasons"])


if __name__ == "__main__":
    unittest.main()
