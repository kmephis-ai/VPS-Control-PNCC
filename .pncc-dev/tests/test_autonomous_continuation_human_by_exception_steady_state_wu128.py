#!/usr/bin/env python3
import copy, importlib.util, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EVAL=ROOT/'.pncc-dev/scripts/evaluate_autonomous_continuation_human_by_exception_steady_state.py'
spec=importlib.util.spec_from_file_location('wu128_eval',EVAL); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
POLICY=mod.load_json(ROOT/'.pncc-dev/contracts/autonomous-continuation-human-by-exception-steady-state-policy-wu128.json')
MAIN='71e9d6a07f6a15dabb5d358d58a7293eb5f96eec'

def control(decision='PLAN_EXISTING_BOUNDED_BRANCH_CREATE'):
 return {'schema_version':1,'role':'AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION','state':'PLAN_ONLY_CONTROL_LOOP_PASS','decision':decision,'provider_mutation_performed':False,'issue_mutation_performed':False,'branch_mutation_performed':False,'pull_request_mutation_performed':False,'writer_lease_mutation_performed':False,'workflow_rerun_performed':False,'merge_performed':False,'runtime_action_performed':False,'product_runtime_mutation_performed':False}

def admission(decision='ADMIT_EXISTING_WRITER_LEASE_AUTHORITY',delegated='EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY',target='BOUNDED_NON_MAIN_BRANCH_CREATE_PATH',control_decision='PLAN_EXISTING_BOUNDED_BRANCH_CREATE'):
 return {'schema_version':1,'role':'AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_DECISION','state':'PLAN_ONLY_ADMISSION_BLOCKED' if decision=='BLOCKED' else 'PLAN_ONLY_ADMISSION_PASS','decision':decision,'reasons':[],'control_loop_decision':control_decision,'delegated_authority':delegated,'target_action':target,'provider_mutation_performed':False,'issue_mutation_performed':False,'branch_mutation_performed':False,'pull_request_mutation_performed':False,'writer_lease_mutation_performed':False,'workflow_rerun_performed':False,'merge_performed':False,'runtime_action_performed':False}

def snapshot(*,seq=1,txn_state='NOT_STARTED',txn_count=0,readback=False,provider_mutation=False,decision='ADMIT_EXISTING_WRITER_LEASE_AUTHORITY',delegated='EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY',target='BOUNDED_NON_MAIN_BRANCH_CREATE_PATH'):
 ctl='PLAN_EXISTING_BOUNDED_BRANCH_CREATE' if decision=='ADMIT_EXISTING_WRITER_LEASE_AUTHORITY' else {'WAIT_ONLY':'WAIT_ONLY','STOP_ONLY':'STOP_ONLY','SEPARATE_AUTHORITY_REQUIRED':'SEPARATE_AUTHORITY_REQUIRED','BLOCKED':'BLOCKED'}[decision]
 c=control(ctl); a=admission(decision,delegated,target,ctl)
 txn={'delegated_transaction_count':txn_count,'state':txn_state,'delegated_authority_identity':delegated,'target_action':target,'provider_mutation_performed':provider_mutation,'fresh_provider_readback_completed':readback}
 if txn_state=='PERFORMED_READBACK_COMPLETE': txn['provider_state_after']={'fresh':True,'identity':'wu128-test-readback'}
 base={'schema_version':1,'role':'REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_SNAPSHOT','repository':'kmephis-ai/VPS-Control-PNCC','default_branch':'main','provider_truth_fresh':True,'current_main_sha':MAIN,'iteration_sequence':seq,'control_loop_fresh_for_iteration':True,'execution_admission_fresh_for_iteration':True,'control_loop_reused_from_prior_iteration':False,'execution_admission_reused_from_prior_iteration':False,'previous_iteration_fresh_provider_readback_completed':True if seq>1 else False,'interrupted':False,'stale_state':False,'contradiction_detected':False,'anchor_drift_detected':False,'revocation_detected':False,'classified_failure_detected':False,'control_loop_decision':c,'execution_admission_decision':a,'delegated_transaction':txn}
 ops={'schema_version':1,'role':'AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_SNAPSHOT','repository':'kmephis-ai/VPS-Control-PNCC','default_branch':'main','provider_truth_fresh':True,'current_main_sha':MAIN,'admission_current_main_sha':MAIN,'input_mode':'EXECUTION_ADMISSION','owner_exception':None,'execution_admission_decision':copy.deepcopy(a)}
 return {'schema_version':1,'role':'AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_SNAPSHOT','repository':'kmephis-ai/VPS-Control-PNCC','default_branch':'main','provider_truth_fresh':True,'current_main_sha':MAIN,'input_mode':'ITERATION','iteration_sequence':seq,'control_loop_fresh_for_iteration':True,'execution_admission_fresh_for_iteration':True,'operationalization_fresh_for_iteration':True,'control_loop_reused_from_prior_iteration':False,'execution_admission_reused_from_prior_iteration':False,'operationalization_reused_from_prior_iteration':False,'previous_iteration_fresh_provider_readback_completed':True if seq>1 else False,'reusable_steady_state_snapshot':base,'operationalization_snapshot':ops}

class WU128Tests(unittest.TestCase):
 def ev(self,s,p=None): return mod.evaluate(s,policy=p or POLICY,check_anchors=True)
 def test_execute_one_existing_authority_transaction(self):
  r=self.ev(snapshot()); self.assertEqual(r['outcome'],'CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY'); self.assertTrue(r['automatic_continuation_permitted']); self.assertFalse(r['authority_granted'])
 def test_readback_barrier_suppresses_next_mutation(self):
  r=self.ev(snapshot(txn_state='PERFORMED_READBACK_PENDING',txn_count=1,provider_mutation=True)); self.assertEqual(r['outcome'],'READBACK_REQUIRED_BEFORE_NEXT_ITERATION'); self.assertTrue(r['readback_required']); self.assertFalse(r['automatic_continuation_permitted'])
 def test_complete_iteration_allows_only_fresh_next_iteration(self):
  r=self.ev(snapshot(seq=2,txn_state='PERFORMED_READBACK_COMPLETE',txn_count=1,readback=True,provider_mutation=True)); self.assertEqual(r['outcome'],'NEXT_FRESH_ITERATION_ALLOWED'); self.assertTrue(r['next_fresh_iteration_allowed']); self.assertFalse(r['automatic_replay_permitted'])
 def test_second_delegated_transaction_blocks(self):
  r=self.ev(snapshot(txn_state='PERFORMED_READBACK_COMPLETE',txn_count=2,readback=True,provider_mutation=True)); self.assertEqual(r['outcome'],'BLOCKED')
 def test_stale_operationalization_reuse_blocks(self):
  s=snapshot(); s['operationalization_reused_from_prior_iteration']=True; self.assertEqual(self.ev(s)['outcome'],'BLOCKED')
 def test_admission_operationalization_binding_mismatch_blocks(self):
  s=snapshot(); s['operationalization_snapshot']['execution_admission_decision']['target_action']='DIFFERENT'; self.assertEqual(self.ev(s)['outcome'],'BLOCKED')
 def test_wait_only_stays_no_mutation(self):
  s=snapshot(decision='WAIT_ONLY',delegated='NONE_WAIT_ONLY',target=None); r=self.ev(s); self.assertEqual(r['outcome'],'WAIT_ONLY'); self.assertFalse(r['automatic_continuation_permitted'])
 def test_owner_escalation_is_out_of_band_no_replay(self):
  ops={'schema_version':1,'role':'AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_SNAPSHOT','repository':'kmephis-ai/VPS-Control-PNCC','default_branch':'main','provider_truth_fresh':True,'current_main_sha':MAIN,'admission_current_main_sha':MAIN,'input_mode':'OWNER_EXCEPTION','execution_admission_decision':None,'owner_exception':{'classification':'OWNER_ESCALATION_REQUIRED','reason_classification_present':True,'mutation_permitted':False,'automatic_replay_permitted':False}}
  s={'schema_version':1,'role':'AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_SNAPSHOT','repository':'kmephis-ai/VPS-Control-PNCC','default_branch':'main','provider_truth_fresh':True,'current_main_sha':MAIN,'input_mode':'OWNER_EXCEPTION','reusable_steady_state_snapshot':None,'operationalization_fresh_for_iteration':True,'operationalization_reused_from_prior_iteration':False,'operationalization_snapshot':ops}
  r=self.ev(s); self.assertEqual(r['outcome'],'OWNER_ESCALATION_REQUIRED'); self.assertTrue(r['owner_escalation_required']); self.assertFalse(r['automatic_replay_permitted'])
 def test_policy_cannot_grant_authority(self):
  p=copy.deepcopy(POLICY); p['authority_flags']['merge_authority']=True; self.assertEqual(mod.evaluate(snapshot(),policy=p,check_anchors=False)['outcome'],'BLOCKED')

if __name__=='__main__': unittest.main()
