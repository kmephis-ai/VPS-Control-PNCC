import importlib.util, json, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/".pncc-dev/scripts/evaluate_autonomous_continuation_execution_admission.py"
POL=ROOT/".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json"
spec=importlib.util.spec_from_file_location("admission",MOD); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
P=json.loads(POL.read_text())
MAIN="a"*40
WU="PIPE-WU-109"
BR="agent/PIPE-WU-109-x"

def control(decision,delegated,state="PLAN_ONLY_CONTROL_LOOP_PASS"):
    return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION","state":state,
      "decision":decision,"delegated_authority":delegated,
      "provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,
      "pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,
      "merge_performed":False,"runtime_action_performed":False,"product_runtime_mutation_performed":False}

def snap(c,e):
    return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_SNAPSHOT",
      "repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main","provider_truth_fresh":True,
      "current_main_sha":MAIN,"control_loop_decision":c,"transaction_evidence":e}

def sel(**extra):
    x={"selected_work_unit_exact":True,"selected_issue_open":True,"runtime_required_false":True,
       "selected_base_sha":MAIN,"work_unit_id":WU,"issue_number":265,"branch_name":BR}
    x.update(extra); return x

class T(unittest.TestCase):
    def ev(self,c,e): return m.evaluate(snap(c,e),policy=P,check_anchors=False)
    def test_materialization(self):
        c=control("PLAN_EXISTING_MATERIALIZATION_TRANSACTION","EXISTING_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY")
        e={k:True for k in ("selector_no_work","no_open_canonical_work_unit","materialization_eligible","proposal_deterministic","proposal_runtime_required_false","proposed_issue_absent")}
        e["proposal_base_sha"]=MAIN
        self.assertEqual(self.ev(c,e)["decision"],"ADMIT_EXISTING_MATERIALIZATION_AUTHORITY")
    def test_claim(self):
        c=control("PLAN_EXISTING_WRITER_LEASE_ACQUISITION","EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY")
        e=sel(claim_eligible=True,no_conflicting_unexpired_lease=True,registry_cas_fresh=True,provider_state_head_sha="b"*40,registry_blob_sha="c"*40)
        self.assertEqual(self.ev(c,e)["target_action"],"WRITER_LEASE_ACQUIRE_FRESH_CAS_PATH")
    def test_branch_create(self):
        c=control("PLAN_EXISTING_BOUNDED_BRANCH_CREATE","EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY")
        self.assertEqual(self.ev(c,sel(exact_active_unexpired_lease=True,branch_absent=True))["decision"],"ADMIT_EXISTING_WRITER_LEASE_AUTHORITY")
    def test_continue_branch(self):
        c=control("CONTINUE_EXISTING_BOUNDED_BRANCH","EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY")
        self.assertEqual(self.ev(c,sel(exact_active_unexpired_lease=True,branch_exists=True,branch_head_exact=True))["target_action"],"BOUNDED_BRANCH_CONTINUATION_PATH")
    def test_pr_create(self):
        c=control("PLAN_EXISTING_PULL_REQUEST_CREATE","EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY")
        self.assertEqual(self.ev(c,sel(exact_active_unexpired_lease=True,branch_exists=True,branch_head_exact=True,pull_request_absent=True))["target_action"],"EXACT_BOUNDED_PULL_REQUEST_CREATE_PATH")
    def test_wait_ci(self):
        c=control("WAIT_FOR_EXACT_HEAD_CI","NONE_WAIT_ONLY")
        self.assertEqual(self.ev(c,{"exact_pr_head_binding":True})["decision"],"WAIT_ONLY")
    def test_recovery_separate(self):
        c=control("PLAN_CLASSIFIED_FAILURE_RECOVERY","NONE_SEPARATE_RECOVERY_AUTHORITY_REQUIRED")
        self.assertEqual(self.ev(c,{"failure_classification_present":True})["decision"],"SEPARATE_AUTHORITY_REQUIRED")
    def test_release(self):
        c=control("PLAN_EXISTING_WRITER_LEASE_RELEASE","EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY")
        e=sel(exact_active_unexpired_lease=True,pull_request_open_exact=True,exact_head_ci_success=True,no_pending_checks=True,registry_cas_fresh=True)
        self.assertEqual(self.ev(c,e)["target_action"],"WRITER_LEASE_RELEASE_FRESH_CAS_PATH")
    def test_merge(self):
        c=control("PLAN_EXISTING_MERGE_CLOSE_AUTHORITY_PATH","EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY")
        e=sel(exact_released_lease=True,provider_state_no_drift_after_release=True,merge_close_phase="MERGE",
              pull_request_open_exact=True,pull_request_mergeable=True,exact_head_ci_success=True,no_pending_checks=True,
              head_no_drift=True,no_protected_surface_violation=True)
        self.assertEqual(self.ev(c,e)["target_action"],"WU100_PINNED_MERGE_ELIGIBILITY_PATH")
    def test_close(self):
        c=control("PLAN_EXISTING_MERGE_CLOSE_AUTHORITY_PATH","EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY")
        e=sel(exact_released_lease=True,provider_state_no_drift_after_release=True,merge_close_phase="CLOSE",
              merge_completed=True,actual_merge_sha_readback=True,current_main_equals_actual_merge_sha=True,
              exact_work_unit_issue_open=True,actual_merge_sha=MAIN)
        self.assertEqual(self.ev(c,e)["target_action"],"WU100_EXACT_ISSUE_CLOSE_ELIGIBILITY_PATH")
    def test_runtime_wait(self):
        c=control("WAIT_FOR_PRIVATE_RUNTIME","NONE_WAIT_ONLY")
        self.assertEqual(self.ev(c,{})["decision"],"WAIT_ONLY")
    def test_stop(self):
        c=control("STOP_NO_FRONTIER","NONE_TERMINAL")
        self.assertEqual(self.ev(c,{"frontier_none":True})["decision"],"STOP_ONLY")
    def test_blocked(self):
        c=control("BLOCKED","NONE_FAIL_CLOSED","PLAN_ONLY_CONTROL_LOOP_BLOCKED")
        self.assertEqual(self.ev(c,{})["decision"],"BLOCKED")
    def test_delegation_mismatch_blocks(self):
        c=control("PLAN_EXISTING_WRITER_LEASE_ACQUISITION","EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY")
        self.assertEqual(self.ev(c,{})["decision"],"BLOCKED")
    def test_stale_provider_blocks(self):
        c=control("WAIT_FOR_PRIVATE_RUNTIME","NONE_WAIT_ONLY")
        s=snap(c,{}); s["provider_truth_fresh"]=False
        self.assertEqual(m.evaluate(s,policy=P,check_anchors=False)["decision"],"BLOCKED")
    def test_stale_selected_base_blocks(self):
        c=control("PLAN_EXISTING_BOUNDED_BRANCH_CREATE","EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY")
        e=sel(exact_active_unexpired_lease=True,branch_absent=True,selected_base_sha="b"*40)
        self.assertEqual(self.ev(c,e)["decision"],"BLOCKED")
    def test_missing_merge_evidence_blocks(self):
        c=control("PLAN_EXISTING_MERGE_CLOSE_AUTHORITY_PATH","EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY")
        e=sel(exact_released_lease=True,provider_state_no_drift_after_release=True,merge_close_phase="MERGE")
        self.assertEqual(self.ev(c,e)["decision"],"BLOCKED")
    def test_policy_has_no_authority(self):
        for k in m.FALSE_AUTH: self.assertIs(P[k],False)
    def test_exact_anchor_map(self):
        m.validate_policy(P); m.validate_anchors(P)

if __name__=="__main__": unittest.main()
