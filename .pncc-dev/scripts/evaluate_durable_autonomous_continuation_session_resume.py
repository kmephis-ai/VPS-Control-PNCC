#!/usr/bin/env python3
"""PLAN_ONLY fail-closed durable PNCC continuation session resume evaluator."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
POLICY_PATH=ROOT/".pncc-dev/contracts/durable-autonomous-continuation-session-resume-policy.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
CHECKPOINT_ID=re.compile(r"^PNCC-CONTINUATION-CHECKPOINT-[A-Za-z0-9._-]+$")
FALSE_AUTH=(
"provider_mutation_authority","issue_create_authority","issue_update_authority","issue_close_authority",
"branch_mutation_authority","pull_request_mutation_authority","writer_lease_mutation_authority","workflow_rerun_authority",
"merge_authority","runtime_action_authority","product_runtime_mutation_authority","adwf_binding_mutation_authority",
"adwf_repository_mutation_authority","release_tag_promotion_authority","ruleset_policy_mutation_authority",
"private_evidence_publication_authority","force_ref_update_authority","silent_lease_steal_authority",
"reserve_1080_lifecycle_mutation_authority","primary_1081_lifecycle_mutation_authority")
CHECKPOINT_KEYS={"schema_version","role","checkpoint_state","checkpoint_id","repository","default_branch","recorded_main_sha","selected_work_unit","provider_state","execution_state","last_completed_steady_state_iteration","transaction_boundary","persisted_decisions","checkpoint_is_mutation_authority","checkpoint_cas_tokens_reusable","checkpoint_ci_success_reusable","checkpoint_admission_reusable","contains_private_runtime_payload","contains_credentials","contains_host_identifiers","contains_secret_transport_data"}
SELECTED_KEYS={"work_unit_id","issue_number","base_sha","runtime_required","provider_open"}
PROVIDER_KEYS={"state_branch_present","state_branch_head_sha","registry_blob_sha","registry_generation"}
EXECUTION_KEYS={"lease","branch","pull_request","ci"}
LEASE_KEYS={"state","lease_id","generation","branch"}
BRANCH_KEYS={"present","name","head_sha"}
PR_KEYS={"state","number","base_sha","head_sha","merge_commit_sha"}
CI_KEYS={"state","head_sha"}
PERSISTED_KEYS={"control_loop_decision","execution_admission_decision","ci_decision"}

class ResumeError(ValueError): pass

def _strict(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise ResumeError("DUPLICATE_KEY:"+k)
        out[k]=v
    return out

def load_json(path:Path)->Any:
    try:return json.loads(path.read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
    except (OSError,UnicodeError,json.JSONDecodeError) as exc: raise ResumeError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc

def blob_sha(path:Path)->str:
    b=path.read_bytes(); return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def _sha(v,name,nullable=False):
    if nullable and v is None:return None
    if not isinstance(v,str) or SHA40.fullmatch(v) is None: raise ResumeError("SHA_INVALID:"+name)
    return v

def _exact_keys(obj,keys,name):
    if not isinstance(obj,dict): raise ResumeError(name+"_OBJECT_REQUIRED")
    if set(obj)!=keys:
        missing=sorted(keys-set(obj)); extra=sorted(set(obj)-keys)
        raise ResumeError(f"{name}_KEYSET_INVALID:missing={','.join(missing)}:extra={','.join(extra)}")

def validate_policy(p):
    exact={"schema_version":1,"role":"DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME_POLICY","mode":"PLAN_ONLY_RESUME_FAIL_CLOSED","repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main","checkpoint_role":"DURABLE_AUTONOMOUS_CONTINUATION_SESSION_CHECKPOINT","snapshot_role":"DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME_SNAPSHOT","decision_role":"DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME_DECISION","drift_behavior":"DISCARD_PERSISTED_DECISIONS_AND_RECOMPUTE_FROM_FRESH_PROVIDER_TRUTH","interruption_behavior":"NO_REPLAY_RECONCILE_PROVIDER_OUTCOME_FIRST","next_boundary":"DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME_EXECUTION"}
    for k,v in exact.items():
        if p.get(k)!=v: raise ResumeError("POLICY_FIELD_INVALID:"+k)
    required=("fresh_provider_truth_required","fresh_current_main_required","fresh_selected_work_unit_required","fresh_provider_state_required","fresh_branch_pr_ci_truth_required_when_applicable","fresh_wu108_recomputation_required_before_mutation","fresh_wu109_recomputation_required_before_mutation","checkpoint_is_hint_only","checkpoint_never_grants_mutation_authority","persisted_control_loop_decision_reuse_forbidden","persisted_execution_admission_reuse_forbidden","persisted_ci_success_reuse_forbidden","persisted_registry_cas_token_reuse_forbidden","persisted_merge_eligibility_reuse_forbidden","interrupted_transaction_requires_fresh_provider_reconciliation","unknown_transaction_outcome_must_not_be_replayed","provider_truth_supersedes_checkpoint","expired_or_released_lease_reuse_forbidden","stale_branch_or_pr_head_reuse_forbidden","classified_failure_requires_separate_authority","checkpoint_public_safety_required")
    for k in required:
        if p.get(k) is not True: raise ResumeError("POLICY_REQUIRED_TRUE:"+k)
    decisions=p.get("resume_decisions")
    if not isinstance(decisions,list) or len(decisions)!=len(set(decisions)) or set(decisions)!={"RECOMPUTE_FRESH_CONTINUATION","RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH","WAIT_FOR_FRESH_PROVIDER_READBACK","SEPARATE_AUTHORITY_REQUIRED","BLOCKED"}: raise ResumeError("POLICY_DECISIONS_INVALID")
    if p.get("transaction_boundaries")!=["CLEAN_ITERATION_BOUNDARY","TRANSACTION_OUTCOME_UNKNOWN","PROVIDER_READBACK_PENDING"]: raise ResumeError("POLICY_BOUNDARIES_INVALID")
    paths,blobs=p.get("anchor_paths"),p.get("anchor_blobs")
    if not isinstance(paths,dict) or not isinstance(blobs,dict) or set(paths)!=set(blobs): raise ResumeError("POLICY_ANCHOR_MAP_INVALID")
    for k in FALSE_AUTH:
        if p.get(k) is not False: raise ResumeError("POLICY_AUTHORITY_PRESENT:"+k)

def validate_anchors(p,root=ROOT):
    for name,rel in sorted(p["anchor_paths"].items()):
        path=root/rel
        if not path.is_file(): raise ResumeError("ANCHOR_MISSING:"+name)
        if blob_sha(path)!=p["anchor_blobs"][name]: raise ResumeError("ANCHOR_DRIFT:"+name)

def _selected(obj,name="SELECTED"):
    if obj is None:return None
    _exact_keys(obj,SELECTED_KEYS,name)
    wu=obj["work_unit_id"]
    if not isinstance(wu,str) or re.fullmatch(r"PIPE-WU-[0-9]+",wu) is None: raise ResumeError(name+"_WORK_UNIT_ID_INVALID")
    if not isinstance(obj["issue_number"],int) or isinstance(obj["issue_number"],bool) or obj["issue_number"]<1: raise ResumeError(name+"_ISSUE_INVALID")
    _sha(obj["base_sha"],name+"_BASE")
    if not isinstance(obj["runtime_required"],bool) or not isinstance(obj["provider_open"],bool): raise ResumeError(name+"_BOOLEAN_INVALID")
    return obj

def _provider(obj,name="PROVIDER_STATE"):
    _exact_keys(obj,PROVIDER_KEYS,name)
    if not isinstance(obj["state_branch_present"],bool): raise ResumeError(name+"_PRESENT_INVALID")
    _sha(obj["state_branch_head_sha"],name+"_HEAD",nullable=True); _sha(obj["registry_blob_sha"],name+"_BLOB",nullable=True)
    gen=obj["registry_generation"]
    if gen is not None and (not isinstance(gen,int) or isinstance(gen,bool) or gen<0): raise ResumeError(name+"_GENERATION_INVALID")
    if obj["state_branch_present"]:
        if obj["state_branch_head_sha"] is None or obj["registry_blob_sha"] is None or gen is None: raise ResumeError(name+"_PRESENT_FIELDS_REQUIRED")
    elif any(obj[k] is not None for k in ("state_branch_head_sha","registry_blob_sha","registry_generation")): raise ResumeError(name+"_ABSENT_FIELDS_MUST_BE_NULL")
    return obj

def _execution(obj,name="EXECUTION"):
    _exact_keys(obj,EXECUTION_KEYS,name)
    lease=obj["lease"]; _exact_keys(lease,LEASE_KEYS,name+"_LEASE")
    if lease["state"] not in {"NONE","ACTIVE","RELEASED","EXPIRED","UNKNOWN"}: raise ResumeError(name+"_LEASE_STATE_INVALID")
    gen=lease["generation"]
    if gen is not None and (not isinstance(gen,int) or isinstance(gen,bool) or gen<0): raise ResumeError(name+"_LEASE_GENERATION_INVALID")
    for k in ("lease_id","branch"):
        if lease[k] is not None and (not isinstance(lease[k],str) or not lease[k]): raise ResumeError(name+"_LEASE_FIELD_INVALID:"+k)
    branch=obj["branch"]; _exact_keys(branch,BRANCH_KEYS,name+"_BRANCH")
    if not isinstance(branch["present"],bool): raise ResumeError(name+"_BRANCH_PRESENT_INVALID")
    if branch["name"] is not None and (not isinstance(branch["name"],str) or not branch["name"]): raise ResumeError(name+"_BRANCH_NAME_INVALID")
    _sha(branch["head_sha"],name+"_BRANCH_HEAD",nullable=True)
    if branch["present"] and (branch["name"] is None or branch["head_sha"] is None): raise ResumeError(name+"_BRANCH_FIELDS_REQUIRED")
    if not branch["present"] and (branch["name"] is not None or branch["head_sha"] is not None): raise ResumeError(name+"_BRANCH_ABSENT_FIELDS_INVALID")
    pr=obj["pull_request"]; _exact_keys(pr,PR_KEYS,name+"_PR")
    if pr["state"] not in {"NONE","OPEN","MERGED","CLOSED","UNKNOWN"}: raise ResumeError(name+"_PR_STATE_INVALID")
    if pr["number"] is not None and (not isinstance(pr["number"],int) or isinstance(pr["number"],bool) or pr["number"]<1): raise ResumeError(name+"_PR_NUMBER_INVALID")
    for k in ("base_sha","head_sha","merge_commit_sha"):_sha(pr[k],name+"_PR_"+k.upper(),nullable=True)
    ci=obj["ci"]; _exact_keys(ci,CI_KEYS,name+"_CI")
    if ci["state"] not in {"NONE","SUCCESS","PENDING","FAILED","AMBIGUOUS","UNKNOWN"}: raise ResumeError(name+"_CI_STATE_INVALID")
    _sha(ci["head_sha"],name+"_CI_HEAD",nullable=True)
    return obj

def validate_checkpoint(c,p):
    _exact_keys(c,CHECKPOINT_KEYS,"CHECKPOINT")
    if c["schema_version"]!=1 or c["role"]!=p["checkpoint_role"] or c["checkpoint_state"]!="PERSISTED_HINT_ONLY": raise ResumeError("CHECKPOINT_IDENTITY_INVALID")
    cid=c["checkpoint_id"]
    if not isinstance(cid,str) or not 32<=len(cid)<=160 or CHECKPOINT_ID.fullmatch(cid) is None: raise ResumeError("CHECKPOINT_ID_INVALID")
    if c["repository"]!=p["repository"] or c["default_branch"]!=p["default_branch"]: raise ResumeError("CHECKPOINT_PROVIDER_IDENTITY_INVALID")
    _sha(c["recorded_main_sha"],"CHECKPOINT_MAIN")
    _selected(c["selected_work_unit"],"CHECKPOINT_SELECTED"); _provider(c["provider_state"],"CHECKPOINT_PROVIDER_STATE"); _execution(c["execution_state"],"CHECKPOINT_EXECUTION")
    it=c["last_completed_steady_state_iteration"]
    if not isinstance(it,int) or isinstance(it,bool) or it<0: raise ResumeError("CHECKPOINT_ITERATION_INVALID")
    if c["transaction_boundary"] not in p["transaction_boundaries"]: raise ResumeError("CHECKPOINT_BOUNDARY_INVALID")
    _exact_keys(c["persisted_decisions"],PERSISTED_KEYS,"CHECKPOINT_PERSISTED_DECISIONS")
    for k,v in c["persisted_decisions"].items():
        if v is not None and (not isinstance(v,str) or not v or len(v)>128): raise ResumeError("CHECKPOINT_PERSISTED_DECISION_INVALID:"+k)
    for k in ("checkpoint_is_mutation_authority","checkpoint_cas_tokens_reusable","checkpoint_ci_success_reusable","checkpoint_admission_reusable","contains_private_runtime_payload","contains_credentials","contains_host_identifiers","contains_secret_transport_data"):
        if c[k] is not False: raise ResumeError("CHECKPOINT_FORBIDDEN_FLAG:"+k)

def _out(decision,p,*,reasons=None,drift=None,checkpoint=None):
    persisted=[]
    if isinstance(checkpoint,dict) and isinstance(checkpoint.get("persisted_decisions"),dict):
        persisted=sorted(k for k,v in checkpoint["persisted_decisions"].items() if v is not None)
    return {"schema_version":1,"role":p["decision_role"],"state":"RESUME_BLOCKED" if decision=="BLOCKED" else "RESUME_PLAN_ONLY_PASS","decision":decision,"reasons":reasons or [],"checkpoint_drift_fields":drift or [],"discarded_persisted_decisions":persisted,"fresh_wu108_recomputation_required":decision!="BLOCKED","fresh_wu109_recomputation_required_before_mutation":decision!="BLOCKED","provider_reconciliation_required":decision in {"RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH","WAIT_FOR_FRESH_PROVIDER_READBACK"},"checkpoint_authority_used":False,"persisted_admission_reused":False,"persisted_ci_reused":False,"persisted_cas_reused":False,"provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,"pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,"merge_performed":False,"runtime_action_performed":False,"product_runtime_mutation_performed":False,"next_boundary":p["next_boundary"]}

def _drift(checkpoint,current_main,selected,provider_state,execution):
    d=[]
    if checkpoint["recorded_main_sha"]!=current_main:d.append("current_main")
    if checkpoint["selected_work_unit"]!=selected:d.append("selected_work_unit")
    if checkpoint["provider_state"]!=provider_state:d.append("provider_state")
    cle=checkpoint["execution_state"]
    if cle["lease"]!=execution["lease"]:d.append("writer_lease")
    if cle["branch"]!=execution["branch"]:d.append("branch")
    if cle["pull_request"]!=execution["pull_request"]:d.append("pull_request")
    if cle["ci"]!=execution["ci"]:d.append("ci")
    return d

def evaluate(snapshot,*,policy=None,root=ROOT,check_anchors=True):
    p=policy or load_json(POLICY_PATH); checkpoint=None
    try:
        validate_policy(p)
        if check_anchors:validate_anchors(p,root=root)
        if not isinstance(snapshot,dict) or snapshot.get("schema_version")!=1 or snapshot.get("role")!=p["snapshot_role"]: raise ResumeError("SNAPSHOT_IDENTITY_INVALID")
        if snapshot.get("repository")!=p["repository"] or snapshot.get("default_branch")!=p["default_branch"]: raise ResumeError("SNAPSHOT_PROVIDER_IDENTITY_INVALID")
        if snapshot.get("provider_truth_fresh") is not True: raise ResumeError("PROVIDER_TRUTH_NOT_FRESH")
        if snapshot.get("contradictory_provider_truth") is not False: raise ResumeError("CONTRADICTORY_PROVIDER_TRUTH")
        current=_sha(snapshot.get("current_main_sha"),"CURRENT_MAIN")
        selected=_selected(snapshot.get("selected_work_unit"),"FRESH_SELECTED")
        provider=_provider(snapshot.get("provider_state"),"FRESH_PROVIDER_STATE")
        execution=_execution(snapshot.get("execution_state"),"FRESH_EXECUTION")
        if snapshot.get("classified_failure_detected") is True:
            return _out("SEPARATE_AUTHORITY_REQUIRED",p,reasons=["CLASSIFIED_FAILURE_REQUIRES_SEPARATE_AUTHORITY"])
        if snapshot.get("classified_failure_detected") is not False: raise ResumeError("CLASSIFIED_FAILURE_FLAG_INVALID")
        checkpoint=snapshot.get("checkpoint")
        if checkpoint is None:
            return _out("RECOMPUTE_FRESH_CONTINUATION",p,reasons=["NO_CHECKPOINT_FRESH_PROVIDER_TRUTH_IS_AUTHORITY"])
        if not isinstance(checkpoint,dict): raise ResumeError("CHECKPOINT_OBJECT_OR_NULL_REQUIRED")
        validate_checkpoint(checkpoint,p)
        boundary=checkpoint["transaction_boundary"]
        readback=snapshot.get("fresh_provider_readback_completed")
        if not isinstance(readback,bool): raise ResumeError("FRESH_PROVIDER_READBACK_FLAG_REQUIRED")
        drift=_drift(checkpoint,current,selected,provider,execution)
        if boundary in {"TRANSACTION_OUTCOME_UNKNOWN","PROVIDER_READBACK_PENDING"}:
            if not readback:
                return _out("WAIT_FOR_FRESH_PROVIDER_READBACK",p,reasons=["INTERRUPTED_TRANSACTION_OUTCOME_MUST_NOT_BE_ASSUMED"],drift=drift,checkpoint=checkpoint)
            return _out("RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH",p,reasons=["FRESH_PROVIDER_READBACK_SUPERSEDES_INTERRUPTED_CHECKPOINT"],drift=drift,checkpoint=checkpoint)
        if boundary!="CLEAN_ITERATION_BOUNDARY": raise ResumeError("CHECKPOINT_BOUNDARY_UNHANDLED")
        reasons=["CLEAN_BOUNDARY_RECOMPUTE_FRESH_WU108_WU109"]
        if drift: reasons.append("CHECKPOINT_STALE_PROVIDER_TRUTH_SUPERSEDES_CHECKPOINT")
        lease_state=execution["lease"]["state"]
        if lease_state in {"RELEASED","EXPIRED","UNKNOWN"}: reasons.append("PERSISTED_LEASE_NOT_REUSABLE")
        if execution["ci"]["state"]=="SUCCESS": reasons.append("PERSISTED_CI_SUCCESS_NOT_REUSABLE_REINSPECT_EXACT_HEAD")
        return _out("RECOMPUTE_FRESH_CONTINUATION",p,reasons=reasons,drift=drift,checkpoint=checkpoint)
    except (ResumeError,KeyError,TypeError) as exc:
        try:validate_policy(p)
        except Exception:pass
        return _out("BLOCKED",p,reasons=[str(exc)],checkpoint=checkpoint)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--policy",default=str(POLICY_PATH)); a=ap.parse_args()
    p=load_json(Path(a.policy)); result=evaluate(load_json(Path(a.input)),policy=p)
    print(json.dumps(result,indent=2,sort_keys=True)); return 2 if result["decision"]=="BLOCKED" else 0
if __name__=="__main__": raise SystemExit(main())
