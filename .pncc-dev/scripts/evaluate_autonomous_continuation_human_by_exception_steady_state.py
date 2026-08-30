#!/usr/bin/env python3
"""Fail-closed Human-by-Exception steady-state wrapper for PIPE-WU-128."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
POLICY_PATH=ROOT/".pncc-dev/contracts/autonomous-continuation-human-by-exception-steady-state-policy-wu128.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
MUTATING={
 "ADMIT_EXISTING_MATERIALIZATION_AUTHORITY",
 "ADMIT_EXISTING_WRITER_LEASE_AUTHORITY",
 "ADMIT_EXISTING_MERGE_CLOSE_AUTHORITY",
}
NON_MUTATING={"WAIT_ONLY","STOP_ONLY","SEPARATE_AUTHORITY_REQUIRED","BLOCKED"}
MUTATION_FIELDS=("provider_mutation_performed","issue_mutation_performed","branch_mutation_performed","pull_request_mutation_performed","writer_lease_mutation_performed","workflow_rerun_performed","merge_performed","runtime_action_performed")

class HumanByExceptionSteadyStateError(ValueError): pass

def _strict(pairs):
 out={}
 for k,v in pairs:
  if k in out: raise HumanByExceptionSteadyStateError("DUPLICATE_KEY:"+k)
  out[k]=v
 return out

def load_json(path):
 try: return json.loads(Path(path).read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
 except (OSError,UnicodeError,json.JSONDecodeError) as e: raise HumanByExceptionSteadyStateError(f"INVALID_JSON:{Path(path).as_posix()}:{type(e).__name__}") from e

def blob_sha(path):
 b=Path(path).read_bytes(); return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def _module(path,name):
 spec=importlib.util.spec_from_file_location(name,path)
 if spec is None or spec.loader is None: raise HumanByExceptionSteadyStateError("EVALUATOR_IMPORT_FAILED:"+name)
 mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def _all_false(value,name):
 if not isinstance(value,dict) or not value: raise HumanByExceptionSteadyStateError(name+"_MAP_REQUIRED")
 for k,v in value.items():
  if v is not False: raise HumanByExceptionSteadyStateError(name+"_FLAG:"+k)

def validate_policy(p):
 exact={
  "schema_version":1,
  "role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_POLICY",
  "state":"READY",
  "mode":"HUMAN_BY_EXCEPTION_STEADY_STATE_EXISTING_AUTHORITY_ONLY_FAIL_CLOSED",
  "repository":"kmephis-ai/VPS-Control-PNCC",
  "default_branch":"main",
  "snapshot_role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_SNAPSHOT",
  "decision_role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_DECISION",
  "next_boundary":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_EXECUTION_WITH_EXISTING_AUTHORITY_ONLY"}
 if not isinstance(p,dict): raise HumanByExceptionSteadyStateError("POLICY_OBJECT_REQUIRED")
 for k,v in exact.items():
  if p.get(k)!=v: raise HumanByExceptionSteadyStateError("POLICY_FIELD_INVALID:"+k)
 if p.get("work_unit")!={"work_unit_id":"PIPE-WU-128","issue_number":304,"base_sha":"71e9d6a07f6a15dabb5d358d58a7293eb5f96eec","branch":"agent/PIPE-WU-128-human-by-exception-steady-state-existing-authority-only","runtime_required":False}: raise HumanByExceptionSteadyStateError("WORK_UNIT_BINDING_INVALID")
 if p.get("provider_snapshot")!={"state_branch":"pncc-provider-state","state_branch_head_sha":"8da949103d827e3e41a7b3ce80aa6c732b61738f","registry_blob_sha":"9f623561b2f41311277dbc39b8c19cb610797c57","registry_generation":36,"writer_lease_id":"f92e06b1-c5bb-44d4-adf9-3735a9c0b9c1"}: raise HumanByExceptionSteadyStateError("PROVIDER_SNAPSHOT_INVALID")
 req=p.get("iteration_requirements",{})
 required=("fresh_provider_truth_each_iteration","fresh_control_loop_each_iteration","fresh_execution_admission_each_iteration","fresh_operationalization_each_iteration","same_iteration_control_admission_binding","same_iteration_admission_operationalization_semantic_binding","mutating_delegated_authority_identity_must_match_exactly","non_mutating_delegated_authority_projection_must_match_policy","previous_iteration_readback_before_next_iteration","fresh_exact_readback_after_delegated_transaction","stale_control_loop_reuse_forbidden","stale_execution_admission_reuse_forbidden","stale_operationalization_reuse_forbidden","batch_mutation_forbidden","inferred_or_fallback_authority_forbidden")
 for k in required:
  if req.get(k) is not True: raise HumanByExceptionSteadyStateError("ITERATION_REQUIREMENT_MISSING:"+k)
 if req.get("maximum_delegated_transactions_per_iteration")!=1: raise HumanByExceptionSteadyStateError("TRANSACTION_LIMIT_INVALID")
 projection=p.get("non_mutating_admission_projection")
 expected_projection={
  "WAIT_ONLY":{"reusable_steady_state_delegated_authority":"NO_MUTATION","operationalization_delegated_authority":"NONE_WAIT_ONLY"},
  "STOP_ONLY":{"reusable_steady_state_delegated_authority":"NO_MUTATION","operationalization_delegated_authority":"NONE_TERMINAL"},
  "SEPARATE_AUTHORITY_REQUIRED":{"reusable_steady_state_delegated_authority":"NO_MUTATION_AND_SEPARATE_EXPLICIT_AUTHORITY_REQUIRED","operationalization_delegated_authority":"NONE_SEPARATE_RECOVERY_AUTHORITY_REQUIRED"},
  "BLOCKED":{"reusable_steady_state_delegated_authority":"NO_MUTATION_FAIL_CLOSED","operationalization_delegated_authority":"NONE_FAIL_CLOSED"}}
 if projection!=expected_projection: raise HumanByExceptionSteadyStateError("NON_MUTATING_PROJECTION_INVALID")
 expected_outcomes={"EXECUTE_ONE_DELEGATED_TRANSACTION":"CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY","READBACK_REQUIRED_BEFORE_NEXT_ITERATION":"READBACK_REQUIRED_BEFORE_NEXT_ITERATION","ITERATION_COMPLETE_NEXT_FRESH_ITERATION_ALLOWED":"NEXT_FRESH_ITERATION_ALLOWED","WAIT_ONLY":"WAIT_ONLY","STOP_ONLY":"STOP_ONLY","SEPARATE_AUTHORITY_REQUIRED":"SEPARATE_AUTHORITY_REQUIRED","BLOCKED":"BLOCKED"}
 if p.get("outcome_mapping")!=expected_outcomes: raise HumanByExceptionSteadyStateError("OUTCOME_MAPPING_INVALID")
 if p.get("owner_exception_policy")!={"input_mode":"OWNER_EXCEPTION","classification":"OWNER_ESCALATION_REQUIRED","outcome":"OWNER_ESCALATION_REQUIRED","out_of_band_non_mutating_interrupt":True,"mutation_permitted":False,"automatic_replay_permitted":False}: raise HumanByExceptionSteadyStateError("OWNER_EXCEPTION_POLICY_INVALID")
 paths,blobs=p.get("anchor_paths"),p.get("anchor_blobs")
 if not isinstance(paths,dict) or not isinstance(blobs,dict) or set(paths)!=set(blobs): raise HumanByExceptionSteadyStateError("ANCHOR_MAP_INVALID")
 _all_false(p.get("authority_flags"),"POLICY_AUTHORITY")

def validate_anchors(p,root=ROOT):
 for k,rel in p["anchor_paths"].items():
  path=root/rel
  if not path.is_file() or blob_sha(path)!=p["anchor_blobs"][k]: raise HumanByExceptionSteadyStateError("ANCHOR_DRIFT:"+k)
 c=p.get("controlled_execution_input",{}); path=root/c.get("path","")
 if not path.is_file() or blob_sha(path)!=c.get("blob_sha"): raise HumanByExceptionSteadyStateError("CONTROLLED_EXECUTION_ANCHOR_DRIFT")
 e=load_json(path); txn=e.get("controlled_transaction",{})
 if txn.get("transaction_kind")!=c.get("required_transaction_kind") or txn.get("transaction_count")!=c.get("required_transaction_count"): raise HumanByExceptionSteadyStateError("CONTROLLED_EXECUTION_BOUNDARY_INVALID")
 if e.get("authority_broadening_performed") is not False: raise HumanByExceptionSteadyStateError("CONTROLLED_EXECUTION_AUTHORITY_BROADENED")

def _out(outcome,p,*,base=None,op=None,reasons=None):
 base=base or {}; op=op or {}
 return {"schema_version":1,"role":p["decision_role"],"state":"HUMAN_BY_EXCEPTION_STEADY_STATE_BLOCKED" if outcome=="BLOCKED" else "HUMAN_BY_EXCEPTION_STEADY_STATE_PASS","outcome":outcome,"reasons":reasons or [],"base_steady_state_decision":base.get("decision"),"operationalization_outcome":op.get("outcome"),"delegated_authority":op.get("delegated_authority"),"target_action":op.get("target_action"),"automatic_continuation_permitted":outcome=="CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY","automatic_replay_permitted":False,"readback_required":outcome=="READBACK_REQUIRED_BEFORE_NEXT_ITERATION","next_fresh_iteration_allowed":outcome=="NEXT_FRESH_ITERATION_ALLOWED","owner_escalation_required":outcome=="OWNER_ESCALATION_REQUIRED","terminal_stop":outcome=="STOP_ONLY","separate_authority_required":outcome=="SEPARATE_AUTHORITY_REQUIRED","authority_granted":False,"higher_autonomy_authorized":False,"provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,"pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,"merge_performed":False,"runtime_action_performed":False,"product_runtime_mutation_performed":False,"next_boundary":p["next_boundary"]}

def _validate_semantic_admission_binding(base_a,op_a,p):
 if not isinstance(base_a,dict) or not isinstance(op_a,dict): raise HumanByExceptionSteadyStateError("ADMISSION_OBJECT_REQUIRED")
 for k in ("schema_version","role","state","decision","control_loop_decision","target_action"):
  if base_a.get(k)!=op_a.get(k): raise HumanByExceptionSteadyStateError("ADMISSION_SEMANTIC_BINDING_MISMATCH:"+k)
 for k in MUTATION_FIELDS:
  if base_a.get(k) is not False or op_a.get(k) is not False: raise HumanByExceptionSteadyStateError("ADMISSION_MUTATION_REPORTED:"+k)
 decision=base_a.get("decision")
 if decision in MUTATING:
  if base_a.get("delegated_authority")!=op_a.get("delegated_authority"): raise HumanByExceptionSteadyStateError("MUTATING_DELEGATED_AUTHORITY_MISMATCH")
  return
 if decision in NON_MUTATING:
  mapping=p["non_mutating_admission_projection"][decision]
  if base_a.get("delegated_authority")!=mapping["reusable_steady_state_delegated_authority"]: raise HumanByExceptionSteadyStateError("BASE_NON_MUTATING_DELEGATION_INVALID")
  if op_a.get("delegated_authority")!=mapping["operationalization_delegated_authority"]: raise HumanByExceptionSteadyStateError("OP_NON_MUTATING_DELEGATION_INVALID")
  return
 raise HumanByExceptionSteadyStateError("ADMISSION_DECISION_INVALID")

def evaluate(snapshot,*,policy=None,root=ROOT,check_anchors=True):
 p=policy if policy is not None else load_json(POLICY_PATH)
 try:
  validate_policy(p)
  if check_anchors: validate_anchors(p,root)
  if not isinstance(snapshot,dict) or snapshot.get("schema_version")!=1 or snapshot.get("role")!=p["snapshot_role"]: raise HumanByExceptionSteadyStateError("SNAPSHOT_IDENTITY_INVALID")
  if snapshot.get("repository")!=p["repository"] or snapshot.get("default_branch")!=p["default_branch"]: raise HumanByExceptionSteadyStateError("SNAPSHOT_REPOSITORY_INVALID")
  if snapshot.get("provider_truth_fresh") is not True: raise HumanByExceptionSteadyStateError("PROVIDER_TRUTH_NOT_FRESH")
  current=snapshot.get("current_main_sha")
  if not isinstance(current,str) or SHA40.fullmatch(current) is None: raise HumanByExceptionSteadyStateError("MAIN_SHA_INVALID")
  opmod=_module(root/".pncc-dev/scripts/evaluate_autonomous_continuation_human_by_exception_operationalization.py","pncc_hbe_op_wu128")
  mode=snapshot.get("input_mode")
  if mode=="OWNER_EXCEPTION":
   if snapshot.get("reusable_steady_state_snapshot") is not None: raise HumanByExceptionSteadyStateError("OWNER_EXCEPTION_STEADY_STATE_AMBIGUOUS")
   if snapshot.get("operationalization_fresh_for_iteration") is not True or snapshot.get("operationalization_reused_from_prior_iteration") is not False: raise HumanByExceptionSteadyStateError("OWNER_EXCEPTION_OPERATIONALIZATION_FRESHNESS_INVALID")
   ops=snapshot.get("operationalization_snapshot")
   if not isinstance(ops,dict) or ops.get("current_main_sha")!=current: raise HumanByExceptionSteadyStateError("OWNER_EXCEPTION_MAIN_BINDING_INVALID")
   op=opmod.evaluate(ops,check_anchors=check_anchors)
   if op.get("outcome")!="OWNER_ESCALATION_REQUIRED" or op.get("automatic_replay_permitted") is not False or op.get("authority_granted") is not False: raise HumanByExceptionSteadyStateError("OWNER_EXCEPTION_DECISION_INVALID")
   return _out("OWNER_ESCALATION_REQUIRED",p,op=op)
  if mode!="ITERATION": raise HumanByExceptionSteadyStateError("INPUT_MODE_INVALID")
  seq=snapshot.get("iteration_sequence")
  if not isinstance(seq,int) or isinstance(seq,bool) or seq<1: raise HumanByExceptionSteadyStateError("ITERATION_SEQUENCE_INVALID")
  for k in ("control_loop_fresh_for_iteration","execution_admission_fresh_for_iteration","operationalization_fresh_for_iteration"):
   if snapshot.get(k) is not True: raise HumanByExceptionSteadyStateError("FRESHNESS_REQUIRED:"+k)
  for k in ("control_loop_reused_from_prior_iteration","execution_admission_reused_from_prior_iteration","operationalization_reused_from_prior_iteration"):
   if snapshot.get(k) is not False: raise HumanByExceptionSteadyStateError("STALE_REUSE_FORBIDDEN:"+k)
  if seq>1 and snapshot.get("previous_iteration_fresh_provider_readback_completed") is not True: raise HumanByExceptionSteadyStateError("PREVIOUS_ITERATION_READBACK_REQUIRED")
  if seq==1 and snapshot.get("previous_iteration_fresh_provider_readback_completed") not in (None,False): raise HumanByExceptionSteadyStateError("FIRST_ITERATION_PREVIOUS_READBACK_INVALID")
  base_snapshot=snapshot.get("reusable_steady_state_snapshot"); ops=snapshot.get("operationalization_snapshot")
  if not isinstance(base_snapshot,dict) or not isinstance(ops,dict): raise HumanByExceptionSteadyStateError("NESTED_SNAPSHOT_REQUIRED")
  if base_snapshot.get("iteration_sequence")!=seq or base_snapshot.get("current_main_sha")!=current: raise HumanByExceptionSteadyStateError("BASE_ITERATION_BINDING_INVALID")
  if ops.get("current_main_sha")!=current or ops.get("admission_current_main_sha")!=current: raise HumanByExceptionSteadyStateError("OPERATIONALIZATION_MAIN_BINDING_INVALID")
  if ops.get("input_mode")!="EXECUTION_ADMISSION": raise HumanByExceptionSteadyStateError("OPERATIONALIZATION_MODE_INVALID")
  _validate_semantic_admission_binding(base_snapshot.get("execution_admission_decision"),ops.get("execution_admission_decision"),p)
  basemod=_module(root/".pncc-dev/scripts/evaluate_reusable_autonomous_continuation_steady_state.py","pncc_base_steady_wu128")
  base=basemod.evaluate(base_snapshot,check_anchors=check_anchors); op=opmod.evaluate(ops,check_anchors=check_anchors)
  b=base.get("decision"); o=op.get("outcome")
  if op.get("authority_granted") is not False or op.get("higher_autonomy_authorized") is not False or op.get("automatic_replay_permitted") is not False: raise HumanByExceptionSteadyStateError("OPERATIONALIZATION_AUTHORITY_BOUNDARY_INVALID")
  if b in ("EXECUTE_ONE_DELEGATED_TRANSACTION","READBACK_REQUIRED_BEFORE_NEXT_ITERATION","ITERATION_COMPLETE_NEXT_FRESH_ITERATION_ALLOWED"):
   if o!="CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY": raise HumanByExceptionSteadyStateError("MUTATING_ADMISSION_OPERATIONALIZATION_MISMATCH")
   if op.get("delegated_authority")!=base.get("delegated_authority") or op.get("target_action")!=base.get("target_action"): raise HumanByExceptionSteadyStateError("DELEGATED_TRANSACTION_BINDING_MISMATCH")
  elif b in ("WAIT_ONLY","STOP_ONLY","SEPARATE_AUTHORITY_REQUIRED","BLOCKED"):
   if o!=b: raise HumanByExceptionSteadyStateError("NON_MUTATING_OUTCOME_MISMATCH")
  else: raise HumanByExceptionSteadyStateError("BASE_DECISION_INVALID")
  return _out(p["outcome_mapping"][b],p,base=base,op=op)
 except (HumanByExceptionSteadyStateError,KeyError,TypeError) as e:
  try: validate_policy(p); return _out("BLOCKED",p,reasons=[str(e)])
  except Exception: return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_DECISION","state":"HUMAN_BY_EXCEPTION_STEADY_STATE_BLOCKED","outcome":"BLOCKED","reasons":[str(e)],"automatic_continuation_permitted":False,"automatic_replay_permitted":False,"authority_granted":False,"higher_autonomy_authorized":False}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--policy",default=str(POLICY_PATH)); a=ap.parse_args()
 p=load_json(a.policy); out=evaluate(load_json(a.input),policy=p); print(json.dumps(out,indent=2,sort_keys=True)); return 2 if out["outcome"]=="BLOCKED" else 0
if __name__=="__main__": raise SystemExit(main())
