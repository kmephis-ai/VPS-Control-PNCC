import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".pncc-dev/scripts/evaluate_autonomous_continuation_human_by_exception_readiness_decision.py"
spec = importlib.util.spec_from_file_location("wu120_decision", MODULE_PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

DECISION = m.load_json(ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-decision-wu120.json")
ASSESSMENT = m.load_json(ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-assessment-wu119.json")
RUBRIC = m.load_json(ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-rubric.json")


def registry_fixture():
    stale_by_id = {x["lease_id"]: x for x in ASSESSMENT["stale_active_history"]}
    entries = []
    for lease_id in DECISION["stale_history_decision"]["lease_ids"]:
        row = stale_by_id[lease_id]
        entries.append({
            "lease_id": lease_id,
            "work_unit_id": row["work_unit_id"],
            "generation": row["generation"],
            "state": "ACTIVE",
            "expires_at": row["expires_at"],
            "base_sha": "0" * 40,
            "branch": "historical",
        })
    c = DECISION["current_writer"]
    entries.append({
        "lease_id": c["lease_id"],
        "work_unit_id": c["work_unit_id"],
        "generation": c["generation"],
        "state": c["state"],
        "expires_at": c["expires_at"],
        "base_sha": c["base_sha"],
        "branch": c["branch"],
    })
    return {"schema_version": 1, "role": "WRITER_LEASE_REGISTRY", "generation": 28, "entries": entries}


class DecisionTests(unittest.TestCase):
    def evaluate(self, registry=None, decision=None, assessment=None, rubric=None):
        return m.evaluate(
            registry if registry is not None else registry_fixture(),
            decision=decision if decision is not None else copy.deepcopy(DECISION),
            assessment=assessment if assessment is not None else copy.deepcopy(ASSESSMENT),
            rubric=rubric if rubric is not None else copy.deepcopy(RUBRIC),
            check_anchors=False,
        )

    def test_canonical_decision_defers_and_remediates(self):
        out = self.evaluate()
        self.assertEqual(out["state"], "READINESS_DECISION_VALIDATED_DEFER_AND_REMEDIATE")
        self.assertEqual(out["stale_active_history_count"], 4)
        self.assertFalse(out["higher_autonomy_authorized"])
        self.assertFalse(out["authority_granted"])
        self.assertTrue(out["historical_state_reconciliation_required"])

    def test_decision_cannot_authorize_higher_autonomy(self):
        d = copy.deepcopy(DECISION)
        d["higher_autonomy_authorized"] = True
        with self.assertRaisesRegex(m.DecisionError, "DECISION_FIELD_INVALID:higher_autonomy_authorized"):
            self.evaluate(decision=d)

    def test_decision_cannot_grant_authority(self):
        d = copy.deepcopy(DECISION)
        d["authority_granted"] = True
        with self.assertRaisesRegex(m.DecisionError, "DECISION_FIELD_INVALID:authority_granted"):
            self.evaluate(decision=d)

    def test_outcome_cannot_be_ready(self):
        d = copy.deepcopy(DECISION)
        d["decision_outcome"] = "READY_WITH_EXISTING_AUTHORITY_ONLY"
        with self.assertRaisesRegex(m.DecisionError, "DECISION_FIELD_INVALID:decision_outcome"):
            self.evaluate(decision=d)

    def test_missing_stale_provider_entry_fails_closed(self):
        r = registry_fixture()
        r["entries"] = r["entries"][1:]
        with self.assertRaisesRegex(m.DecisionError, "STALE_PROVIDER_SET_INVALID"):
            self.evaluate(registry=r)

    def test_historical_entry_made_future_conflicts_with_current_writer(self):
        r = registry_fixture()
        r["entries"][0]["expires_at"] = "2026-08-31T18:54:21Z"
        with self.assertRaises(m.DecisionError):
            self.evaluate(registry=r)

    def test_registry_generation_drift_fails_closed(self):
        r = registry_fixture()
        r["generation"] = 27
        with self.assertRaisesRegex(m.DecisionError, "REGISTRY_GENERATION_INVALID"):
            self.evaluate(registry=r)

    def test_wrong_current_work_unit_fails_closed(self):
        r = registry_fixture()
        r["entries"][-1]["work_unit_id"] = "PIPE-WU-119"
        with self.assertRaisesRegex(m.DecisionError, "CURRENT_WRITER_PROVIDER_MISMATCH:work_unit_id"):
            self.evaluate(registry=r)

    def test_wu119_assessment_cannot_be_rewritten_ready(self):
        a = copy.deepcopy(ASSESSMENT)
        a["readiness_verdict"] = "READY_WITH_EXISTING_AUTHORITY_ONLY"
        with self.assertRaisesRegex(m.DecisionError, "ASSESSMENT_VERDICT_INVALID"):
            self.evaluate(assessment=a)

    def test_historical_mutation_cannot_be_claimed_in_wu120(self):
        d = copy.deepcopy(DECISION)
        d["stale_history_decision"]["historical_state_mutation_performed_in_wu120"] = True
        with self.assertRaisesRegex(m.DecisionError, "STALE_DECISION_FIELD_INVALID:historical_state_mutation_performed_in_wu120"):
            self.evaluate(decision=d)

    def test_authority_flag_cannot_flip_true(self):
        d = copy.deepcopy(DECISION)
        d["authority_flags"]["provider_mutation_authority"] = True
        with self.assertRaisesRegex(m.DecisionError, "DECISION_AUTHORITY_AUTHORITY_OR_SAFETY_FLAG"):
            self.evaluate(decision=d)

    def test_public_safety_flag_cannot_flip_true(self):
        d = copy.deepcopy(DECISION)
        d["public_safety"]["contains_credentials"] = True
        with self.assertRaisesRegex(m.DecisionError, "PUBLIC_SAFETY_AUTHORITY_OR_SAFETY_FLAG"):
            self.evaluate(decision=d)

    def test_next_boundary_is_exact(self):
        d = copy.deepcopy(DECISION)
        d["next_boundary"] = "HUMAN_BY_EXCEPTION_AUTHORIZATION"
        with self.assertRaisesRegex(m.DecisionError, "DECISION_FIELD_INVALID:next_boundary"):
            self.evaluate(decision=d)


if __name__ == "__main__":
    unittest.main()
