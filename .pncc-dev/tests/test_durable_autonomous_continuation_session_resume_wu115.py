import copy, importlib.util, json, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/".pncc-dev/scripts/evaluate_durable_autonomous_continuation_session_resume.py"
POL=ROOT/".pncc-dev/contracts/durable-autonomous-continuation-session-resume-policy.json"
spec=importlib.util.spec_from_file_location("resume115",MOD); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
P=json.loads(POL.read_text())
MAIN="f9e03320d815cc870836067f24cce14ecba1cc62"
BRANCH="agent/PIPE-WU-115-durable-autonomous-continuation-session-resume"
LEASE="509b6d46-6999-4cae-b586-2f1e6e86ff43"
PROVIDER={"state_branch_present":True,"state_branch_head_sha":"1f76a1247c0f8757c28b18aac10b7d8ad5b6d6ad","registry_blob_sha":"a254843017e09e4170d914476f756cd008254177","registry_generation":23}
SELECTED={"work_unit_id":"PIPE-WU-115","issue_number":277,"base_sha":MAIN,"runtime_required":False,"provider_open":True}
EXEC={"lease":{"state":"ACTIVE","lease_id":LEASE,"generation":23,"branch":BRANCH},"branch":{"present":True,"name":BRANCH,"head_sha":MAIN},"pull_request":{"state":"NONE","number":None,"base_sha":None,"head_sha":None,"merge_commit_sha":None},"ci":{"state":"NONE","head_sha":None}}

def checkpoint(boundary="CLEAN_ITERATION_BOUNDARY"):
    return {"schema_version":1,"role":"DURABLE_AUTONOMOUS_CONTINUATION_SESSION_CHECKPOINT","checkpoint_state":"PERSISTED_HINT_ONLY","checkpoint_id":"PNCC-CONTINUATION-CHECKPOINT-WU115-A1","repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main","recorded_main_sha":MAIN,"selected_work_unit":copy.deepcopy(SELECTED),"provider_state":copy.deepcopy(PROVIDER),"execution_state":copy.deepcopy(EXEC),"last_completed_steady_state_iteration":2,"transaction_boundary":boundary,"persisted_decisions":{"control_loop_decision":"PLAN_EXISTING_BOUNDED_BRANCH_CREATE","execution_admission_decision":"ADMIT_EXISTING_WRITER_LEASE_AUTHORITY","ci_decision":None},"checkpoint_is_mutation_authority":False,"checkpoint_cas_tokens_reusable":False,"checkpoint_ci_success_reusable":False,"checkpoint_admission_reusable":False,"contains_private_runtime_payload":False,"contains_credentials":False,"contains_host_identifiers":False,"contains_secret_transport_data":False}

def snapshot(cp=None,readback=True,**overrides):
    s={"schema_version":1,"role":"DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME_SNAPSHOT","repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main","provider_truth_fresh":True,"contradictory_provider_truth":False,"current_main_sha":MAIN,"selected_work_unit":copy.deepcopy(SELECTED),"provider_state":copy.deepcopy(PROVIDER),"execution_state":copy.deepcopy(EXEC),"classified_failure_detected":False,"fresh_provider_readback_completed":readback,"checkpoint":cp}
    s.update(overrides); return s

class DurableSessionResumeTests(unittest.TestCase):
    def ev(self,s): return m.evaluate(s,policy=P,check_anchors=False)
    def test_no_checkpoint_recomputes_from_provider_truth(self):
        r=self.ev(snapshot()); self.assertEqual(r["decision"],"RECOMPUTE_FRESH_CONTINUATION"); self.assertFalse(r["checkpoint_authority_used"])
    def test_clean_checkpoint_recomputes_and_discards_persisted_decisions(self):
        r=self.ev(snapshot(checkpoint())); self.assertEqual(r["decision"],"RECOMPUTE_FRESH_CONTINUATION"); self.assertEqual(r["checkpoint_drift_fields"],[]); self.assertEqual(r["discarded_persisted_decisions"],["control_loop_decision","execution_admission_decision"]); self.assertTrue(r["fresh_wu108_recomputation_required"]); self.assertTrue(r["fresh_wu109_recomputation_required_before_mutation"])
    def test_clean_checkpoint_main_drift_uses_fresh_truth_not_checkpoint(self):
        cp=checkpoint(); s=snapshot(cp,current_main_sha="a"*40); r=self.ev(s); self.assertEqual(r["decision"],"RECOMPUTE_FRESH_CONTINUATION"); self.assertIn("current_main",r["checkpoint_drift_fields"])
    def test_selected_provider_lease_branch_pr_ci_drift_are_detected(self):
        mutations=[("selected_work_unit",lambda s: s.update(selected_work_unit=None),"selected_work_unit"),("provider",lambda s: s["provider_state"].update(registry_generation=24),"provider_state"),("lease",lambda s: s["execution_state"]["lease"].update(state="RELEASED"),"writer_lease"),("branch",lambda s: s["execution_state"]["branch"].update(head_sha="b"*40),"branch"),("pr",lambda s: s["execution_state"]["pull_request"].update(state="OPEN",number=279,base_sha=MAIN,head_sha=MAIN),"pull_request"),("ci",lambda s: s["execution_state"]["ci"].update(state="SUCCESS",head_sha=MAIN),"ci")]
        for name,fn,field in mutations:
            s=snapshot(checkpoint()); fn(s); r=self.ev(s); self.assertEqual(r["decision"],"RECOMPUTE_FRESH_CONTINUATION",name); self.assertIn(field,r["checkpoint_drift_fields"],name)
    def test_unknown_transaction_without_readback_waits(self):
        r=self.ev(snapshot(checkpoint("TRANSACTION_OUTCOME_UNKNOWN"),readback=False)); self.assertEqual(r["decision"],"WAIT_FOR_FRESH_PROVIDER_READBACK"); self.assertTrue(r["provider_reconciliation_required"])
    def test_unknown_transaction_with_readback_reconciles_not_replays(self):
        r=self.ev(snapshot(checkpoint("TRANSACTION_OUTCOME_UNKNOWN"),readback=True)); self.assertEqual(r["decision"],"RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH"); self.assertFalse(r["persisted_admission_reused"]); self.assertFalse(r["persisted_cas_reused"])
    def test_pending_readback_same_fail_closed_semantics(self):
        self.assertEqual(self.ev(snapshot(checkpoint("PROVIDER_READBACK_PENDING"),readback=False))["decision"],"WAIT_FOR_FRESH_PROVIDER_READBACK")
        self.assertEqual(self.ev(snapshot(checkpoint("PROVIDER_READBACK_PENDING"),readback=True))["decision"],"RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH")
    def test_persisted_ci_success_is_never_reused(self):
        cp=checkpoint(); cp["execution_state"]["ci"]={"state":"SUCCESS","head_sha":MAIN}; cp["persisted_decisions"]["ci_decision"]="CI_SUCCESS"
        s=snapshot(cp); s["execution_state"]["ci"]={"state":"SUCCESS","head_sha":MAIN}; r=self.ev(s); self.assertEqual(r["decision"],"RECOMPUTE_FRESH_CONTINUATION"); self.assertFalse(r["persisted_ci_reused"]); self.assertIn("ci_decision",r["discarded_persisted_decisions"])
    def test_released_or_expired_lease_never_reused(self):
        for state in ("RELEASED","EXPIRED"):
            cp=checkpoint(); cp["execution_state"]["lease"]["state"]=state; s=snapshot(cp); s["execution_state"]["lease"]["state"]=state; r=self.ev(s); self.assertEqual(r["decision"],"RECOMPUTE_FRESH_CONTINUATION"); self.assertFalse(r["checkpoint_authority_used"])
    def test_classified_failure_requires_separate_authority(self):
        r=self.ev(snapshot(checkpoint(),classified_failure_detected=True)); self.assertEqual(r["decision"],"SEPARATE_AUTHORITY_REQUIRED"); self.assertFalse(r["provider_mutation_performed"])
    def test_stale_or_contradictory_provider_truth_blocks(self):
        self.assertEqual(self.ev(snapshot(checkpoint(),provider_truth_fresh=False))["decision"],"BLOCKED")
        self.assertEqual(self.ev(snapshot(checkpoint(),contradictory_provider_truth=True))["decision"],"BLOCKED")
    def test_checkpoint_cannot_claim_authority_or_sensitive_payload(self):
        for field in ("checkpoint_is_mutation_authority","checkpoint_cas_tokens_reusable","checkpoint_ci_success_reusable","checkpoint_admission_reusable","contains_private_runtime_payload","contains_credentials","contains_host_identifiers","contains_secret_transport_data"):
            cp=checkpoint(); cp[field]=True; self.assertEqual(self.ev(snapshot(cp))["decision"],"BLOCKED",field)
    def test_checkpoint_additional_property_blocks(self):
        cp=checkpoint(); cp["password"]="forbidden"; self.assertEqual(self.ev(snapshot(cp))["decision"],"BLOCKED")
    def test_checkpoint_bad_identity_blocks(self):
        cp=checkpoint(); cp["checkpoint_id"]="bad"; self.assertEqual(self.ev(snapshot(cp))["decision"],"BLOCKED")
    def test_policy_and_anchor_map_are_exact(self):
        m.validate_policy(P); m.validate_anchors(P)
    def test_policy_contains_no_direct_mutation_authority(self):
        for k in m.FALSE_AUTH: self.assertIs(P[k],False,k)

if __name__=="__main__": unittest.main()
