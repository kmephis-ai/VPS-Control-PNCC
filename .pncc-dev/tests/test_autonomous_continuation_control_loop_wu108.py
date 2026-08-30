#!/usr/bin/env python3
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EVAL_PATH=ROOT/'.pncc-dev/scripts/evaluate_autonomous_continuation_control_loop.py'
POLICY_PATH=ROOT/'.pncc-dev/contracts/autonomous-continuation-control-loop-policy.json'
spec=importlib.util.spec_from_file_location('control_loop',EVAL_PATH)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

MAIN='a'*40
OLD='d'*40
HEAD='b'*40
WU='PIPE-WU-108'
ISSUE=263
BRANCH='agent/PIPE-WU-108-autonomous-continuation-control-loop'
PR=264


def policy(): return mod.load_json(POLICY_PATH)

def selected(base=MAIN):
    return {'issue':ISSUE,'work_unit_id':WU,'state':'READY','conflict_domain':'wave5-autonomous-continuation-control-loop-integration',
            'base_sha':base,'branch':None,'runtime_required':False,'materialization_phase':'INTAKE',
            'classification':'EXECUTABLE_READ_ONLY_SELECTION','reason':None}

def continuation(decision='CONTINUE_SELECTED_WORK_UNIT',sel=None):
    if sel is None and decision=='CONTINUE_SELECTED_WORK_UNIT': sel=selected()
    return {'schema_version':1,'role':'PROVIDER_TRUTH_CONTINUATION_DECISION','state':'READ_ONLY_CONTINUATION_PASS',
            'decision':decision,'reasons':[],'selector_guard_state':'PASS','selector_result':None,'selected':sel,
            'materialization_plan':None,'provider_mutation_performed':False,'issue_mutation_performed':False,
            'writer_lease_mutation_performed':False,'merge_performed':False,'runtime_action_performed':False}

def ci(decision='CI_PENDING',head=HEAD,number=PR):
    return {'schema_version':1,'role':'EXACT_HEAD_CI_INSPECTION_CLASSIFICATION_DECISION','state':'READ_ONLY_CI_INSPECTION_PASS',
            'decision':decision,'reasons':[],'pr_number':number,'pr_head_sha':head,'workflow_count':7,
            'pending_workflows':[],'failed_workflows':[],'failure_classification_evidence':[],
            'provider_mutation_performed':False,'workflow_rerun_performed':False,'branch_mutation_performed':False,
            'pull_request_mutation_performed':False,'writer_lease_mutation_performed':False,'merge_performed':False,
            'runtime_action_performed':False,'product_runtime_mutation_performed':False,'next_boundary':'x'}

def execution(lease='NONE',branch_exists=False,branch_head=None,pr=None,post_merge=False):
    return {'work_unit_id':WU,'issue_number':ISSUE,'issue_open':True,'lease_state':lease,
            'lease_exact_binding':False if lease=='NONE' else True,'branch_exists':branch_exists,
            'branch_name':BRANCH if branch_exists else None,'branch_head_sha':branch_head if branch_exists else None,
            'pull_request':pr,'post_merge_recovery':post_merge}

def snapshot(cont=None,exe=None,ci_decision=None,main=MAIN,fresh=True):
    return {'schema_version':1,'role':'AUTONOMOUS_CONTINUATION_CONTROL_LOOP_SNAPSHOT',
            'repository':'kmephis-ai/VPS-Control-PNCC','default_branch':'main','provider_truth_fresh':fresh,
            'current_main_sha':main,'continuation_decision':cont or continuation(),'execution_state':exe,
            'ci_decision':ci_decision}

def open_pr(head=HEAD,base=MAIN): return {'number':PR,'state':'OPEN','base_sha':base,'head_sha':head}

def assert_no_mutation(test,result):
    for field in ('provider_mutation_performed','issue_mutation_performed','branch_mutation_performed',
                  'pull_request_mutation_performed','writer_lease_mutation_performed','workflow_rerun_performed',
                  'merge_performed','runtime_action_performed','product_runtime_mutation_performed'):
        test.assertIs(result[field],False,field)


class ControlLoopTests(unittest.TestCase):
    def evaluate(self,s,p=None,anchors=False):
        r=mod.evaluate_control_loop(s,policy=p or policy(),check_anchors=anchors)
        assert_no_mutation(self,r); return r

    def test_materialization_delegates_existing_grant(self):
        r=self.evaluate(snapshot(cont=continuation('PLAN_MATERIALIZATION',None),exe=None))
        self.assertEqual(r['decision'],'PLAN_EXISTING_MATERIALIZATION_TRANSACTION')
        self.assertEqual(r['delegated_authority'],'EXISTING_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY')

    def test_no_lease_plans_acquisition(self):
        r=self.evaluate(snapshot(exe=execution()))
        self.assertEqual(r['decision'],'PLAN_EXISTING_WRITER_LEASE_ACQUISITION')

    def test_active_lease_without_branch_plans_branch_create(self):
        r=self.evaluate(snapshot(exe=execution('ACTIVE')))
        self.assertEqual(r['decision'],'PLAN_EXISTING_BOUNDED_BRANCH_CREATE')

    def test_active_branch_at_base_continues_bounded_branch(self):
        r=self.evaluate(snapshot(exe=execution('ACTIVE',True,MAIN)))
        self.assertEqual(r['decision'],'CONTINUE_EXISTING_BOUNDED_BRANCH')

    def test_advanced_branch_without_pr_plans_pr_create(self):
        r=self.evaluate(snapshot(exe=execution('ACTIVE',True,HEAD)))
        self.assertEqual(r['decision'],'PLAN_EXISTING_PULL_REQUEST_CREATE')

    def test_open_pr_pending_waits(self):
        r=self.evaluate(snapshot(exe=execution('ACTIVE',True,HEAD,open_pr()),ci_decision=ci('CI_PENDING')))
        self.assertEqual(r['decision'],'WAIT_FOR_EXACT_HEAD_CI')
        self.assertEqual(r['delegated_authority'],'NONE_WAIT_ONLY')

    def test_classified_failure_never_executes_recovery(self):
        for decision in ('HARNESS_OR_VALIDATION_DEFECT_CANDIDATE','PRODUCT_RUNTIME_DEFECT_CANDIDATE','PROVIDER_ENVIRONMENT_AMBIGUITY'):
            with self.subTest(decision=decision):
                r=self.evaluate(snapshot(exe=execution('ACTIVE',True,HEAD,open_pr()),ci_decision=ci(decision)))
                self.assertEqual(r['decision'],'PLAN_CLASSIFIED_FAILURE_RECOVERY')
                self.assertEqual(r['delegated_authority'],'NONE_SEPARATE_RECOVERY_AUTHORITY_REQUIRED')

    def test_success_with_active_lease_plans_release(self):
        r=self.evaluate(snapshot(exe=execution('ACTIVE',True,HEAD,open_pr()),ci_decision=ci('CI_SUCCESS')))
        self.assertEqual(r['decision'],'PLAN_EXISTING_WRITER_LEASE_RELEASE')

    def test_success_with_released_lease_delegates_merge_close(self):
        r=self.evaluate(snapshot(exe=execution('RELEASED',True,HEAD,open_pr()),ci_decision=ci('CI_SUCCESS')))
        self.assertEqual(r['decision'],'PLAN_EXISTING_MERGE_CLOSE_AUTHORITY_PATH')
        self.assertEqual(r['delegated_authority'],'EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY')

    def test_post_merge_interruption_recovers_only_exact_stale_base(self):
        stale=selected(OLD); stale['classification']='STALE_BASE'; stale['reason']='BASE_DOES_NOT_MATCH_DEFAULT_HEAD'
        c=continuation('BLOCKED',None); c['state']='READ_ONLY_CONTINUATION_BLOCKED'; c['reasons']=['SELECTOR_DISPOSITION_BLOCKED']
        c['selector_result']={'schema_version':2,'state':'READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS','decision':'NO_EXECUTABLE_WORK_UNIT',
                              'orchestration_disposition':'BLOCKED','provider_mutation_performed':False,'canonical_work_units':[stale]}
        merged={'number':PR,'state':'MERGED','base_sha':OLD,'head_sha':HEAD,'merge_commit_sha':MAIN}
        r=self.evaluate(snapshot(cont=c,exe=execution('RELEASED',True,HEAD,merged,True),main=MAIN))
        self.assertEqual(r['decision'],'PLAN_EXISTING_MERGE_CLOSE_AUTHORITY_PATH')

    def test_post_merge_wrong_main_readback_blocks(self):
        stale=selected(OLD); stale['classification']='STALE_BASE'; stale['reason']='BASE_DOES_NOT_MATCH_DEFAULT_HEAD'
        c=continuation('BLOCKED',None); c['selector_result']={'schema_version':2,'state':'READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS',
            'decision':'NO_EXECUTABLE_WORK_UNIT','orchestration_disposition':'BLOCKED','provider_mutation_performed':False,'canonical_work_units':[stale]}
        merged={'number':PR,'state':'MERGED','base_sha':OLD,'head_sha':HEAD,'merge_commit_sha':'c'*40}
        r=self.evaluate(snapshot(cont=c,exe=execution('RELEASED',True,HEAD,merged,True)))
        self.assertEqual(r['decision'],'BLOCKED')
        self.assertIn('POST_MERGE_MAIN_READBACK_MISMATCH',r['reasons'][0])

    def test_post_merge_ambiguous_nonterminal_blocks(self):
        stale=selected(OLD); stale['classification']='STALE_BASE'; stale['reason']='BASE_DOES_NOT_MATCH_DEFAULT_HEAD'
        other=copy.deepcopy(stale); other['issue']=999; other['work_unit_id']='PIPE-WU-999'
        c=continuation('BLOCKED',None); c['selector_result']={'schema_version':2,'state':'READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS',
            'decision':'NO_EXECUTABLE_WORK_UNIT','orchestration_disposition':'BLOCKED','provider_mutation_performed':False,'canonical_work_units':[stale,other]}
        merged={'number':PR,'state':'MERGED','base_sha':OLD,'head_sha':HEAD,'merge_commit_sha':MAIN}
        r=self.evaluate(snapshot(cont=c,exe=execution('RELEASED',True,HEAD,merged,True)))
        self.assertEqual(r['decision'],'BLOCKED')

    def test_ci_head_drift_blocks(self):
        r=self.evaluate(snapshot(exe=execution('ACTIVE',True,HEAD,open_pr()),ci_decision=ci('CI_PENDING','c'*40)))
        self.assertEqual(r['decision'],'BLOCKED')
        self.assertIn('CI_PR_BINDING_MISMATCH',r['reasons'][0])

    def test_branch_without_lease_blocks(self):
        r=self.evaluate(snapshot(exe=execution('NONE',True,HEAD)))
        self.assertEqual(r['decision'],'BLOCKED')

    def test_stale_provider_truth_blocks(self):
        r=self.evaluate(snapshot(exe=execution(),fresh=False))
        self.assertEqual(r['decision'],'BLOCKED')

    def test_runtime_and_no_frontier_are_wait_stop_only(self):
        r=self.evaluate(snapshot(cont=continuation('WAITING_RUNTIME',None),exe=None))
        self.assertEqual(r['decision'],'WAIT_FOR_PRIVATE_RUNTIME')
        r=self.evaluate(snapshot(cont=continuation('NO_FRONTIER',None),exe=None))
        self.assertEqual(r['decision'],'STOP_NO_FRONTIER')

    def test_policy_authority_broadening_blocks(self):
        p=policy(); p['merge_authority']=True
        r=self.evaluate(snapshot(exe=execution()),p=p)
        self.assertEqual(r['decision'],'BLOCKED')

    def test_anchor_drift_blocks(self):
        r=mod.evaluate_control_loop(snapshot(exe=execution()),policy=policy(),check_anchors=True,blob_reader=lambda _:'0'*40)
        self.assertEqual(r['decision'],'BLOCKED'); assert_no_mutation(self,r)


if __name__=='__main__': unittest.main()
