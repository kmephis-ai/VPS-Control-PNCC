import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("hbe_resume", ROOT/"scripts"/"evaluate_autonomous_continuation_human_by_exception_durable_session_resume.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
POLICY=mod.load_json(ROOT/"contracts"/"autonomous-continuation-human-by-exception-durable-session-resume-policy-wu130.json")

def base_snapshot():
    return {
      "schema_version":1,
      "role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_SESSION_CHECKPOINT",
      "provider_truth_fresh":True,"main_fresh":True,"selection_fresh":True,
      "branch_readback_fresh":True,"pr_ci_readback_fresh_when_applicable":True,
      "current_main_sha":"f6f942f40db14eac28b97fa79429f3ad49f1b9ae",
      "selected_work_unit":{
        "work_unit_id":"PIPE-WU-130","issue_number":308,"marker_state":"READY",
        "conflict_domain":"wave5-autonomous-continuation-human-by-exception-durable-session-resume-existing-authority-only",
        "runtime_required":False,"base_sha":"f6f942f40db14eac28b97fa79429f3ad49f1b9ae"
      },
      "provider_state":{
        "state_branch_head_sha":"cd4f127c616968eb407b02a77cbcd95c15c776c2",
        "registry_blob_sha":"87e545c85a2e8641eba5e741adbad66fd305dab2",
        "registry_generation":39,"unexpired_active_in_conflict_domain":1,
        "exact_owned_lease":{
          "lease_id":"7435a7f5-9dcb-4c87-a803-62e0561f6153","work_unit_id":"PIPE-WU-130",
          "conflict_domain":"wave5-autonomous-continuation-human-by-exception-durable-session-resume-existing-authority-only",
          "holder":"chatgpt-wave5-writer","base_sha":"f6f942f40db14eac28b97fa79429f3ad49f1b9ae",
          "branch":"agent/PIPE-WU-130-human-by-exception-durable-session-resume-existing-authority-only",
          "state":"ACTIVE","generation":39,"expired":False
        }
      },
      "branch_state":{"present":True,"name":"agent/PIPE-WU-130-human-by-exception-durable-session-resume-existing-authority-only",
                      "head_sha":"f6f942f40db14eac28b97fa79429f3ad49f1b9ae","base_sha":"f6f942f40db14eac28b97fa79429f3ad49f1b9ae"},
      "expected_branch":"agent/PIPE-WU-130-human-by-exception-durable-session-resume-existing-authority-only",
      "transaction_boundary":"CLEAN_ITERATION_BOUNDARY",
      "completed_transaction_fingerprints":["writer-lease-acquire-gen39","bounded-branch-create"],
      "next_transaction_fingerprint":"future-fresh-control-loop-action",
      "hbe_boundary":"CONTINUE"
    }

class Tests(unittest.TestCase):
    def eval(self,s): return mod.evaluate(POLICY,s)
    def test_live_owned_lease_recomputes(self):
        r=self.eval(base_snapshot()); self.assertEqual(r["decision"],"RECOMPUTE_FRESH_CONTINUATION"); self.assertFalse(r["authority_granted"])
    def test_expired_active_requires_fresh_monotonic_claim(self):
        s=base_snapshot(); s["provider_state"]["exact_owned_lease"]["expired"]=True; s["provider_state"]["unexpired_active_in_conflict_domain"]=0
        r=self.eval(s); self.assertEqual(r["decision"],"FRESH_MONOTONIC_LEASE_REQUIRED"); self.assertEqual(r["required_minimum_next_generation"],40); self.assertFalse(r["historical_lease_mutation_performed"])
    def test_released_requires_fresh_claim(self):
        s=base_snapshot(); s["provider_state"]["exact_owned_lease"]["state"]="RELEASED"; s["provider_state"]["exact_owned_lease"]["expired"]=True; s["provider_state"]["unexpired_active_in_conflict_domain"]=0
        self.assertEqual(self.eval(s)["decision"],"FRESH_MONOTONIC_LEASE_REQUIRED")
    def test_absent_lease_requires_fresh_claim(self):
        s=base_snapshot(); s["provider_state"]["exact_owned_lease"]=None; s["provider_state"]["unexpired_active_in_conflict_domain"]=0
        self.assertEqual(self.eval(s)["decision"],"FRESH_MONOTONIC_LEASE_REQUIRED")
    def test_conflicting_unexpired_blocks(self):
        s=base_snapshot(); s["provider_state"]["exact_owned_lease"]=None; s["provider_state"]["unexpired_active_in_conflict_domain"]=1
        self.assertEqual(self.eval(s)["decision"],"BLOCKED")
    def test_unknown_transaction_reconciles_without_replay(self):
        s=base_snapshot(); s["transaction_boundary"]="TRANSACTION_OUTCOME_UNKNOWN"
        r=self.eval(s); self.assertEqual(r["decision"],"RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH"); self.assertFalse(r["transaction_replay_performed"])
    def test_readback_pending_waits(self):
        s=base_snapshot(); s["transaction_boundary"]="PROVIDER_READBACK_PENDING"
        self.assertEqual(self.eval(s)["decision"],"WAIT_FOR_FRESH_PROVIDER_READBACK")
    def test_completed_transaction_replay_blocks(self):
        s=base_snapshot(); s["next_transaction_fingerprint"]="bounded-branch-create"
        self.assertEqual(self.eval(s)["decision"],"BLOCKED")
    def test_owner_wait_stop_separate_are_distinct(self):
        expected={"OWNER_ESCALATION_REQUIRED":"OWNER_ESCALATION_REQUIRED","WAIT_ONLY":"WAIT_ONLY","STOP_ONLY":"STOP_ONLY","SEPARATE_AUTHORITY_REQUIRED":"SEPARATE_AUTHORITY_REQUIRED","BLOCKED":"BLOCKED"}
        for boundary,decision in expected.items():
            s=base_snapshot(); s["hbe_boundary"]=boundary
            self.assertEqual(self.eval(s)["decision"],decision)
    def test_stale_provider_blocks(self):
        s=base_snapshot(); s["provider_truth_fresh"]=False
        self.assertEqual(self.eval(s)["decision"],"BLOCKED")
    def test_main_drift_blocks(self):
        s=base_snapshot(); s["current_main_sha"]="0"*40
        self.assertEqual(self.eval(s)["decision"],"BLOCKED")
    def test_historical_rewrite_request_blocks(self):
        s=base_snapshot(); s["historical_lease_rewrite_requested"]=True
        self.assertEqual(self.eval(s)["decision"],"BLOCKED")
    def test_persisted_decision_reuse_blocks(self):
        s=base_snapshot(); s["persisted_cas_reuse_requested"]=True
        self.assertEqual(self.eval(s)["decision"],"BLOCKED")
    def test_authority_flip_invalidates_policy(self):
        p=copy.deepcopy(POLICY); p["writer_lease_mutation_authority"]=True
        self.assertEqual(mod.evaluate(p,base_snapshot())["decision"],"BLOCKED")

if __name__=="__main__": unittest.main()
