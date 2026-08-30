#!/usr/bin/env python3
"""Validate and replay PIPE-WU-114 two-iteration steady-state execution evidence."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, sys
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE_PATH=ROOT/".pncc-dev/contracts/reusable-autonomous-continuation-steady-state-execution-wu114.json"
STEADY_PATH=ROOT/".pncc-dev/scripts/evaluate_reusable_autonomous_continuation_steady_state.py"
STEADY_POLICY=ROOT/".pncc-dev/contracts/reusable-autonomous-continuation-steady-state-policy.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
EXACT={
 "work_unit_id":"PIPE-WU-114","issue_number":275,"base_main_sha":"add2818df8551d7f95beee2487f5b0bee57d204a",
 "frontier_id":"REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_EXECUTION",
 "predecessor_frontier_blob_sha":"1cea35626f69047db79855a09e878d38e314e1a8",
 "branch":"agent/PIPE-WU-114-reusable-autonomous-continuation-steady-state-execution",
 "steady_state_policy_blob_sha":"6957f09565a66e7b7f7206a640157aac4491bfa8",
 "steady_state_evaluator_blob_sha":"66af19669dbd7efff1aa3709d263c590fcec5108",
 "executor_grant_blob_sha":"2c62780720dace54b220cedd42f77f834886e62a",
 "owner_authorization_receipt_blob_sha":"143723fee62a2955817e95e4cca48794769a0b46",
 "first_transaction_evidence_blob_sha":"647e04524f6095fb23996386627dab92a6d5ec9d",
 "control_loop_policy_blob_sha":"822bcd1833ff4843b6bd176337b3ef3b742275de",
 "control_loop_evaluator_blob_sha":"1f794892cfec466505a1a6c38b271492f9759127",
 "execution_admission_policy_blob_sha":"406d78da6250c452bfc7706b57dc51a18ca48977",
 "execution_admission_evaluator_blob_sha":"cde13515632717b81cef77876e53e9ceef0c46bf",
 "delegated_authority_grant_blob_sha":"717e1f9081915f40fad2e0620c64245a650ca235",
 "next_boundary":"DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME"}
ANCHORS={
 "steady_state_policy":(".pncc-dev/contracts/reusable-autonomous-continuation-steady-state-policy.json","6957f09565a66e7b7f7206a640157aac4491bfa8"),
 "steady_state_evaluator":(".pncc-dev/scripts/evaluate_reusable_autonomous_continuation_steady_state.py","66af19669dbd7efff1aa3709d263c590fcec5108"),
 "executor_grant":(".pncc-dev/contracts/reusable-autonomous-continuation-executor-authorized.json","2c62780720dace54b220cedd42f77f834886e62a"),
 "owner_receipt":(".pncc-dev/attestations/reusable-autonomous-continuation-executor-owner-authorization-wu111.json","143723fee62a2955817e95e4cca48794769a0b46"),
 "first_transaction":(".pncc-dev/contracts/reusable-autonomous-continuation-executor-first-transaction-wu112.json","647e04524f6095fb23996386627dab92a6d5ec9d"),
 "control_policy":(".pncc-dev/contracts/autonomous-continuation-control-loop-policy.json","822bcd1833ff4843b6bd176337b3ef3b742275de"),
 "control_evaluator":(".pncc-dev/scripts/evaluate_autonomous_continuation_control_loop.py","1f794892cfec466505a1a6c38b271492f9759127"),
 "admission_policy":(".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json","406d78da6250c452bfc7706b57dc51a18ca48977"),
 "admission_evaluator":(".pncc-dev/scripts/evaluate_autonomous_continuation_execution_admission.py","cde13515632717b81cef77876e53e9ceef0c46bf"),
 "writer_grant":(".pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json","717e1f9081915f40fad2e0620c64245a650ca235")}
FORBIDDEN_TRUE=("stale_control_loop_or_admission_reuse_performed","batch_provider_mutation_performed","inferred_or_fallback_authority_used","product_runtime_mutation_performed","runtime_action_performed","adwf_binding_or_repository_mutation_performed","release_tag_promotion_performed","ruleset_policy_mutation_performed","private_evidence_publication_performed","reserve_1080_lifecycle_mutation_performed","primary_1081_lifecycle_mutation_performed","authority_broadening_performed")

class ValidationError(ValueError): pass

def load(path:Path)->Any:
    try:return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e: raise ValidationError(f"INVALID_JSON:{type(e).__name__}") from e

def blob(path:Path)->str:
    b=path.read_bytes(); return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def req(obj,key,val=True):
    if obj.get(key) is not val: raise ValidationError("REQUIRED_FLAG:"+key)

def sha(v,key):
    if not isinstance(v,str) or SHA40.fullmatch(v) is None: raise ValidationError("SHA_INVALID:"+key)
    return v

def load_steady():
    spec=importlib.util.spec_from_file_location("pncc_steady",STEADY_PATH)
    if spec is None or spec.loader is None: raise ValidationError("STEADY_IMPORT_FAILED")
    mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod); return mod

def decision_objects(it):
    control={"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION","state":"PLAN_ONLY_CONTROL_LOOP_PASS","decision":it["control_loop_decision"],"delegated_authority":it["delegated_authority_identity"],"provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,"pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,"merge_performed":False,"runtime_action_performed":False,"product_runtime_mutation_performed":False}
    admission={"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_DECISION","state":"PLAN_ONLY_ADMISSION_PASS","decision":it["execution_admission_decision"],"control_loop_decision":it["control_loop_decision"],"delegated_authority":it["delegated_authority_identity"],"target_action":it["target_action"],"provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,"pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,"merge_performed":False,"runtime_action_performed":False}
    return control,admission

def replay(mod,policy,it,completed):
    control,admission=decision_objects(it)
    txn={"state":"PERFORMED_READBACK_COMPLETE" if completed else "NOT_STARTED","delegated_transaction_count":1 if completed else 0,"delegated_authority_identity":it["delegated_authority_identity"],"target_action":it["target_action"],"provider_mutation_performed":completed,"fresh_provider_readback_completed":completed,"provider_state_after":{"fresh":True,"identity":f"wu114-iteration-{it['iteration_sequence']}-readback"} if completed else None}
    snap={"schema_version":1,"role":"REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_SNAPSHOT","repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main","provider_truth_fresh":it["provider_truth_fresh"],"current_main_sha":EXACT["base_main_sha"],"iteration_sequence":it["iteration_sequence"],"control_loop_fresh_for_iteration":it["control_loop_fresh_for_iteration"],"execution_admission_fresh_for_iteration":it["execution_admission_fresh_for_iteration"],"control_loop_reused_from_prior_iteration":it["control_loop_reused_from_prior_iteration"],"execution_admission_reused_from_prior_iteration":it["execution_admission_reused_from_prior_iteration"],"previous_iteration_fresh_provider_readback_completed":it["previous_iteration_fresh_provider_readback_completed"],"interrupted":False,"stale_state":False,"contradiction_detected":False,"anchor_drift_detected":False,"revocation_detected":False,"classified_failure_detected":False,"control_loop_decision":control,"execution_admission_decision":admission,"delegated_transaction":txn}
    return mod.evaluate(snap,policy=policy,check_anchors=False)

def validate(e,*,check_anchors=True):
    if e.get("schema_version")!=1 or e.get("role")!="REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_EXECUTION_EVIDENCE" or e.get("evidence_state")!="RECORDED": raise ValidationError("EVIDENCE_IDENTITY_INVALID")
    for k,v in EXACT.items():
        if e.get(k)!=v: raise ValidationError("EXACT_FIELD_MISMATCH:"+k)
    if e.get("required_iteration_count")!=2 or e.get("completed_iteration_count")!=2 or e.get("maximum_delegated_transactions_per_iteration")!=1: raise ValidationError("ITERATION_CONTRACT_INVALID")
    for k in ("cross_iteration_provider_state_chain_exact","fresh_control_loop_and_admission_per_iteration","main_unchanged_after_iterations"): req(e,k)
    for k in FORBIDDEN_TRUE:
        if e.get(k) is not False: raise ValidationError("FORBIDDEN_FLAG_TRUE:"+k)
    if e.get("main_sha_after_iterations")!=EXACT["base_main_sha"]: raise ValidationError("MAIN_DRIFT")
    selected=e.get("selected_work_unit")
    if not isinstance(selected,dict) or selected!={"work_unit_id":"PIPE-WU-114","issue_number":275,"marker_state":"READY","conflict_domain":"wave5-reusable-autonomous-continuation-steady-state-execution","runtime_required":False,"base_sha":EXACT["base_main_sha"]}: raise ValidationError("SELECTED_WORK_UNIT_INVALID")
    if check_anchors:
        for name,(rel,expected) in ANCHORS.items():
            p=ROOT/rel
            if not p.is_file() or blob(p)!=expected: raise ValidationError("ANCHOR_DRIFT:"+name)
    its=e.get("iterations")
    if not isinstance(its,list) or len(its)!=2 or [x.get("iteration_sequence") for x in its]!=[1,2]: raise ValidationError("ITERATION_SEQUENCE_INVALID")
    expected=[("PLAN_EXISTING_WRITER_LEASE_ACQUISITION","WRITER_LEASE_ACQUIRE_FRESH_CAS_PATH","WRITER_LEASE_ACQUISITION"),("PLAN_EXISTING_BOUNDED_BRANCH_CREATE","BOUNDED_NON_MAIN_BRANCH_CREATE_PATH","BOUNDED_BRANCH_CREATE")]
    for idx,(it,exp) in enumerate(zip(its,expected),1):
        for k in ("provider_truth_fresh","control_loop_fresh_for_iteration","execution_admission_fresh_for_iteration","fresh_provider_readback_completed","readback_matches_expected_transaction"): req(it,k)
        if it.get("control_loop_reused_from_prior_iteration") is not False or it.get("execution_admission_reused_from_prior_iteration") is not False: raise ValidationError("STALE_ADMISSION_REUSE")
        if it.get("previous_iteration_fresh_provider_readback_completed") is not (idx>1): raise ValidationError("PREVIOUS_READBACK_BINDING_INVALID")
        if (it.get("control_loop_decision"),it.get("target_action"),it.get("transaction_kind"))!=exp: raise ValidationError("ITERATION_DECISION_INVALID")
        if it.get("execution_admission_decision")!="ADMIT_EXISTING_WRITER_LEASE_AUTHORITY" or it.get("delegated_authority_identity")!="EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY" or it.get("delegated_transaction_count")!=1: raise ValidationError("DELEGATED_TRANSACTION_INVALID")
        if it.get("transaction_result",{}).get("provider_mutation_performed") is not True: raise ValidationError("MUTATION_EVIDENCE_REQUIRED")
    i1,i2=its
    if i1["provider_state_after"]!=i2["provider_state_before"]: raise ValidationError("CROSS_ITERATION_PROVIDER_CHAIN_MISMATCH")
    if i1["provider_state_before"]!={"state_branch_head_sha":"91f2250b630d1c394a509e0bb97b41a49b46e4fa","registry_blob_sha":"1fb1a26dc6b1e4b89daefbcbd91b6144d37c9d5d","registry_generation":21,"exact_work_unit_lease_present":False}: raise ValidationError("ITERATION1_PROVIDER_BEFORE_INVALID")
    tr1=i1["transaction_result"]
    if tr1.get("provider_state_commit_sha")!="f766134d7630ce980e40df9932cb7e301e00838b" or tr1.get("lease_id")!="153462e4-59bb-44ae-9864-f6e35a57ba2d" or tr1.get("generation")!=22 or tr1.get("state")!="ACTIVE": raise ValidationError("LEASE_RESULT_INVALID")
    after1={"state_branch_head_sha":"f766134d7630ce980e40df9932cb7e301e00838b","registry_blob_sha":"0f4feb90a9eaa1c0598229d892d24d44a899eb48","registry_generation":22,"exact_work_unit_lease_present":True,"exact_work_unit_lease_state":"ACTIVE"}
    if i1["provider_state_after"]!=after1 or i2["provider_state_after"]!=after1: raise ValidationError("PROVIDER_READBACK_INVALID")
    if i2.get("branch_state_before")!={"branch_present":False}: raise ValidationError("BRANCH_PRESTATE_INVALID")
    tr2=i2["transaction_result"]; bs=i2["branch_state_after"]
    if tr2.get("branch_created") is not True or tr2.get("branch")!=EXACT["branch"] or tr2.get("branch_head_sha")!=EXACT["base_main_sha"] or tr2.get("branch_base_sha")!=EXACT["base_main_sha"]: raise ValidationError("BRANCH_TRANSACTION_INVALID")
    if bs!={"branch_present":True,"branch_head_sha":EXACT["base_main_sha"],"compare_status":"identical","ahead_by":0,"behind_by":0}: raise ValidationError("BRANCH_READBACK_INVALID")
    mod=load_steady(); policy=load(STEADY_POLICY)
    for it in its:
        pre=replay(mod,policy,it,False); post=replay(mod,policy,it,True)
        if pre.get("decision")!="EXECUTE_ONE_DELEGATED_TRANSACTION": raise ValidationError("STEADY_PRE_REPLAY_FAILED")
        if post.get("decision")!="ITERATION_COMPLETE_NEXT_FRESH_ITERATION_ALLOWED": raise ValidationError("STEADY_POST_REPLAY_FAILED")
    return {"schema_version":1,"role":"WU114_STEADY_STATE_EXECUTION_VALIDATION","state":"PASS","work_unit_id":"PIPE-WU-114","iterations_validated":2,"next_boundary":EXACT["next_boundary"]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--evidence",default=str(EVIDENCE_PATH)); a=ap.parse_args()
    try:r=validate(load(Path(a.evidence)))
    except ValidationError as exc:r={"schema_version":1,"role":"WU114_STEADY_STATE_EXECUTION_VALIDATION","state":"BLOCKED","reasons":[str(exc)]}
    print(json.dumps(r,indent=2,sort_keys=True)); return 0 if r["state"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
