#!/usr/bin/env python3
"""PLAN_ONLY fail-closed steady-state wrapper for the reusable continuation executor."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
POLICY_PATH=ROOT/".pncc-dev/contracts/reusable-autonomous-continuation-steady-state-policy.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
FALSE_AUTH=(
"direct_provider_mutation_authority","direct_issue_create_authority","direct_issue_update_authority",
"direct_issue_close_authority","direct_branch_mutation_authority","direct_pull_request_mutation_authority",
"direct_writer_lease_mutation_authority","direct_workflow_rerun_authority","direct_merge_authority",
"runtime_action_authority","product_runtime_mutation_authority","adwf_binding_mutation_authority",
"adwf_repository_mutation_authority","release_tag_promotion_authority","ruleset_policy_mutation_authority",
"private_evidence_publication_authority","force_ref_update_authority","silent_lease_steal_authority",
"reserve_1080_lifecycle_mutation_authority","primary_1081_lifecycle_mutation_authority")

class SteadyStateError(ValueError): pass

def _strict(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise SteadyStateError("DUPLICATE_KEY:"+k)
        out[k]=v
    return out

def load_json(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
    except (OSError,UnicodeError,json.JSONDecodeError) as e:
        raise SteadyStateError(f"INVALID_JSON:{Path(path).as_posix()}:{type(e).__name__}") from e

def blob_sha(path):
    b=Path(path).read_bytes()
    return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def validate_policy(p):
    if p.get("schema_version")!=1 or p.get("role")!="REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_POLICY":
        raise SteadyStateError("POLICY_IDENTITY_INVALID")
    exact={
      "mode":"PLAN_ONLY_STEADY_STATE_FAIL_CLOSED",
      "repository":"kmephis-ai/VPS-Control-PNCC",
      "default_branch":"main",
      "snapshot_role":"REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_SNAPSHOT",
      "decision_role":"REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_DECISION",
      "control_loop_role":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION",
      "execution_admission_role":"AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_DECISION",
      "first_transaction_evidence_work_unit_id":"PIPE-WU-112",
      "first_transaction_evidence_blob_sha":"647e04524f6095fb23996386627dab92a6d5ec9d",
      "next_boundary":"REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_EXECUTION"}
    for k,v in exact.items():
        if p.get(k)!=v: raise SteadyStateError("POLICY_FIELD_INVALID:"+k)
    required=(
      "fresh_provider_truth_required_each_iteration","fresh_control_loop_required_each_iteration",
      "fresh_execution_admission_required_each_iteration","same_iteration_control_loop_admission_binding_required",
      "previous_iteration_readback_required_before_next_iteration",
      "fresh_provider_readback_required_after_delegated_transaction",
      "stale_control_loop_reuse_forbidden","stale_execution_admission_reuse_forbidden",
      "batch_provider_mutation_forbidden","inferred_or_fallback_authority_forbidden",
      "delegated_authority_must_match_execution_admission",
      "delegated_target_action_must_match_execution_admission")
    for k in required:
        if p.get(k) is not True: raise SteadyStateError("POLICY_REQUIRED_TRUE:"+k)
    if p.get("maximum_delegated_transactions_per_iteration")!=1:
        raise SteadyStateError("POLICY_TRANSACTION_LIMIT_INVALID")
    mut=p.get("mutating_admission_decisions"); non=p.get("non_mutating_admission_decisions")
    deleg=p.get("delegated_authority_identity"); decisions=p.get("iteration_decisions")
    if not isinstance(mut,list) or not isinstance(non,list) or not mut or not non:
        raise SteadyStateError("POLICY_ADMISSION_SETS_INVALID")
    if set(mut)&set(non) or set(deleg)!=(set(mut)|set(non)):
        raise SteadyStateError("POLICY_DELEGATION_MAP_INVALID")
    if not isinstance(decisions,list) or "BLOCKED" not in decisions or len(decisions)!=len(set(decisions)):
        raise SteadyStateError("POLICY_DECISIONS_INVALID")
    flags=p.get("failure_flags"); behavior=p.get("failure_behavior")
    if not isinstance(flags,list) or not isinstance(behavior,dict) or set(flags)!=set(behavior):
        raise SteadyStateError("POLICY_FAILURE_MAP_INVALID")
    paths,blobs=p.get("anchor_paths"),p.get("anchor_blobs")
    if not isinstance(paths,dict) or not isinstance(blobs,dict) or set(paths)!=set(blobs):
        raise SteadyStateError("POLICY_ANCHOR_MAP_INVALID")
    for k in FALSE_AUTH:
        if p.get(k) is not False: raise SteadyStateError("POLICY_AUTHORITY_PRESENT:"+k)

def validate_anchors(p,root=ROOT):
    for k,rel in sorted(p["anchor_paths"].items()):
        path=root/rel
        if not path.is_file(): raise SteadyStateError("ANCHOR_MISSING:"+k)
        if blob_sha(path)!=p["anchor_blobs"][k]: raise SteadyStateError("ANCHOR_DRIFT:"+k)

def _sha(v,name):
    if not isinstance(v,str) or SHA40.fullmatch(v) is None: raise SteadyStateError("SHA_INVALID:"+name)
    return v

def _no_plan_mutation(obj,prefix):
    for k in ("provider_mutation_performed","issue_mutation_performed","branch_mutation_performed",
              "pull_request_mutation_performed","writer_lease_mutation_performed","workflow_rerun_performed",
              "merge_performed","runtime_action_performed"):
        if obj.get(k) is not False: raise SteadyStateError(prefix+"_MUTATION_REPORTED:"+k)

def _out(decision,p,*,admission=None,reasons=None,transaction_count=0,readback_required=False):
    return {
      "schema_version":1,"role":p["decision_role"],
      "state":"STEADY_STATE_BLOCKED" if decision=="BLOCKED" else "STEADY_STATE_PASS",
      "decision":decision,"reasons":reasons or [],
      "execution_admission_decision":None if not isinstance(admission,dict) else admission.get("decision"),
      "delegated_authority":None if not isinstance(admission,dict) else admission.get("delegated_authority"),
      "target_action":None if not isinstance(admission,dict) else admission.get("target_action"),
      "delegated_transaction_count":transaction_count,
      "readback_required":readback_required,
      "provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,
      "pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,
      "workflow_rerun_performed":False,"merge_performed":False,"runtime_action_performed":False,
      "product_runtime_mutation_performed":False,"authority_broadening_performed":False,
      "next_boundary":p["next_boundary"]}

def _validate_control(control,p):
    if not isinstance(control,dict) or control.get("schema_version")!=1 or control.get("role")!=p["control_loop_role"]:
        raise SteadyStateError("CONTROL_LOOP_IDENTITY_INVALID")
    if control.get("state") not in {"PLAN_ONLY_CONTROL_LOOP_PASS","PLAN_ONLY_CONTROL_LOOP_BLOCKED"}:
        raise SteadyStateError("CONTROL_LOOP_STATE_INVALID")
    _no_plan_mutation(control,"CONTROL_LOOP")
    if control.get("product_runtime_mutation_performed") is not False:
        raise SteadyStateError("CONTROL_LOOP_PRODUCT_MUTATION_REPORTED")
    if not isinstance(control.get("decision"),str) or not control["decision"]:
        raise SteadyStateError("CONTROL_LOOP_DECISION_INVALID")

def _validate_admission(admission,p,control):
    if not isinstance(admission,dict) or admission.get("schema_version")!=1 or admission.get("role")!=p["execution_admission_role"]:
        raise SteadyStateError("ADMISSION_IDENTITY_INVALID")
    if admission.get("state") not in {"PLAN_ONLY_ADMISSION_PASS","PLAN_ONLY_ADMISSION_BLOCKED"}:
        raise SteadyStateError("ADMISSION_STATE_INVALID")
    _no_plan_mutation(admission,"ADMISSION")
    decision=admission.get("decision")
    if decision not in p["delegated_authority_identity"]:
        raise SteadyStateError("ADMISSION_DECISION_INVALID")
    if admission.get("control_loop_decision")!=control.get("decision"):
        raise SteadyStateError("CONTROL_ADMISSION_BINDING_MISMATCH")
    expected=p["delegated_authority_identity"][decision]
    if admission.get("delegated_authority")!=expected:
        raise SteadyStateError("ADMISSION_DELEGATION_MISMATCH")
    if decision in p["mutating_admission_decisions"]:
        target=admission.get("target_action")
        if not isinstance(target,str) or not target:
            raise SteadyStateError("ADMISSION_TARGET_REQUIRED")
    return decision

def evaluate(snapshot,*,policy=None,root=ROOT,check_anchors=True):
    p=policy or load_json(POLICY_PATH)
    admission=None
    try:
        validate_policy(p)
        if check_anchors: validate_anchors(p,root=root)
        if not isinstance(snapshot,dict) or snapshot.get("schema_version")!=1 or snapshot.get("role")!=p["snapshot_role"]:
            raise SteadyStateError("SNAPSHOT_IDENTITY_INVALID")
        if snapshot.get("repository")!=p["repository"] or snapshot.get("default_branch")!=p["default_branch"]:
            raise SteadyStateError("PROVIDER_IDENTITY_MISMATCH")
        if snapshot.get("provider_truth_fresh") is not True:
            raise SteadyStateError("PROVIDER_TRUTH_NOT_FRESH")
        _sha(snapshot.get("current_main_sha"),"current_main_sha")
        seq=snapshot.get("iteration_sequence")
        if not isinstance(seq,int) or isinstance(seq,bool) or seq<1:
            raise SteadyStateError("ITERATION_SEQUENCE_INVALID")
        if snapshot.get("control_loop_fresh_for_iteration") is not True:
            raise SteadyStateError("CONTROL_LOOP_NOT_FRESH")
        if snapshot.get("execution_admission_fresh_for_iteration") is not True:
            raise SteadyStateError("ADMISSION_NOT_FRESH")
        if snapshot.get("control_loop_reused_from_prior_iteration") is not False:
            raise SteadyStateError("CONTROL_LOOP_REUSE_FORBIDDEN")
        if snapshot.get("execution_admission_reused_from_prior_iteration") is not False:
            raise SteadyStateError("ADMISSION_REUSE_FORBIDDEN")
        if seq>1 and snapshot.get("previous_iteration_fresh_provider_readback_completed") is not True:
            raise SteadyStateError("PREVIOUS_ITERATION_READBACK_REQUIRED")
        if seq==1 and snapshot.get("previous_iteration_fresh_provider_readback_completed") not in {None,False}:
            raise SteadyStateError("FIRST_ITERATION_PREVIOUS_READBACK_INVALID")

        for flag in p["failure_flags"]:
            value=snapshot.get(flag)
            if value is not False:
                if flag=="classified_failure_detected" and value is True:
                    txn=snapshot.get("delegated_transaction")
                    if isinstance(txn,dict) and txn.get("delegated_transaction_count",0)!=0:
                        raise SteadyStateError("CLASSIFIED_FAILURE_WITH_TRANSACTION_FORBIDDEN")
                    return _out("SEPARATE_AUTHORITY_REQUIRED",p,reasons=["CLASSIFIED_FAILURE_NO_GUESSED_RECOVERY"])
                raise SteadyStateError("FAIL_CLOSED_FLAG:"+flag)

        control=snapshot.get("control_loop_decision"); _validate_control(control,p)
        admission=snapshot.get("execution_admission_decision"); decision=_validate_admission(admission,p,control)

        txn=snapshot.get("delegated_transaction")
        if not isinstance(txn,dict): raise SteadyStateError("DELEGATED_TRANSACTION_EVIDENCE_REQUIRED")
        count=txn.get("delegated_transaction_count")
        if not isinstance(count,int) or isinstance(count,bool) or count<0 or count>1:
            raise SteadyStateError("DELEGATED_TRANSACTION_COUNT_INVALID")
        state=txn.get("state")
        if state not in {"NOT_STARTED","PERFORMED_READBACK_PENDING","PERFORMED_READBACK_COMPLETE"}:
            raise SteadyStateError("DELEGATED_TRANSACTION_STATE_INVALID")
        if state=="NOT_STARTED" and count!=0: raise SteadyStateError("NOT_STARTED_COUNT_INVALID")
        if state!="NOT_STARTED" and count!=1: raise SteadyStateError("PERFORMED_COUNT_INVALID")

        if decision in p["non_mutating_admission_decisions"]:
            if count!=0 or state!="NOT_STARTED":
                raise SteadyStateError("NON_MUTATING_DECISION_TRANSACTION_FORBIDDEN")
            if txn.get("provider_mutation_performed") is not False:
                raise SteadyStateError("NON_MUTATING_DECISION_MUTATION_REPORTED")
            mapping={"WAIT_ONLY":"WAIT_ONLY","STOP_ONLY":"STOP_ONLY",
                     "SEPARATE_AUTHORITY_REQUIRED":"SEPARATE_AUTHORITY_REQUIRED","BLOCKED":"BLOCKED"}
            return _out(mapping[decision],p,admission=admission)

        if txn.get("delegated_authority_identity")!=admission.get("delegated_authority"):
            raise SteadyStateError("TRANSACTION_DELEGATION_MISMATCH")
        if txn.get("target_action")!=admission.get("target_action"):
            raise SteadyStateError("TRANSACTION_TARGET_MISMATCH")

        if state=="NOT_STARTED":
            if txn.get("provider_mutation_performed") is not False:
                raise SteadyStateError("NOT_STARTED_MUTATION_REPORTED")
            if txn.get("fresh_provider_readback_completed") is not False:
                raise SteadyStateError("NOT_STARTED_READBACK_INVALID")
            return _out("EXECUTE_ONE_DELEGATED_TRANSACTION",p,admission=admission,transaction_count=0)

        if txn.get("provider_mutation_performed") is not True:
            raise SteadyStateError("PERFORMED_TRANSACTION_MUTATION_EVIDENCE_REQUIRED")
        if state=="PERFORMED_READBACK_PENDING":
            if txn.get("fresh_provider_readback_completed") is not False:
                raise SteadyStateError("PENDING_READBACK_FLAG_INVALID")
            return _out("READBACK_REQUIRED_BEFORE_NEXT_ITERATION",p,admission=admission,
                        transaction_count=1,readback_required=True)

        if txn.get("fresh_provider_readback_completed") is not True:
            raise SteadyStateError("FRESH_PROVIDER_READBACK_REQUIRED")
        after=txn.get("provider_state_after")
        if not isinstance(after,dict) or after.get("fresh") is not True:
            raise SteadyStateError("PROVIDER_STATE_AFTER_FRESH_REQUIRED")
        if not isinstance(after.get("identity"),str) or not after["identity"]:
            raise SteadyStateError("PROVIDER_STATE_AFTER_IDENTITY_REQUIRED")
        return _out("ITERATION_COMPLETE_NEXT_FRESH_ITERATION_ALLOWED",p,admission=admission,transaction_count=1)
    except (SteadyStateError,KeyError,TypeError) as exc:
        try: validate_policy(p)
        except Exception: pass
        return _out("BLOCKED",p,admission=admission,reasons=[str(exc)])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--policy",default=str(POLICY_PATH))
    a=ap.parse_args()
    p=load_json(a.policy)
    result=evaluate(load_json(a.input),policy=p)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 2 if result["decision"]=="BLOCKED" else 0

if __name__=="__main__": raise SystemExit(main())
