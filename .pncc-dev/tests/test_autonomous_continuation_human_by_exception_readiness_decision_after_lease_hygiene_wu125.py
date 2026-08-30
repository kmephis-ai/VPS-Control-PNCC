#!/usr/bin/env python3
"""Adversarial tests for PIPE-WU-125 post-hygiene Human-by-Exception decision."""
from __future__ import annotations
import copy, importlib.util, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD_PATH=ROOT/".pncc-dev/scripts/evaluate_autonomous_continuation_human_by_exception_readiness_decision_after_lease_hygiene.py"
SPEC=importlib.util.spec_from_file_location("wu125_decision",MOD_PATH)
MOD=importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name]=MOD; SPEC.loader.exec_module(MOD)
DECISION=MOD.load_json(ROOT/".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-decision-after-lease-hygiene-wu125.json")
ASSESSMENT=MOD.load_json(ROOT/".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-reassessment-wu124.json")

REGISTRY={
 "schema_version":1,"role":"WRITER_LEASE_REGISTRY","generation":33,
 "entries":[
   {"lease_id":"older","work_unit_id":"PIPE-WU-124","state":"RELEASED","expires_at":"2026-08-30T19:10:00Z"},
   {"lease_id":"27829f63-9bc6-4ba3-b495-4985bb36be32","work_unit_id":"PIPE-WU-125","generation":33,
    "base_sha":"7af4f2752ea59c2c79deb78defe04ce912282019",
    "branch":"agent/PIPE-WU-125-human-by-exception-readiness-decision-after-lease-hygiene",
    "state":"ACTIVE","expires_at":"2026-08-30T19:40:00Z"}
 ]
}

class WU125DecisionTests(unittest.TestCase):
    def evaluate(self,d=None,r=None,a=None):
        return MOD.evaluate(copy.deepcopy(r or REGISTRY),decision=copy.deepcopy(d or DECISION),assessment=copy.deepcopy(a or ASSESSMENT),check_anchors=False)

    def test_canonical_positive_decision_is_existing_authority_only(self):
        out=self.evaluate()
        self.assertEqual(out["state"],"READINESS_DECISION_VALIDATED_APPROVED_EXISTING_AUTHORITY_ONLY")
        self.assertTrue(out["human_by_exception_operating_mode_approved"])
        self.assertFalse(out["higher_autonomy_authorized"])
        self.assertFalse(out["authority_granted"])
        self.assertEqual(out["stale_active_history_count"],0)

    def test_cannot_turn_readiness_into_authority(self):
        d=copy.deepcopy(DECISION); d["authority_granted"]=True
        with self.assertRaises(MOD.DecisionError): self.evaluate(d=d)

    def test_cannot_enable_higher_autonomy(self):
        d=copy.deepcopy(DECISION); d["higher_autonomy_authorized"]=True
        with self.assertRaises(MOD.DecisionError): self.evaluate(d=d)

    def test_stale_active_history_blocks(self):
        r=copy.deepcopy(REGISTRY); r["entries"][0]["state"]="ACTIVE"; r["entries"][0]["expires_at"]="2026-08-30T18:00:00Z"
        with self.assertRaises(MOD.DecisionError): self.evaluate(r=r)

    def test_second_current_writer_blocks(self):
        r=copy.deepcopy(REGISTRY); x=copy.deepcopy(r["entries"][-1]); x["lease_id"]="other"; x["work_unit_id"]="PIPE-WU-X"; r["entries"].append(x)
        with self.assertRaises(MOD.DecisionError): self.evaluate(r=r)

    def test_wait_stop_separate_and_owner_boundaries_are_immutable(self):
        for key in ("wait","stop","separate_authority","owner_escalation"):
            d=copy.deepcopy(DECISION); d["classification_boundaries"][key]="AUTO"
            with self.assertRaises(MOD.DecisionError): self.evaluate(d=d)

    def test_public_safety_flags_cannot_flip(self):
        d=copy.deepcopy(DECISION); d["public_safety"]["reserve_1080_lifecycle_mutation"]=True
        with self.assertRaises(MOD.DecisionError): self.evaluate(d=d)

if __name__=="__main__":
    unittest.main()
