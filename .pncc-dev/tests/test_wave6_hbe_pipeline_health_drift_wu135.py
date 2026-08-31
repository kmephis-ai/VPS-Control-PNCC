#!/usr/bin/env python3
import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/evaluate_wave6_hbe_pipeline_health_drift.py"
POLICY = ROOT / ".pncc-dev/contracts/wave6-hbe-pipeline-health-drift-assessment-policy.json"
ASSESSMENT = ROOT / ".pncc-dev/contracts/wave6-hbe-pipeline-health-drift-assessment-wu135.json"

spec = importlib.util.spec_from_file_location("wu135_eval", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

NOW = datetime(2026, 8, 31, 12, 10, 0, tzinfo=timezone.utc)

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def snapshot():
    return {
        "observed_at": "2026-08-31T12:09:30Z",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "main_sha": "55c1ff6ea4b43ce7b8a6735c3475a996ef49cc4c",
        "selected_work_unit_id": "PIPE-WU-135",
        "selected_work_unit_issue_number": 318,
        "selected_work_unit_state": "OPEN_READY",
        "provider_state_sha": "f0a96f140b25e22e8c02dfe65d625b7d0220ae8a",
        "registry_generation": 46,
        "ruleset_enforcement": "ACTIVE_NO_BYPASS",
        "required_check_contexts": ["repo-integrity", "powershell-static", "truth-contract"],
        "boundary_requests": {
            "product_runtime": False,
            "physical_runtime": False,
            "release_tag_promotion": False,
            "ruleset_security": False,
            "adwf": False,
            "private_evidence": False,
            "reserve_1080_lifecycle": False,
            "primary_1081_lifecycle": False,
            "periodic_scheduling": False,
            "unattended_mutation": False,
            "higher_autonomy": False,
        },
    }

class WU135Tests(unittest.TestCase):
    def evaluate(self, s=None, p=None, a=None, anchors=False):
        return mod.evaluate(snapshot() if s is None else s, now=NOW,
                            policy=load(POLICY) if p is None else p,
                            assessment=load(ASSESSMENT) if a is None else a,
                            check_anchors=anchors)

    def test_healthy_snapshot(self):
        out = self.evaluate(anchors=False)
        self.assertEqual(out["outcome"], "HEALTHY")
        self.assertFalse(out["provider_mutation_performed"])
        self.assertFalse(out["periodic_schedule_created"])
        self.assertFalse(out["authority_granted"])

    def test_main_drift_is_detected(self):
        s = snapshot(); s["main_sha"] = "0" * 40
        out = self.evaluate(s)
        self.assertEqual(out["outcome"], "DRIFT_DETECTED")
        self.assertIn("MAIN_SHA_DRIFT", out["reasons"])

    def test_stale_snapshot_blocks(self):
        s = snapshot(); s["observed_at"] = "2026-08-31T12:00:00Z"
        self.assertEqual(self.evaluate(s)["outcome"], "BLOCKED")

    def test_future_snapshot_blocks(self):
        s = snapshot(); s["observed_at"] = "2026-08-31T12:11:00Z"
        self.assertEqual(self.evaluate(s)["outcome"], "BLOCKED")

    def test_work_unit_drift_is_detected(self):
        s = snapshot(); s["selected_work_unit_id"] = "PIPE-WU-999"
        self.assertEqual(self.evaluate(s)["outcome"], "DRIFT_DETECTED")

    def test_registry_generation_regression_is_detected(self):
        s = snapshot(); s["registry_generation"] = 45
        self.assertEqual(self.evaluate(s)["outcome"], "DRIFT_DETECTED")

    def test_ruleset_drift_is_detected(self):
        s = snapshot(); s["ruleset_enforcement"] = "INACTIVE"
        self.assertEqual(self.evaluate(s)["outcome"], "DRIFT_DETECTED")

    def test_required_check_drift_is_detected(self):
        s = snapshot(); s["required_check_contexts"] = ["repo-integrity", "truth-contract"]
        self.assertEqual(self.evaluate(s)["outcome"], "DRIFT_DETECTED")

    def test_owner_boundary_never_grants_authority(self):
        s = snapshot(); s["boundary_requests"]["periodic_scheduling"] = True
        out = self.evaluate(s)
        self.assertEqual(out["outcome"], "OWNER_EXCEPTION_REQUIRED")
        self.assertFalse(out["authority_granted"])
        self.assertFalse(out["periodic_schedule_created"])

    def test_higher_autonomy_boundary_never_grants_authority(self):
        s = snapshot(); s["boundary_requests"]["higher_autonomy"] = True
        out = self.evaluate(s)
        self.assertEqual(out["outcome"], "OWNER_EXCEPTION_REQUIRED")
        self.assertFalse(out["unattended_mutation_authority_granted"])

    def test_malformed_snapshot_blocks(self):
        s = snapshot(); del s["provider_state_sha"]
        self.assertEqual(self.evaluate(s)["outcome"], "BLOCKED")

    def test_invalid_provider_sha_blocks(self):
        s = snapshot(); s["provider_state_sha"] = "not-a-sha"
        self.assertEqual(self.evaluate(s)["outcome"], "BLOCKED")

    def test_policy_authority_flip_blocks(self):
        p = load(POLICY); p["periodic_scheduling_authority"] = True
        out = self.evaluate(p=p)
        self.assertEqual(out["outcome"], "BLOCKED")
        self.assertIn("POLICY_AUTHORITY_PRESENT:periodic_scheduling_authority", out["reasons"])

    def test_assessment_authority_flip_blocks(self):
        a = load(ASSESSMENT); a["assessment_output_authority"]["merge_authority"] = True
        out = self.evaluate(a=a)
        self.assertEqual(out["outcome"], "BLOCKED")
        self.assertIn("ASSESSMENT_OUTPUT_AUTHORITY_PRESENT:merge_authority", out["reasons"])

    def test_duplicate_json_key_is_rejected(self):
        p = Path("/tmp/wu135-duplicate.json")
        p.write_text('{"a":1,"a":2}', encoding="utf-8")
        with self.assertRaises(mod.AssessmentError):
            mod.load_json(p)

if __name__ == "__main__":
    unittest.main()
