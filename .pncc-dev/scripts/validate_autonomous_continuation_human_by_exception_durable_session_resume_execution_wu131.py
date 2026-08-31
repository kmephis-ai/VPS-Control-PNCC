#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-durable-session-resume-execution-wu131.json"
HBE_POLICY_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-durable-session-resume-policy-wu130.json"
HBE_EVALUATOR_PATH = ROOT / ".pncc-dev/scripts/evaluate_autonomous_continuation_human_by_exception_durable_session_resume.py"

EXPECTED = {
    "definition_policy": "c2691ffade539f09bf6e70012e4baa7b1ee034b2",
    "definition_evaluator": "01a62d4d60ed915d8e1993027be1ac075b40fae0",
    "generic_execution_pattern": "e9c104d24f0b27c496857d162903d9d610c7e39d",
    "control_policy": "822bcd1833ff4843b6bd176337b3ef3b742275de",
    "admission_policy": "406d78da6250c452bfc7706b57dc51a18ca48977",
    "writer_grant": "717e1f9081915f40fad2e0620c64245a650ca235",
    "claim_policy": "bf83539899df5c5a4e660734e861653f1d4cc1ee",
    "topology_validator": "aad1f221e28cd413408c676eb9ea9da48c4130f0",
}
ANCHORS = {
    "definition_policy": HBE_POLICY_PATH,
    "definition_evaluator": HBE_EVALUATOR_PATH,
    "generic_execution_pattern": ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-session-resume-execution-wu116.json",
    "control_policy": ROOT / ".pncc-dev/contracts/autonomous-continuation-control-loop-policy.json",
    "admission_policy": ROOT / ".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json",
    "writer_grant": ROOT / ".pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json",
    "claim_policy": ROOT / ".pncc-dev/contracts/writer-lease-claim-admission-policy.json",
    "topology_validator": ROOT / ".pncc-dev/scripts/validate_writer_lease_registry_topology.py",
}
BASE = "05534a95f322ca2c3dbc5afef1fb4c3b0583014f"
BRANCH = "agent/PIPE-WU-131-human-by-exception-durable-session-resume-execution-existing-authority-only"
CONFLICT = "wave5-autonomous-continuation-human-by-exception-durable-session-resume-execution-existing-authority-only"
LEASE_ID = "9aa39cfb-92f5-475a-80c1-4fd3b6771d46"
PROVIDER_BEFORE = "bf10263258555ad719a3375f1a18db47439e0f60"
REG_BEFORE = "743552536112b05c4d7d5b85157fb1c868bd81e4"
PROVIDER_AFTER = "d83a845ce79bc033dbc5f77d40321740da35c658"
REG_AFTER = "18d6ab6cf50d510aae2b7570dca502ba5a024b4c"

class ValidationError(ValueError):
    pass

def _strict(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise ValidationError("DUPLICATE_KEY:"+k)
        out[k]=v
    return out

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("INVALID_JSON:"+path.as_posix()+":"+type(exc).__name__) from exc

def blob_sha(path: Path) -> str:
    data=path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def load_module(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise ValidationError("MODULE_LOAD_FAILED:"+name)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod
    spec.loader.exec_module(mod)
    return mod

def req_true(v,name):
    if v is not True:
        raise ValidationError("REQUIRED_TRUE:"+name)

def req_false(v,name):
    if v is not False:
        raise ValidationError("REQUIRED_FALSE:"+name)

def validate_anchors(e):
    for k,p in ANCHORS.items():
        if not p.is_file():
            raise ValidationError("ANCHOR_MISSING:"+k)
        actual=blob_sha(p)
        if actual != EXPECTED[k]:
            raise ValidationError(f"ANCHOR_DRIFT:{k}:{actual}")
    fields={
      "definition_policy_blob_sha":EXPECTED["definition_policy"],
      "definition_evaluator_blob_sha":EXPECTED["definition_evaluator"],
      "generic_resume_execution_pattern_blob_sha":EXPECTED["generic_execution_pattern"],
      "control_loop_policy_blob_sha":EXPECTED["control_policy"],
      "execution_admission_policy_blob_sha":EXPECTED["admission_policy"],
      "delegated_authority_grant_blob_sha":EXPECTED["writer_grant"],
      "writer_lease_claim_policy_blob_sha":EXPECTED["claim_policy"],
      "writer_lease_topology_validator_blob_sha":EXPECTED["topology_validator"],
    }
    for k,v in fields.items():
        if e.get(k)!=v:
            raise ValidationError("EVIDENCE_ANCHOR_MISMATCH:"+k)

def make_checkpoint(*, lease_state="ACTIVE", expired=False, boundary="CLEAN_ITERATION_BOUNDARY",
                    hbe="CONTINUE", completed=None, next_fp=None, generation=40, conflicts=1):
    lease = {
      "lease_id": LEASE_ID if generation==40 else "7435a7f5-9dcb-4c87-a803-62e0561f6153",
      "work_unit_id":"PIPE-WU-131",
      "conflict_domain":CONFLICT,
      "holder":"chatgpt-wave5-writer",
      "base_sha":BASE,
      "branch":BRANCH,
      "state":lease_state,
      "generation":generation,
      "expired":expired,
    }
    return {
      "schema_version":1,
      "role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_SESSION_CHECKPOINT",
      "provider_truth_fresh":True,
      "main_fresh":True,
      "selection_fresh":True,
      "branch_readback_fresh":True,
      "pr_ci_readback_fresh_when_applicable":True,
      "current_main_sha":BASE,
      "selected_work_unit":{
        "work_unit_id":"PIPE-WU-131","issue_number":310,"marker_state":"READY",
        "conflict_domain":CONFLICT,"runtime_required":False,"base_sha":BASE,
      },
      "provider_state":{
        "state_branch_head_sha":PROVIDER_AFTER if generation==40 else PROVIDER_BEFORE,
        "registry_blob_sha":REG_AFTER if generation==40 else REG_BEFORE,
        "registry_generation":40 if generation==40 else 39,
        "unexpired_active_in_conflict_domain":conflicts,
        "exact_owned_lease":lease,
      },
      "branch_state":{"present":True,"name":BRANCH,"head_sha":BASE,"base_sha":BASE},
      "expected_branch":BRANCH,
      "transaction_boundary":boundary,
      "completed_transaction_fingerprints":list(completed or []),
      "next_transaction_fingerprint":next_fp,
      "hbe_boundary":hbe,
      "historical_lease_rewrite_requested":False,
      "persisted_control_loop_reuse_requested":False,
      "persisted_admission_reuse_requested":False,
      "persisted_ci_reuse_requested":False,
      "persisted_cas_reuse_requested":False,
    }

def replay_hbe_definition(e):
    mod=load_module(HBE_EVALUATOR_PATH,"wu131_hbe_replay")
    policy=load_json(HBE_POLICY_PATH)
    fps=e["completed_transaction_fingerprints"]
    live=mod.evaluate(policy,make_checkpoint(completed=fps))
    if live.get("decision")!="RECOMPUTE_FRESH_CONTINUATION":
        raise ValidationError("LIVE_LEASE_REPLAY:"+repr(live))
    if live.get("authority_granted") is not False:
        raise ValidationError("LIVE_LEASE_AUTHORITY_GRANTED")
    released=make_checkpoint(lease_state="RELEASED", expired=True, generation=39, conflicts=0, completed=fps)
    claim=mod.evaluate(policy,released)
    if claim.get("decision")!="FRESH_MONOTONIC_LEASE_REQUIRED":
        raise ValidationError("FRESH_CLAIM_REPLAY:"+repr(claim))
    if claim.get("required_minimum_next_generation")!=40:
        raise ValidationError("FRESH_CLAIM_GENERATION")
    if claim.get("delegated_authority_identity")!="EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY":
        raise ValidationError("FRESH_CLAIM_DELEGATION")
    if claim.get("authority_granted") is not False:
        raise ValidationError("FRESH_CLAIM_AUTHORITY_GRANTED")
    unknown=mod.evaluate(policy,make_checkpoint(boundary="TRANSACTION_OUTCOME_UNKNOWN",completed=fps))
    if unknown.get("decision")!="RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH":
        raise ValidationError("UNKNOWN_OUTCOME_REPLAY")
    pending=mod.evaluate(policy,make_checkpoint(boundary="PROVIDER_READBACK_PENDING",completed=fps))
    if pending.get("decision")!="WAIT_FOR_FRESH_PROVIDER_READBACK":
        raise ValidationError("PENDING_READBACK_REPLAY")
    for boundary,expected in (
        ("OWNER_ESCALATION_REQUIRED","OWNER_ESCALATION_REQUIRED"),
        ("WAIT_ONLY","WAIT_ONLY"),
        ("STOP_ONLY","STOP_ONLY"),
        ("SEPARATE_AUTHORITY_REQUIRED","SEPARATE_AUTHORITY_REQUIRED"),
        ("BLOCKED","BLOCKED"),
    ):
        out=mod.evaluate(policy,make_checkpoint(hbe=boundary,completed=fps))
        if out.get("decision")!=expected:
            raise ValidationError("HBE_BOUNDARY_REPLAY:"+boundary+":"+repr(out))
        if out.get("mutation_performed") is not False or out.get("authority_granted") is not False:
            raise ValidationError("HBE_BOUNDARY_MUTATION:"+boundary)
    replay=mod.evaluate(policy,make_checkpoint(completed=fps,next_fp=fps[0]))
    if replay.get("decision")!="BLOCKED" or replay.get("reason")!="COMPLETED_TRANSACTION_REPLAY_FORBIDDEN":
        raise ValidationError("COMPLETED_REPLAY_NOT_BLOCKED")

def validate_evidence(e: dict[str,Any], *, check_anchors=True, replay=True):
    exact={
      "schema_version":1,
      "role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_SESSION_RESUME_EXECUTION_EVIDENCE",
      "evidence_state":"RECORDED",
      "work_unit_id":"PIPE-WU-131",
      "issue_number":310,
      "base_main_sha":BASE,
      "frontier_id":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_SESSION_RESUME_EXECUTION_WITH_EXISTING_AUTHORITY_ONLY",
      "predecessor_frontier_blob_sha":"806a1b12c5d9fc157c20979fd696d6080a238c74",
      "branch":BRANCH,
      "next_boundary":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_MULTI_SESSION_STEADY_STATE_WITH_EXISTING_AUTHORITY_ONLY",
    }
    for k,v in exact.items():
        if e.get(k)!=v:
            raise ValidationError("IDENTITY_MISMATCH:"+k)
    if check_anchors:
        validate_anchors(e)
    h=e.get("handoff")
    if not isinstance(h,dict) or h.get("checkpoint_transaction_boundary")!="CLEAN_ITERATION_BOUNDARY":
        raise ValidationError("HANDOFF_INVALID")
    for k in ("checkpoint_is_mutation_authority","persisted_control_loop_reused","persisted_execution_admission_reused",
              "persisted_ci_success_reused","persisted_registry_cas_reused","persisted_merge_eligibility_reused"):
        req_false(h.get(k),"handoff."+k)
    fresh=e.get("fresh_resume_truth_before_transaction")
    if not isinstance(fresh,dict):
        raise ValidationError("FRESH_TRUTH_REQUIRED")
    req_true(fresh.get("provider_truth_fresh"),"fresh.provider_truth_fresh")
    req_true(fresh.get("fresh_control_loop_required"),"fresh.control")
    req_true(fresh.get("fresh_execution_admission_required_before_mutation"),"fresh.admission")
    req_false(fresh.get("checkpoint_authority_used"),"fresh.checkpoint_authority")
    if fresh.get("current_main_sha")!=BASE or fresh.get("resume_decision")!="RECOMPUTE_FRESH_CONTINUATION":
        raise ValidationError("FRESH_TRUTH_IDENTITY")
    ps=fresh.get("provider_state") or {}
    if ps.get("state_branch_head_sha")!=PROVIDER_BEFORE or ps.get("registry_blob_sha")!=REG_BEFORE or ps.get("registry_generation")!=39:
        raise ValidationError("FRESH_PROVIDER_BEFORE")
    if ps.get("exact_work_unit_lease_present") is not False or ps.get("unexpired_active_in_conflict_domain")!=0:
        raise ValidationError("FRESH_PROVIDER_TOPOLOGY")
    if (fresh.get("branch_state") or {}).get("present") is not False:
        raise ValidationError("BRANCH_NOT_ABSENT_BEFORE")
    it=e.get("post_handoff_iterations")
    if not isinstance(it,list) or len(it)!=2:
        raise ValidationError("ITERATION_COUNT")
    if [x.get("iteration_sequence") for x in it] != [1,2]:
        raise ValidationError("ITERATION_SEQUENCE")
    expected=[
      ("PLAN_EXISTING_WRITER_LEASE_ACQUISITION","WRITER_LEASE_ACQUISITION"),
      ("PLAN_EXISTING_BOUNDED_BRANCH_CREATE","BOUNDED_BRANCH_CREATE"),
    ]
    seen=[]
    for i,(control,kind) in zip(it,expected):
        req_true(i.get("provider_truth_fresh"),"iteration.provider_truth_fresh")
        req_true(i.get("control_loop_fresh_for_iteration"),"iteration.control_fresh")
        req_true(i.get("execution_admission_fresh_for_iteration"),"iteration.admission_fresh")
        req_false(i.get("control_loop_reused_from_prior_session"),"iteration.control_reuse")
        req_false(i.get("execution_admission_reused_from_prior_session"),"iteration.admission_reuse")
        if i.get("control_loop_decision")!=control or i.get("execution_admission_decision")!="ADMIT_EXISTING_WRITER_LEASE_AUTHORITY":
            raise ValidationError("ITERATION_DECISION")
        if i.get("delegated_authority_identity")!="EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY":
            raise ValidationError("ITERATION_DELEGATION")
        if i.get("delegated_transaction_count")!=1 or i.get("transaction_kind")!=kind:
            raise ValidationError("ITERATION_TRANSACTION")
        fp=i.get("transaction_fingerprint")
        if not isinstance(fp,str) or not fp or fp in seen:
            raise ValidationError("TRANSACTION_FINGERPRINT")
        seen.append(fp)
        req_true(i.get("fresh_provider_readback_completed"),"iteration.readback")
        req_true(i.get("readback_matches_expected_transaction"),"iteration.readback_match")
    one,two=it
    r1=one["transaction_result"]
    if r1.get("provider_state_commit_sha")!=PROVIDER_AFTER or r1.get("provider_state_parent_sha")!=PROVIDER_BEFORE:
        raise ValidationError("LEASE_PROVIDER_CHAIN")
    if r1.get("registry_blob_sha")!=REG_AFTER or r1.get("lease_id")!=LEASE_ID or r1.get("generation")!=40 or r1.get("state")!="ACTIVE":
        raise ValidationError("LEASE_RESULT")
    if one["provider_state_after"].get("registry_generation")!=40 or one["provider_state_after"].get("registry_blob_sha")!=REG_AFTER:
        raise ValidationError("LEASE_READBACK")
    b2=two["branch_state_after"]
    if b2 != {"branch_present":True,"branch_head_sha":BASE,"compare_status":"identical","ahead_by":0,"behind_by":0}:
        raise ValidationError("BRANCH_READBACK")
    fps=e.get("completed_transaction_fingerprints")
    if fps!=seen or len(fps)!=len(set(fps)):
        raise ValidationError("COMPLETED_FINGERPRINT_SET")
    req_false(e.get("completed_transaction_replay_performed"),"completed_replay")
    hist=e.get("historical_writer_lease_observations") or {}
    if hist.get("wu129_generation37_state")!="ACTIVE":
        raise ValidationError("HISTORICAL_GEN37_STATE")
    req_true(hist.get("wu129_generation37_expired"),"historical.gen37.expired")
    for k in ("wu129_generation37_mutated","historical_lease_reactivated","historical_lease_silently_stolen","historical_lease_retroactively_released"):
        req_false(hist.get(k),"historical."+k)
    for section,decision in (
      ("interrupted_checkpoint_path","RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH"),
      ("readback_pending_checkpoint_path","WAIT_FOR_FRESH_PROVIDER_READBACK"),
    ):
        x=e.get(section) or {}
        if x.get("expected_resume_decision")!=decision:
            raise ValidationError("BOUNDARY_DECISION:"+section)
        req_true(x.get("provider_reconciliation_required"),section+".reconcile")
        req_false(x.get("delegated_transaction_replayed"),section+".replay")
    for k in ("checkpoint_is_mutation_authority","product_runtime_mutation_performed","runtime_action_performed",
              "adwf_binding_or_repository_mutation_performed","release_tag_promotion_performed",
              "ruleset_policy_mutation_performed","private_evidence_publication_performed",
              "reserve_1080_lifecycle_mutation_performed","primary_1081_lifecycle_mutation_performed",
              "authority_broadening_performed","higher_autonomy_authorized",
              "stale_control_loop_or_admission_reuse_performed","stale_ci_or_cas_reuse_performed",
              "inferred_or_fallback_authority_used"):
        req_false(e.get(k),k)
    req_true(e.get("fresh_provider_truth_superseded_checkpoint"),"fresh_supersedes")
    req_true(e.get("fresh_control_loop_and_admission_per_iteration"),"fresh_per_iteration")
    req_true(e.get("main_unchanged_during_post_handoff_iterations"),"main_unchanged")
    if e.get("main_sha_after_iterations")!=BASE:
        raise ValidationError("MAIN_AFTER")
    if replay:
        replay_hbe_definition(e)
    return {"status":"PASS","work_unit_id":"PIPE-WU-131","authority_granted":False,"higher_autonomy_authorized":False}

def main():
    e=load_json(EVIDENCE_PATH)
    result=validate_evidence(e)
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
