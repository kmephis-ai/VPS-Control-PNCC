#!/usr/bin/env python3
"""Fail-closed Human-by-Exception operationalizer for PIPE-WU-126."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
POLICY_PATH=ROOT/".pncc-dev/contracts/autonomous-continuation-human-by-exception-operationalization-policy-wu126.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
MUTATION_PERFORMED=("provider_mutation_performed","issue_mutation_performed","branch_mutation_performed","pull_request_mutation_performed","writer_lease_mutation_performed","workflow_rerun_performed","merge_performed","runtime_action_performed")
ADMITTED={
 "ADMIT_EXISTING_MATERIALIZATION_AUTHORITY":"EXISTING_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY",
 "ADMIT_EXISTING_WRITER_LEASE_AUTHORITY":"EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY",
 "ADMIT_EXISTING_MERGE_CLOSE_AUTHORITY":"EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY",
}
NON_MUTATING={
 "WAIT_ONLY":("WAIT_ONLY","NONE_WAIT_ONLY"),
 "STOP_ONLY":("STOP_ONLY","NONE_TERMINAL"),
 "SEPARATE_AUTHORITY_REQUIRED":("SEPARATE_AUTHORITY_REQUIRED","NONE_SEPARATE_RECOVERY_AUTHORITY_REQUIRED"),
 "BLOCKED":("BLOCKED","NONE_FAIL_CLOSED"),
}

class OperationalizationError(ValueError): pass

def _strict(pairs):
 out={}
 for k,v in pairs:
  if k in out: raise OperationalizationError("DUPLICATE_KEY:"+k)
  out[k]=v
 return out

def load_json(path):
 try: return json.loads(Path(path).read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
 except (OSError,UnicodeError,json.JSONDecodeError) as e: raise OperationalizationError(f"INVALID_JSON:{Path(path).as_posix()}:{type(e).__name__}") from e

def blob_sha(path):
 b=Path(path).read_bytes(); return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def _all_false(value,name):
 if not isinstance(value,dict) or not value: raise OperationalizationError(name+"_MAP_REQUIRED")
 for k,v in value.items():
  if v is not False: raise OperationalizationError(name+"_FLAG:"+k)

def validate_policy(p):
 exact={"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_POLICY","state":"READY","mode":"HUMAN_BY_EXCEPTION_EXISTING_AUTHORITY_ONLY","repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main","snapshot_role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_SNAPSHOT","next_boundary":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_EXECUTION_WITH_EXISTING_AUTHORITY_ONLY"}
 if not isinstance(p,dict): raise OperationalizationError("POLICY_OBJECT_REQUIRED")
 for k,v in exact.items():
  if p.get(k)!=v: raise OperationalizationError("POLICY_FIELD_INVALID:"+k)
 if p.get("work_unit")!={"work_unit_id":"PIPE-WU-126","issue_number":300,"base_sha":"0114ebb9f4e49d24922500803803b5507da7aa7c","branch":"agent/PIPE-WU-126-human-by-exception-operationalization-existing-authority-only","runtime_required":False}: raise OperationalizationError("WORK_UNIT_BINDING_INVALID")
 if p.get("provider_snapshot")!={"state_branch":"pncc-provider-state","state_branch_head_sha":"13c8eeb0f91a8e0732c0aa89ea26bfc1199a2a5e","registry_blob_sha":"91ead615f54e43c6149f99546b7177b6cc7c714f","registry_generation":34,"writer_lease_id":"c9f6690a-5db3-486b-b11b-30d300ffc98e"}: raise OperationalizationError("PROVIDER_SNAPSHOT_INVALID")
 d=p.get("decision_input",{})
 if d.get("required_outcome")!="APPROVE_HUMAN_BY_EXCEPTION_WITH_EXISTING_AUTHORITY_ONLY" or d.get("authority_granted") is not False or d.get("higher_autonomy_authorized") is not False: raise OperationalizationError("DECISION_BOUNDARY_INVALID")
 paths,blobs=p.get("anchor_paths"),p.get("anchor_blobs")
 if not isinstance(paths,dict) or not isinstance(blobs,dict) or set(paths)!=set(blobs): raise OperationalizationError("ANCHOR_MAP_INVALID")
 admitted=p.get("admitted_existing_authority_mapping")
 if not isinstance(admitted,dict) or set(admitted)!=set(ADMITTED): raise OperationalizationError("ADMITTED_MAPPING_INVALID")
 for k,v in ADMITTED.items():
  if admitted[k]!={"delegated_authority":v,"outcome":"CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY"}: raise OperationalizationError("ADMITTED_MAPPING_INVALID:"+k)
 if p.get("non_mutating_mapping")!={k:v[0] for k,v in NON_MUTATING.items()}: raise OperationalizationError("NON_MUTATING_MAPPING_INVALID")
 if p.get("owner_exception_mapping")!={"classification":"OWNER_ESCALATION_REQUIRED","outcome":"OWNER_ESCALATION_REQUIRED","mutation_permitted":False,"automatic_replay_permitted":False}: raise OperationalizationError("OWNER_EXCEPTION_MAPPING_INVALID")
 _all_false(p.get("authority_flags"),"POLICY_AUTHORITY")

def validate_anchors(p,root=ROOT):
 for k,rel in p["anchor_paths"].items():
  path=root/rel
  if not path.is_file() or blob_sha(path)!=p["anchor_blobs"][k]: raise OperationalizationError("ANCHOR_DRIFT:"+k)
 d=p["decision_input"]; path=root/d["path"]
 if not path.is_file() or blob_sha(path)!=d["blob_sha"]: raise OperationalizationError("DECISION_ANCHOR_DRIFT")
 value=load_json(path)
 if value.get("decision_outcome")!=d["required_outcome"] or value.get("authority_granted") is not False or value.get("higher_autonomy_authorized") is not False: raise OperationalizationError("DECISION_CANONICAL_BOUNDARY_INVALID")

def _result(outcome,p,delegated,target=None,reasons=None):
 return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_DECISION","state":"HUMAN_BY_EXCEPTION_OPERATIONALIZATION_BLOCKED" if outcome=="BLOCKED" else "HUMAN_BY_EXCEPTION_OPERATIONALIZATION_PASS","outcome":outcome,"delegated_authority":delegated,"target_action":target,"reasons":reasons or [],"automatic_continuation_permitted":outcome=="CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY","automatic_replay_permitted":False,"terminal_stop":outcome=="STOP_ONLY","owner_escalation_required":outcome=="OWNER_ESCALATION_REQUIRED","separate_authority_required":outcome=="SEPARATE_AUTHORITY_REQUIRED","authority_granted":False,"higher_autonomy_authorized":False,"provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,"pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,"merge_performed":False,"runtime_action_performed":False,"product_runtime_mutation_performed":False,"next_boundary":p["next_boundary"]}

def evaluate(snapshot,*,policy=None,root=ROOT,check_anchors=True):
 p=policy if policy is not None else load_json(POLICY_PATH)
 try:
  validate_policy(p)
  if check_anchors: validate_anchors(p,root)
  if not isinstance(snapshot,dict) or snapshot.get("schema_version")!=1 or snapshot.get("role")!=p["snapshot_role"]: raise OperationalizationError("SNAPSHOT_IDENTITY_INVALID")
  if snapshot.get("repository")!=p["repository"] or snapshot.get("default_branch")!=p["default_branch"]: raise OperationalizationError("SNAPSHOT_REPOSITORY_INVALID")
  if snapshot.get("provider_truth_fresh") is not True: raise OperationalizationError("PROVIDER_TRUTH_NOT_FRESH")
  current=snapshot.get("current_main_sha"); admission_main=snapshot.get("admission_current_main_sha")
  if not isinstance(current,str) or SHA40.fullmatch(current) is None or not isinstance(admission_main,str) or SHA40.fullmatch(admission_main) is None: raise OperationalizationError("MAIN_SHA_INVALID")
  if current!=admission_main: raise OperationalizationError("ADMISSION_MAIN_BINDING_MISMATCH")
  mode=snapshot.get("input_mode")
  if mode=="OWNER_EXCEPTION":
   if snapshot.get("execution_admission_decision") is not None: raise OperationalizationError("OWNER_EXCEPTION_ADMISSION_AMBIGUOUS")
   e=snapshot.get("owner_exception")
   if not isinstance(e,dict) or e.get("classification")!="OWNER_ESCALATION_REQUIRED" or e.get("reason_classification_present") is not True or e.get("mutation_permitted") is not False or e.get("automatic_replay_permitted") is not False: raise OperationalizationError("OWNER_EXCEPTION_BOUNDARY_INVALID")
   return _result("OWNER_ESCALATION_REQUIRED",p,"NONE_OWNER_ESCALATION_REQUIRED","SURFACE_OWNER_EXCEPTION_NO_MUTATION")
  if mode!="EXECUTION_ADMISSION": raise OperationalizationError("INPUT_MODE_INVALID")
  if snapshot.get("owner_exception") is not None: raise OperationalizationError("ADMISSION_OWNER_EXCEPTION_AMBIGUOUS")
  a=snapshot.get("execution_admission_decision")
  if not isinstance(a,dict) or a.get("schema_version")!=1 or a.get("role")!="AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_DECISION": raise OperationalizationError("ADMISSION_IDENTITY_INVALID")
  decision=a.get("decision")
  expected_state="PLAN_ONLY_ADMISSION_BLOCKED" if decision=="BLOCKED" else "PLAN_ONLY_ADMISSION_PASS"
  if a.get("state")!=expected_state: raise OperationalizationError("ADMISSION_STATE_INVALID")
  for k in MUTATION_PERFORMED:
   if a.get(k) is not False: raise OperationalizationError("ADMISSION_MUTATION_REPORTED:"+k)
  if decision in ADMITTED:
   if a.get("delegated_authority")!=ADMITTED[decision]: raise OperationalizationError("ADMISSION_DELEGATION_MISMATCH")
   target=a.get("target_action")
   if not isinstance(target,str) or not target: raise OperationalizationError("ADMISSION_TARGET_REQUIRED")
   return _result("CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY",p,ADMITTED[decision],target)
  if decision in NON_MUTATING:
   outcome,delegated=NON_MUTATING[decision]
   if a.get("delegated_authority")!=delegated: raise OperationalizationError("NON_MUTATING_DELEGATION_MISMATCH")
   return _result(outcome,p,delegated,a.get("target_action"))
  raise OperationalizationError("ADMISSION_DECISION_INVALID")
 except (OperationalizationError,KeyError,TypeError) as e:
  try: validate_policy(p); return _result("BLOCKED",p,"NONE_FAIL_CLOSED",reasons=[str(e)])
  except Exception: return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_DECISION","state":"HUMAN_BY_EXCEPTION_OPERATIONALIZATION_BLOCKED","outcome":"BLOCKED","delegated_authority":"NONE_FAIL_CLOSED","reasons":[str(e)],"automatic_continuation_permitted":False,"automatic_replay_permitted":False,"authority_granted":False,"higher_autonomy_authorized":False}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--policy",default=str(POLICY_PATH)); a=ap.parse_args()
 p=load_json(a.policy); out=evaluate(load_json(a.input),policy=p); print(json.dumps(out,indent=2,sort_keys=True)); return 2 if out["outcome"]=="BLOCKED" else 0
if __name__=="__main__": raise SystemExit(main())
