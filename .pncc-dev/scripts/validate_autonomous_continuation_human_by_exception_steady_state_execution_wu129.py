#!/usr/bin/env python3
"""Fail-closed validation for PIPE-WU-129 Human-by-Exception steady-state execution evidence."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE_PATH=ROOT/".pncc-dev/contracts/autonomous-continuation-human-by-exception-steady-state-execution-wu129.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
BASE="aa4447b854450e3a85b831335d80b8c4ad24ac72"
BRANCH="agent/PIPE-WU-129-human-by-exception-steady-state-execution-existing-authority-only"
CONFLICT="wave5-autonomous-continuation-human-by-exception-steady-state-execution-existing-authority-only"
PRED="320f76f278bd7464e8a755e0a2982236e5e25c00"
PROV36="1eaba6fdbb2920ce3780c931205913066cb916fa"
REG36="a6e953d5b9adcddd42d4fcb45c75c2cd18179169"
PROV37="5be784544b629d2f3ebf7c3e63908b48c13f97a1"
REG37="ece52ff7cbea26f7fd435dc791d5daba8331b878"
LEASE37="b109e670-49f0-4ce2-9af6-27c6a01407e7"
PROV38="064e0afd973f44ceea0a5a0989a4a7a1dab01d0c"
REG38="8f67e99217417a5a8e225bbe4a936a43961f3262"
LEASE38="5f7f97d5-7fab-44c4-8dbb-375043a866b3"
NEXT="AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_SESSION_RESUME_WITH_EXISTING_AUTHORITY_ONLY"

class ValidationError(ValueError): pass

def _strict(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise ValidationError("DUPLICATE_KEY:"+k)
        out[k]=v
    return out

def load(path:Path)->Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise ValidationError("INVALID_JSON:"+type(exc).__name__) from exc

def blob(path:Path)->str:
    data=path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def flag(obj:dict[str,Any], key:str, expected:bool=True)->None:
    if obj.get(key) is not expected: raise ValidationError("FLAG_INVALID:"+key)

def exact_sha(value:Any,key:str)->str:
    if not isinstance(value,str) or SHA40.fullmatch(value) is None: raise ValidationError("SHA_INVALID:"+key)
    return value

def validate(e:Any,*,check_anchors:bool=True,root:Path=ROOT)->dict[str,Any]:
    if not isinstance(e,dict) or e.get("schema_version")!=1 or e.get("role")!="AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_EXECUTION_EVIDENCE" or e.get("evidence_state")!="RECORDED":
        raise ValidationError("EVIDENCE_IDENTITY_INVALID")
    expected={
        "work_unit_id":"PIPE-WU-129","issue_number":306,"base_main_sha":BASE,"branch":BRANCH,
        "conflict_domain":CONFLICT,"runtime_required":False,
        "frontier_id":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_EXECUTION_WITH_EXISTING_AUTHORITY_ONLY",
        "predecessor_frontier_blob_sha":PRED,"required_iteration_count":2,"completed_iteration_count":2,
        "maximum_delegated_transactions_per_iteration":1,"next_boundary":NEXT,
    }
    for k,v in expected.items():
        if e.get(k)!=v: raise ValidationError("EXACT_FIELD_MISMATCH:"+k)
    selected=e.get("selected_work_unit")
    if selected!={"work_unit_id":"PIPE-WU-129","issue_number":306,"marker_state":"READY","conflict_domain":CONFLICT,"runtime_required":False,"base_sha":BASE}:
        raise ValidationError("SELECTED_WORK_UNIT_INVALID")
    for key in ("cross_iteration_provider_state_chain_exact","fresh_inputs_per_iteration"):
        flag(e,key)
    for key in (
        "stale_decision_reuse_performed","batch_mutation_performed","inferred_or_fallback_authority_used",
        "owner_exception_mutation_performed","wait_only_mutation_performed","stop_only_mutation_performed",
        "separate_authority_mutation_performed","blocked_outcome_mutation_performed",
        "product_runtime_mutation_performed","runtime_action_performed","adwf_binding_or_repository_mutation_performed",
        "release_tag_promotion_performed","ruleset_policy_mutation_performed","private_evidence_publication_performed",
        "reserve_1080_lifecycle_mutation_performed","primary_1081_lifecycle_mutation_performed",
        "authority_broadening_performed","authority_granted","higher_autonomy_authorized",
    ):
        flag(e,key,False)
    anchors=e.get("anchors")
    if not isinstance(anchors,dict) or not anchors: raise ValidationError("ANCHOR_MAP_INVALID")
    for name,spec in anchors.items():
        if not isinstance(spec,dict) or set(spec)!={"path","blob_sha"}: raise ValidationError("ANCHOR_SPEC_INVALID:"+name)
        exact_sha(spec["blob_sha"],"anchor:"+name)
        if check_anchors:
            p=root/spec["path"]
            if not p.is_file() or blob(p)!=spec["blob_sha"]: raise ValidationError("ANCHOR_DRIFT:"+name)

    its=e.get("iterations")
    if not isinstance(its,list) or len(its)!=2 or [x.get("iteration_sequence") for x in its]!=[1,2]:
        raise ValidationError("ITERATION_SEQUENCE_INVALID")
    for idx,it in enumerate(its,1):
        for key in ("provider_truth_fresh","control_loop_fresh_for_iteration","execution_admission_fresh_for_iteration","operationalization_fresh_for_iteration","fresh_provider_readback_completed","readback_matches_expected_transaction"):
            flag(it,key)
        for key in ("control_loop_reused_from_prior_iteration","execution_admission_reused_from_prior_iteration","operationalization_reused_from_prior_iteration"):
            flag(it,key,False)
        if it.get("previous_iteration_fresh_provider_readback_completed") is not (idx==2):
            raise ValidationError("PREVIOUS_READBACK_BINDING_INVALID")
        if it.get("execution_admission_decision")!="ADMIT_EXISTING_WRITER_LEASE_AUTHORITY":
            raise ValidationError("ADMISSION_INVALID")
        if it.get("operationalization_outcome")!="CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY":
            raise ValidationError("OPERATIONALIZATION_INVALID")
        if it.get("delegated_authority_identity")!="EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY":
            raise ValidationError("DELEGATED_AUTHORITY_INVALID")
        if it.get("delegated_transaction_count")!=1:
            raise ValidationError("TRANSACTION_COUNT_INVALID")

    i1,i2=its
    if (i1.get("control_loop_decision"),i1.get("target_action"),i1.get("transaction_kind"))!=("PLAN_EXISTING_WRITER_LEASE_ACQUISITION","WRITER_LEASE_ACQUIRE_FRESH_CAS_PATH","WRITER_LEASE_ACQUISITION"):
        raise ValidationError("ITERATION1_PLAN_INVALID")
    before1={"state_branch_head_sha":PROV36,"registry_blob_sha":REG36,"registry_generation":36,"unexpired_active_in_conflict_domain":0}
    if i1.get("provider_state_before")!=before1: raise ValidationError("ITERATION1_PROVIDER_BEFORE_INVALID")
    tr1=i1.get("transaction_result")
    if not isinstance(tr1,dict): raise ValidationError("ITERATION1_RESULT_REQUIRED")
    required_tr1={
        "provider_mutation_performed":True,"provider_state_commit_sha":PROV37,"registry_blob_sha":REG37,
        "registry_generation":37,"lease_id":LEASE37,"lease_state":"ACTIVE","lease_generation":37,
        "acquired_at":"2026-08-30T20:59:30Z","heartbeat_at":"2026-08-30T20:59:30Z","expires_at":"2026-08-30T21:59:30Z",
        "base_sha":BASE,"branch":BRANCH,
    }
    if tr1!=required_tr1: raise ValidationError("ITERATION1_RESULT_INVALID")
    after1={"state_branch_head_sha":PROV37,"registry_blob_sha":REG37,"registry_generation":37,"exact_work_unit_lease_id":LEASE37,"exact_work_unit_lease_state":"ACTIVE"}
    if i1.get("provider_state_after")!=after1: raise ValidationError("ITERATION1_READBACK_INVALID")

    if (i2.get("control_loop_decision"),i2.get("target_action"),i2.get("transaction_kind"))!=("PLAN_EXISTING_BOUNDED_BRANCH_CREATE","BOUNDED_NON_MAIN_BRANCH_CREATE_PATH","BOUNDED_BRANCH_CREATE"):
        raise ValidationError("ITERATION2_PLAN_INVALID")
    if i2.get("provider_state_before")!=after1 or i2.get("provider_state_after")!=after1:
        raise ValidationError("CROSS_ITERATION_PROVIDER_CHAIN_MISMATCH")
    if i2.get("branch_state_before")!={"branch_present":False}: raise ValidationError("BRANCH_PRESTATE_INVALID")
    tr2=i2.get("transaction_result")
    if tr2!={"provider_mutation_performed":False,"branch_created":True,"branch":BRANCH,"branch_base_sha":BASE,"branch_head_sha":BASE,"force":False}:
        raise ValidationError("ITERATION2_RESULT_INVALID")
    if i2.get("branch_state_after")!={"branch_present":True,"branch_head_sha":BASE,"compare_status":"identical","ahead_by":0,"behind_by":0}:
        raise ValidationError("BRANCH_READBACK_INVALID")
    if i2.get("fresh_branch_readback_completed") is not True or i2.get("fresh_main_readback_completed") is not True or i2.get("main_sha_after")!=BASE:
        raise ValidationError("ITERATION2_READBACK_INVALID")

    recovery=e.get("session_interruption_recovery")
    if not isinstance(recovery,dict): raise ValidationError("RECOVERY_REQUIRED")
    flag(recovery,"required_two_iterations_completed_before_interruption")
    flag(recovery,"recovery_counted_as_required_iteration",False)
    flag(recovery,"append_only_generation_advance")
    flag(recovery,"historical_expired_active_plus_one_unexpired_active_topology_permitted")
    old=recovery.get("original_lease")
    if old!={"lease_id":LEASE37,"generation":37,"recorded_state_preserved":"ACTIVE","expires_at":"2026-08-30T21:59:30Z","expired_before_recovery":True,"historical_entry_mutated":False,"historical_entry_reactivated":False,"historical_entry_reused":False,"expired_lease_release_attempted":False,"historical_reconciliation_authority_used":False}:
        raise ValidationError("HISTORICAL_LEASE_RECOVERY_INVALID")
    fresh=recovery.get("fresh_claim")
    if not isinstance(fresh,dict): raise ValidationError("FRESH_CLAIM_REQUIRED")
    expected_fresh={
        "fresh_provider_read_before_claim":True,"provider_state_before":PROV37,"registry_blob_before":REG37,"registry_generation_before":37,
        "unexpired_active_in_conflict_domain_before":0,"provider_state_after":PROV38,"registry_blob_after":REG38,"registry_generation_after":38,
        "lease_id":LEASE38,"lease_state":"ACTIVE","lease_generation":38,"acquired_at":"2026-08-31T03:30:37Z",
        "heartbeat_at":"2026-08-31T03:30:37Z","expires_at":"2026-08-31T04:30:37Z","base_sha":BASE,"branch":BRANCH,
        "silent_lease_steal_performed":False,"force_ref_update_performed":False,
    }
    if fresh!=expected_fresh: raise ValidationError("FRESH_CLAIM_INVALID")
    if fresh["registry_generation_after"]!=old["generation"]+1: raise ValidationError("GENERATION_NOT_MONOTONIC")
    return {"schema_version":1,"role":"WU129_HUMAN_BY_EXCEPTION_STEADY_STATE_EXECUTION_VALIDATION","state":"PASS","work_unit_id":"PIPE-WU-129","iterations_validated":2,"recovery_generation":38,"next_boundary":NEXT}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--evidence",default=str(EVIDENCE_PATH)); args=ap.parse_args()
    try:
        result=validate(load(Path(args.evidence)))
    except ValidationError as exc:
        result={"schema_version":1,"role":"WU129_HUMAN_BY_EXCEPTION_STEADY_STATE_EXECUTION_VALIDATION","state":"BLOCKED","reasons":[str(exc)]}
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["state"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
