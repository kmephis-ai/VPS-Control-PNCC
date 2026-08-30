#!/usr/bin/env python3
"""PLAN_ONLY default-deny admission for autonomous continuation decisions."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
POLICY_PATH=ROOT/".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
FALSE_AUTH=(
"provider_mutation_authority","issue_create_authority","issue_update_authority","issue_close_authority",
"branch_mutation_authority","pull_request_mutation_authority","writer_lease_mutation_authority",
"workflow_rerun_authority","merge_authority","runtime_action_authority","product_runtime_mutation_authority",
"adwf_binding_mutation_authority","adwf_repository_mutation_authority","release_tag_promotion_authority",
"ruleset_policy_mutation_authority","private_evidence_publication_authority",
"reserve_1080_lifecycle_mutation_authority","primary_1081_lifecycle_mutation_authority")

class AdmissionError(ValueError): pass

def _strict(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise AdmissionError("DUPLICATE_KEY:"+k)
        out[k]=v
    return out

def load_json(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
    except (OSError,UnicodeError,json.JSONDecodeError) as e:
        raise AdmissionError(f"INVALID_JSON:{Path(path).as_posix()}:{type(e).__name__}") from e

def blob_sha(path):
    b=Path(path).read_bytes()
    return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def validate_policy(p):
    if p.get("schema_version")!=1 or p.get("role")!="AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_POLICY":
        raise AdmissionError("POLICY_IDENTITY_INVALID")
    if p.get("mode")!="PLAN_ONLY_DEFAULT_DENY": raise AdmissionError("POLICY_MODE_INVALID")
    if p.get("repository")!="kmephis-ai/VPS-Control-PNCC" or p.get("default_branch")!="main":
        raise AdmissionError("POLICY_REPOSITORY_INVALID")
    if p.get("snapshot_role")!="AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_SNAPSHOT":
        raise AdmissionError("POLICY_SNAPSHOT_ROLE_INVALID")
    if p.get("control_loop_role")!="AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION":
        raise AdmissionError("POLICY_CONTROL_LOOP_ROLE_INVALID")
    if p.get("provider_truth_fresh_required") is not True or p.get("exact_current_main_binding_required") is not True:
        raise AdmissionError("POLICY_FRESH_BINDING_REQUIRED")
    decisions=p.get("admission_decisions")
    mapping=p.get("control_loop_mapping")
    delegated=p.get("delegated_authority_identity")
    if not isinstance(decisions,list) or len(decisions)!=len(set(decisions)) or "BLOCKED" not in decisions:
        raise AdmissionError("POLICY_DECISIONS_INVALID")
    if not isinstance(mapping,dict) or not isinstance(delegated,dict) or set(delegated)!=set(decisions):
        raise AdmissionError("POLICY_MAPPING_INVALID")
    paths,blobs=p.get("anchor_paths"),p.get("anchor_blobs")
    if not isinstance(paths,dict) or not isinstance(blobs,dict) or set(paths)!=set(blobs):
        raise AdmissionError("POLICY_ANCHOR_MAP_INVALID")
    for k in FALSE_AUTH:
        if p.get(k) is not False: raise AdmissionError("POLICY_AUTHORITY_PRESENT:"+k)

def validate_anchors(p,root=ROOT):
    for k,rel in sorted(p["anchor_paths"].items()):
        path=root/rel
        if not path.is_file(): raise AdmissionError("ANCHOR_MISSING:"+k)
        if blob_sha(path)!=p["anchor_blobs"][k]: raise AdmissionError("ANCHOR_DRIFT:"+k)

def _sha(v,name):
    if not isinstance(v,str) or SHA40.fullmatch(v) is None: raise AdmissionError("SHA_INVALID:"+name)
    return v

def _require(e,key,val=True):
    if e.get(key) is not val: raise AdmissionError("EVIDENCE_REQUIRED:"+key)

def _out(decision,p,control,*,target=None,reasons=None):
    return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_DECISION",
            "state":"PLAN_ONLY_ADMISSION_BLOCKED" if decision=="BLOCKED" else "PLAN_ONLY_ADMISSION_PASS",
            "decision":decision,"reasons":reasons or [],
            "control_loop_decision":None if not isinstance(control,dict) else control.get("decision"),
            "delegated_authority":p["delegated_authority_identity"][decision],
            "target_action":target,
            "provider_mutation_performed":False,"issue_mutation_performed":False,
            "branch_mutation_performed":False,"pull_request_mutation_performed":False,
            "writer_lease_mutation_performed":False,"workflow_rerun_performed":False,
            "merge_performed":False,"runtime_action_performed":False,
            "next_boundary":p["next_boundary"]}

def _validate_control(c,p):
    if not isinstance(c,dict) or c.get("schema_version")!=1 or c.get("role")!=p["control_loop_role"]:
        raise AdmissionError("CONTROL_LOOP_IDENTITY_INVALID")
    if c.get("state") not in {"PLAN_ONLY_CONTROL_LOOP_PASS","PLAN_ONLY_CONTROL_LOOP_BLOCKED"}:
        raise AdmissionError("CONTROL_LOOP_STATE_INVALID")
    for k in ("provider_mutation_performed","issue_mutation_performed","branch_mutation_performed",
              "pull_request_mutation_performed","writer_lease_mutation_performed","workflow_rerun_performed",
              "merge_performed","runtime_action_performed","product_runtime_mutation_performed"):
        if c.get(k) is not False: raise AdmissionError("CONTROL_LOOP_MUTATION_REPORTED:"+k)
    decision=c.get("decision")
    if decision not in p["control_loop_mapping"]: raise AdmissionError("CONTROL_LOOP_DECISION_INVALID")
    expected=p["delegated_authority_identity"][p["control_loop_mapping"][decision]]
    if c.get("delegated_authority")!=expected: raise AdmissionError("CONTROL_LOOP_DELEGATION_MISMATCH")
    return decision,p["control_loop_mapping"][decision]

def _selected(e,current):
    _require(e,"selected_work_unit_exact")
    _require(e,"selected_issue_open")
    _require(e,"runtime_required_false")
    if e.get("selected_base_sha")!=current: raise AdmissionError("SELECTED_BASE_MAIN_MISMATCH")
    wu=e.get("work_unit_id")
    issue=e.get("issue_number")
    if not isinstance(wu,str) or not re.fullmatch(r"PIPE-WU-[0-9]+",wu): raise AdmissionError("WORK_UNIT_ID_INVALID")
    if not isinstance(issue,int) or isinstance(issue,bool) or issue<1: raise AdmissionError("ISSUE_NUMBER_INVALID")
    return wu

def evaluate(snapshot,*,policy=None,root=ROOT,check_anchors=True):
    p=policy or load_json(POLICY_PATH)
    control=None
    try:
        validate_policy(p)
        if check_anchors: validate_anchors(p,root=root)
        if not isinstance(snapshot,dict) or snapshot.get("schema_version")!=1 or snapshot.get("role")!=p["snapshot_role"]:
            raise AdmissionError("SNAPSHOT_IDENTITY_INVALID")
        if snapshot.get("repository")!=p["repository"] or snapshot.get("default_branch")!=p["default_branch"]:
            raise AdmissionError("SNAPSHOT_PROVIDER_IDENTITY_MISMATCH")
        if snapshot.get("provider_truth_fresh") is not True: raise AdmissionError("PROVIDER_TRUTH_NOT_FRESH")
        current=_sha(snapshot.get("current_main_sha"),"current_main_sha")
        control=snapshot.get("control_loop_decision")
        cdecision,decision=_validate_control(control,p)
        e=snapshot.get("transaction_evidence")
        if not isinstance(e,dict): raise AdmissionError("TRANSACTION_EVIDENCE_REQUIRED")

        if decision=="BLOCKED":
            return _out("BLOCKED",p,control,reasons=["CONTROL_LOOP_BLOCKED"])
        if decision=="WAIT_ONLY":
            if cdecision=="WAIT_FOR_EXACT_HEAD_CI": _require(e,"exact_pr_head_binding")
            return _out(decision,p,control,target="WAIT_NO_MUTATION")
        if decision=="STOP_ONLY":
            _require(e,"frontier_none")
            return _out(decision,p,control,target="STOP_NO_MUTATION")
        if decision=="SEPARATE_AUTHORITY_REQUIRED":
            _require(e,"failure_classification_present")
            return _out(decision,p,control,target="REQUIRE_SEPARATE_RECOVERY_AUTHORITY")

        if decision=="ADMIT_EXISTING_MATERIALIZATION_AUTHORITY":
            for k in ("selector_no_work","no_open_canonical_work_unit","materialization_eligible",
                      "proposal_deterministic","proposal_runtime_required_false","proposed_issue_absent"):
                _require(e,k)
            if e.get("proposal_base_sha")!=current: raise AdmissionError("PROPOSAL_BASE_MAIN_MISMATCH")
            return _out(decision,p,control,target="EXACT_SINGLE_PLANNER_DERIVED_ISSUE_CREATE_PATH")

        wu=_selected(e,current)
        branch=e.get("branch_name")
        if not isinstance(branch,str) or not branch.startswith("agent/"+wu+"-"):
            raise AdmissionError("BRANCH_BINDING_INVALID")

        if decision=="ADMIT_EXISTING_WRITER_LEASE_AUTHORITY":
            if cdecision=="PLAN_EXISTING_WRITER_LEASE_ACQUISITION":
                for k in ("claim_eligible","no_conflicting_unexpired_lease","registry_cas_fresh"):
                    _require(e,k)
                _sha(e.get("provider_state_head_sha"),"provider_state_head_sha")
                _sha(e.get("registry_blob_sha"),"registry_blob_sha")
                target="WRITER_LEASE_ACQUIRE_FRESH_CAS_PATH"
            elif cdecision=="PLAN_EXISTING_BOUNDED_BRANCH_CREATE":
                for k in ("exact_active_unexpired_lease","branch_absent"): _require(e,k)
                target="BOUNDED_NON_MAIN_BRANCH_CREATE_PATH"
            elif cdecision=="CONTINUE_EXISTING_BOUNDED_BRANCH":
                for k in ("exact_active_unexpired_lease","branch_exists","branch_head_exact"): _require(e,k)
                target="BOUNDED_BRANCH_CONTINUATION_PATH"
            elif cdecision=="PLAN_EXISTING_PULL_REQUEST_CREATE":
                for k in ("exact_active_unexpired_lease","branch_exists","branch_head_exact","pull_request_absent"): _require(e,k)
                target="EXACT_BOUNDED_PULL_REQUEST_CREATE_PATH"
            elif cdecision=="PLAN_EXISTING_WRITER_LEASE_RELEASE":
                for k in ("exact_active_unexpired_lease","pull_request_open_exact","exact_head_ci_success",
                          "no_pending_checks","registry_cas_fresh"): _require(e,k)
                target="WRITER_LEASE_RELEASE_FRESH_CAS_PATH"
            else:
                raise AdmissionError("WRITER_LEASE_CONTROL_DECISION_INVALID")
            return _out(decision,p,control,target=target)

        if decision=="ADMIT_EXISTING_MERGE_CLOSE_AUTHORITY":
            _require(e,"exact_released_lease")
            _require(e,"provider_state_no_drift_after_release")
            phase=e.get("merge_close_phase")
            if phase=="MERGE":
                for k in ("pull_request_open_exact","pull_request_mergeable","exact_head_ci_success",
                          "no_pending_checks","head_no_drift","no_protected_surface_violation"):
                    _require(e,k)
                target="WU100_PINNED_MERGE_ELIGIBILITY_PATH"
            elif phase=="CLOSE":
                for k in ("merge_completed","actual_merge_sha_readback","current_main_equals_actual_merge_sha",
                          "exact_work_unit_issue_open"):
                    _require(e,k)
                if e.get("actual_merge_sha")!=current: raise AdmissionError("MERGE_SHA_MAIN_MISMATCH")
                target="WU100_EXACT_ISSUE_CLOSE_ELIGIBILITY_PATH"
            else:
                raise AdmissionError("MERGE_CLOSE_PHASE_INVALID")
            return _out(decision,p,control,target=target)
        raise AdmissionError("ADMISSION_DECISION_UNHANDLED")
    except (AdmissionError,KeyError,TypeError) as exc:
        try: validate_policy(p)
        except Exception: pass
        return _out("BLOCKED",p,control,reasons=[str(exc)])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--policy",default=str(POLICY_PATH))
    a=ap.parse_args()
    p=load_json(a.policy); result=evaluate(load_json(a.input),policy=p)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 2 if result["decision"]=="BLOCKED" else 0

if __name__=="__main__": raise SystemExit(main())
