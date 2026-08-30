import importlib.util, json, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/".pncc-dev/scripts/evaluate_reusable_autonomous_continuation_steady_state.py"
POL=ROOT/".pncc-dev/contracts/reusable-autonomous-continuation-steady-state-policy.json"
spec=importlib.util.spec_from_file_location("steady",MOD); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
P=json.loads(POL.read_text())
MAIN="a"*40

MUTATING={
 "ADMIT_EXISTING_MATERIALIZATION_AUTHORITY":("EXISTING_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY","EXACT_SINGLE_PLANNER_DERIVED_ISSUE_CREATE_PATH"),
 "ADMIT_EXISTING_WRITER_LEASE_AUTHORITY":("EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY","WRITER_LEASE_ACQUIRE_FRESH_CAS_PATH"),
 "ADMIT_EXISTING_MERGE_CLOSE_AUTHORITY":("EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY","WU100_PINNED_MERGE_ELIGIBILITY_PATH"),
}

def control(decision="PLAN_EXISTING_WRITER_LEASE_ACQUISITION",state="PLAN_ONLY_CONTROL_LOOP_PASS"):
    return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION","state":state,
      "decision":decision,"delegated_authority":"EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY",
      "provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,
      "pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,
      "merge_performed":False,"runtime_action_performed":False,"product_runtime_mutation_performed":False}

def admission(decision="ADMIT_EXISTING_WRITER_LEASE_AUTHORITY",control_decision="PLAN_EXISTING_WRITER_LEASE_ACQUISITION",state="PLAN_ONLY_ADMISSION_PASS"):
    delegated,target=MUTATING.get(decision,(P["delegated_authority_identity"].get(decision),None))
    return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_DECISION","state":state,
      "decision":decision,"control_loop_decision":control_decision,"delegated_authority":delegated,"target_action":target,
      "provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,
      "pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,
      "merge_performed":False,"runtime_action_performed":False}

def txn(state="NOT_STARTED",count=0,delegated="EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY",target="WRITER_LEASE_ACQUIRE_FRESH_CAS_PATH"):
    return {"state":state,"delegated_transaction_count":count,"delegated_authority_identity":delegated,
      "target_action":target,"provider_mutation_performed":state!="NOT_STARTED",
      "fresh_provider_readback_completed":state=="PERFORMED_READBACK_COMPLETE",
      "provider_state_after":{"fresh":True,"identity":"provider-readback"} if state=="PERFORMED_READBACK_COMPLETE" else None}

def snap(seq=1,c=None,a=None,t=None,previous=None,**extra):
    x={"schema_version":1,"role":"REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_SNAPSHOT",
      "repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main","provider_truth_fresh":True,
      "current_main_sha":MAIN,"iteration_sequence":seq,"control_loop_fresh_for_iteration":True,
      "execution_admission_fresh_for_iteration":True,"control_loop_reused_from_prior_iteration":False,
      "execution_admission_reused_from_prior_iteration":False,
      "previous_iteration_fresh_provider_readback_completed":previous,
      "interrupted":False,"stale_state":False,"contradiction_detected":False,"anchor_drift_detected":False,
      "revocation_detected":False,"classified_failure_detected":False,
      "control_loop_decision":c or control(),"execution_admission_decision":a or admission(),
      "delegated_transaction":t or txn()}
    x.update(extra); return x

class T(unittest.TestCase):
    def ev(self,s): return m.evaluate(s,policy=P,check_anchors=False)
    def test_admitted_iteration_executes_at_most_one(self):
        r=self.ev(snap()); self.assertEqual(r["decision"],"EXECUTE_ONE_DELEGATED_TRANSACTION"); self.assertEqual(r["delegated_transaction_count"],0)
    def test_performed_transaction_requires_readback(self):
        r=self.ev(snap(t=txn("PERFORMED_READBACK_PENDING",1))); self.assertEqual(r["decision"],"READBACK_REQUIRED_BEFORE_NEXT_ITERATION"); self.assertTrue(r["readback_required"])
    def test_completed_readback_allows_next_fresh_iteration(self):
        r=self.ev(snap(t=txn("PERFORMED_READBACK_COMPLETE",1))); self.assertEqual(r["decision"],"ITERATION_COMPLETE_NEXT_FRESH_ITERATION_ALLOWED")
    def test_second_iteration_requires_previous_readback(self):
        self.assertEqual(self.ev(snap(seq=2,previous=False))["decision"],"BLOCKED")
        self.assertEqual(self.ev(snap(seq=2,previous=True))["decision"],"EXECUTE_ONE_DELEGATED_TRANSACTION")
    def test_two_transactions_in_one_iteration_block(self):
        bad=txn(); bad["delegated_transaction_count"]=2
        self.assertEqual(self.ev(snap(t=bad))["decision"],"BLOCKED")
    def test_stale_provider_and_reuse_block(self):
        self.assertEqual(self.ev(snap(provider_truth_fresh=False))["decision"],"BLOCKED")
        self.assertEqual(self.ev(snap(control_loop_reused_from_prior_iteration=True))["decision"],"BLOCKED")
        self.assertEqual(self.ev(snap(execution_admission_reused_from_prior_iteration=True))["decision"],"BLOCKED")
    def test_control_admission_binding_mismatch_blocks(self):
        a=admission(control_decision="PLAN_EXISTING_BOUNDED_BRANCH_CREATE")
        self.assertEqual(self.ev(snap(a=a))["decision"],"BLOCKED")
    def test_delegated_authority_mismatch_blocks(self):
        a=admission(); a["delegated_authority"]="EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY"
        self.assertEqual(self.ev(snap(a=a))["decision"],"BLOCKED")
    def test_non_mutating_paths_are_mutation_free(self):
        cases=[("WAIT_ONLY","WAIT_ONLY"),("STOP_ONLY","STOP_ONLY"),("SEPARATE_AUTHORITY_REQUIRED","SEPARATE_AUTHORITY_REQUIRED"),("BLOCKED","BLOCKED")]
        for adm_dec,expected in cases:
            c=control("WAIT_FOR_EXACT_HEAD_CI","PLAN_ONLY_CONTROL_LOOP_BLOCKED" if adm_dec=="BLOCKED" else "PLAN_ONLY_CONTROL_LOOP_PASS")
            a=admission(adm_dec,"WAIT_FOR_EXACT_HEAD_CI","PLAN_ONLY_ADMISSION_BLOCKED" if adm_dec=="BLOCKED" else "PLAN_ONLY_ADMISSION_PASS")
            r=self.ev(snap(c=c,a=a,t=txn())); self.assertEqual(r["decision"],expected); self.assertEqual(r["delegated_transaction_count"],0)
    def test_non_mutating_decision_cannot_hide_transaction(self):
        c=control("WAIT_FOR_EXACT_HEAD_CI"); a=admission("WAIT_ONLY","WAIT_FOR_EXACT_HEAD_CI")
        self.assertEqual(self.ev(snap(c=c,a=a,t=txn("PERFORMED_READBACK_PENDING",1)))["decision"],"BLOCKED")
    def test_hazards_fail_closed(self):
        for flag in ("interrupted","stale_state","contradiction_detected","anchor_drift_detected","revocation_detected"):
            self.assertEqual(self.ev(snap(**{flag:True}))["decision"],"BLOCKED",flag)
    def test_classified_failure_requires_separate_authority(self):
        r=self.ev(snap(classified_failure_detected=True)); self.assertEqual(r["decision"],"SEPARATE_AUTHORITY_REQUIRED"); self.assertEqual(r["delegated_transaction_count"],0)
    def test_transaction_target_mismatch_blocks(self):
        bad=txn(); bad["target_action"]="BOUNDED_NON_MAIN_BRANCH_CREATE_PATH"
        self.assertEqual(self.ev(snap(t=bad))["decision"],"BLOCKED")
    def test_policy_has_no_direct_authority(self):
        for k in m.FALSE_AUTH: self.assertIs(P[k],False)
    def test_exact_anchor_map(self):
        m.validate_policy(P); m.validate_anchors(P)

if __name__=="__main__": unittest.main()
