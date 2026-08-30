import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".pncc-dev/scripts/evaluate_autonomous_continuation_human_by_exception_readiness.py"
spec = importlib.util.spec_from_file_location("wu119_readiness", MODULE_PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

RUBRIC = m.load_json(ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-rubric.json")
ASSESSMENT = m.load_json(ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-assessment-wu119.json")

def registry_fixture():
    entries = []
    for row in ASSESSMENT["stale_active_history"]:
        entries.append({
            "lease_id": row["lease_id"],
            "work_unit_id": row["work_unit_id"],
            "generation": row["generation"],
            "state": "ACTIVE",
            "expires_at": row["expires_at"],
            "base_sha": "0" * 40,
            "branch": "historical",
        })
    c = ASSESSMENT["current_writer"]
    entries.append({
        "lease_id": c["lease_id"],
        "work_unit_id": c["work_unit_id"],
        "generation": c["generation"],
        "state": c["state"],
        "expires_at": c["expires_at"],
        "base_sha": c["base_sha"],
        "branch": c["branch"],
    })
    return {"schema_version": 1, "role": "WRITER_LEASE_REGISTRY", "generation": 27, "entries": entries}

class ReadinessTests(unittest.TestCase):
    def evaluate(self, registry=None, rubric=None, assessment=None):
        return m.evaluate(
            registry or registry_fixture(),
            rubric=rubric or copy.deepcopy(RUBRIC),
            assessment=assessment or copy.deepcopy(ASSESSMENT),
            check_anchors=False,
        )

    def test_canonical_assessment_with_blockers(self):
        out = self.evaluate()
        self.assertEqual(out["state"], "ASSESSMENT_VALIDATED_WITH_BLOCKERS")
        self.assertEqual(out["stale_active_history_count"], 4)
        self.assertFalse(out["authority_granted"])
        self.assertTrue(out["separate_hygiene_authority_required"])

    def test_stale_active_cannot_be_current_ownership(self):
        a = copy.deepcopy(ASSESSMENT)
        a["stale_active_history"][0]["current_ownership_eligible"] = True
        with self.assertRaisesRegex(m.ReadinessError, "ASSESSMENT_STALE_OWNERSHIP_INVALID"):
            self.evaluate(assessment=a)

    def test_missing_stale_history_is_provider_mismatch(self):
        r = registry_fixture()
        r["entries"] = r["entries"][1:]
        with self.assertRaisesRegex(m.ReadinessError, "STALE_ACTIVE_SET_MISMATCH"):
            self.evaluate(registry=r)

    def test_expired_history_made_future_becomes_conflicting_current(self):
        r = registry_fixture()
        r["entries"][0]["expires_at"] = "2026-08-31T18:54:21Z"
        with self.assertRaises(m.ReadinessError):
            self.evaluate(registry=r)

    def test_old_work_unit_cannot_replace_current_writer(self):
        r = registry_fixture()
        r["entries"][-1]["work_unit_id"] = "PIPE-WU-108"
        with self.assertRaisesRegex(m.ReadinessError, "CURRENT_WRITER_REGISTRY_MISMATCH"):
            self.evaluate(registry=r)

    def test_registry_generation_must_match_fresh_provider_snapshot(self):
        r = registry_fixture()
        r["generation"] = 26
        with self.assertRaisesRegex(m.ReadinessError, "REGISTRY_GENERATION_MISMATCH"):
            self.evaluate(registry=r)

    def test_assessment_can_never_grant_authority(self):
        a = copy.deepcopy(ASSESSMENT)
        a["authority_granted"] = True
        with self.assertRaisesRegex(m.ReadinessError, "ASSESSMENT_FIELD_INVALID:authority_granted"):
            self.evaluate(assessment=a)

    def test_output_authority_flag_cannot_flip_true(self):
        a = copy.deepcopy(ASSESSMENT)
        a["assessment_output_authority"]["merge_authority"] = True
        with self.assertRaisesRegex(m.ReadinessError, "ASSESSMENT_OUTPUT_AUTHORITY_PRESENT"):
            self.evaluate(assessment=a)

    def test_public_safety_flag_cannot_flip_true(self):
        a = copy.deepcopy(ASSESSMENT)
        a["public_safety"]["contains_credentials"] = True
        with self.assertRaisesRegex(m.ReadinessError, "PUBLIC_SAFETY_INVALID"):
            self.evaluate(assessment=a)

    def test_stale_blocker_count_must_match_provider_truth(self):
        a = copy.deepcopy(ASSESSMENT)
        a["residual_blockers"][0]["count"] = 3
        with self.assertRaisesRegex(m.ReadinessError, "STALE_BLOCKER_INVALID"):
            self.evaluate(assessment=a)

    def test_rubric_authority_cannot_flip_true(self):
        r = copy.deepcopy(RUBRIC)
        r["authority_flags"]["runtime_action_authority"] = True
        with self.assertRaisesRegex(m.ReadinessError, "RUBRIC_AUTHORITY_PRESENT"):
            self.evaluate(rubric=r)

if __name__ == "__main__":
    unittest.main()
