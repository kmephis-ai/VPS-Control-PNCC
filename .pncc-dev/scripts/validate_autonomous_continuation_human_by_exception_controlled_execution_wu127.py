#!/usr/bin/env python3
"""Validate PIPE-WU-127 controlled Human-by-Exception execution evidence."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE_PATH=ROOT/".pncc-dev/contracts/autonomous-continuation-human-by-exception-controlled-execution-wu127.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
BASE="0e2506e64645192236e95caad253104507c26591"
BRANCH="agent/PIPE-WU-127-controlled-human-by-exception-execution-existing-authority-only"
LEASE="b7d7e6b9-13fd-4cd6-a122-0c7b352e0cb5"
PROVIDER="a0e304b467b5781f72c8fa2afb172f89830be36b"
REGISTRY="0512749968d7d9f53128f664c521b774a9bb7fe4"
GEN=35
FALSE_FIELDS=(
 "second_controlled_transaction_performed","stale_control_loop_or_admission_reuse_performed",
 "batch_provider_mutation_performed","inferred_or_fallback_authority_used",
 "product_runtime_mutation_performed","runtime_action_performed",
 "adwf_binding_or_repository_mutation_performed","release_tag_promotion_performed",
 "ruleset_policy_mutation_performed","private_evidence_publication_performed",
 "reserve_1080_lifecycle_mutation_performed","primary_1081_lifecycle_mutation_performed",
 "authority_broadening_performed","higher_autonomy_authorized")
ANCHORS={
 "operationalization_policy_path":"5084d908bd84cd3660e8e57478f8fdf21a76ba58",
 "operationalization_evaluator_path":"d007a80900ba1ba69fd769ad778c4f5bd68a9e4d",
 "executor_grant_path":"2c62780720dace54b220cedd42f77f834886e62a",
 "delegated_authority_grant_path":"717e1f9081915f40fad2e0620c64245a650ca235",
}
STATIC_ANCHORS={
 ".pncc-dev/contracts/autonomous-continuation-control-loop-policy.json":"822bcd1833ff4843b6bd176337b3ef3b742275de",
 ".pncc-dev/scripts/evaluate_autonomous_continuation_control_loop.py":"1f794892cfec466505a1a6c38b271492f9759127",
 ".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json":"406d78da6250c452bfc7706b57dc51a18ca48977",
 ".pncc-dev/scripts/evaluate_autonomous_continuation_execution_admission.py":"cde13515632717b81cef77876e53e9ceef0c46bf",
}

class EvidenceError(ValueError): pass

def _strict(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise EvidenceError("DUPLICATE_KEY:"+k)
        out[k]=v
    return out

def load_json(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
    except (OSError,UnicodeError,json.JSONDecodeError) as e:
        raise EvidenceError(f"INVALID_JSON:{Path(path).as_posix()}:{type(e).__name__}") from e

def blob_sha(path):
    b=Path(path).read_bytes(); return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def _require(obj,key,value=True):
    if obj.get(key) is not value: raise EvidenceError("REQUIRED:"+key)

def _sha(value,name):
    if not isinstance(value,str) or SHA40.fullmatch(value) is None: raise EvidenceError("SHA_INVALID:"+name)
    return value

def validate_anchors(e,root=ROOT):
    for path_key,expected in ANCHORS.items():
        rel=e.get(path_key)
        if not isinstance(rel,str) or not rel: raise EvidenceError("ANCHOR_PATH_INVALID:"+path_key)
        p=root/rel
        if not p.is_file() or blob_sha(p)!=expected: raise EvidenceError("ANCHOR_DRIFT:"+path_key)
        blob_key=path_key.replace("_path","_blob_sha")
        if e.get(blob_key)!=expected: raise EvidenceError("ANCHOR_DECLARATION_DRIFT:"+blob_key)
    declared={
      "control_loop_policy_blob_sha":"822bcd1833ff4843b6bd176337b3ef3b742275de",
      "control_loop_evaluator_blob_sha":"1f794892cfec466505a1a6c38b271492f9759127",
      "execution_admission_policy_blob_sha":"406d78da6250c452bfc7706b57dc51a18ca48977",
      "execution_admission_evaluator_blob_sha":"cde13515632717b81cef77876e53e9ceef0c46bf"}
    for k,v in declared.items():
        if e.get(k)!=v: raise EvidenceError("ANCHOR_DECLARATION_DRIFT:"+k)
    for rel,expected in STATIC_ANCHORS.items():
        p=root/rel
        if not p.is_file() or blob_sha(p)!=expected: raise EvidenceError("ANCHOR_DRIFT:"+rel)

def validate_registry(reg):
    if not isinstance(reg,dict) or reg.get("schema_version")!=1 or reg.get("role")!="WRITER_LEASE_REGISTRY":
        raise EvidenceError("REGISTRY_IDENTITY_INVALID")
    if reg.get("generation")!=GEN: raise EvidenceError("REGISTRY_GENERATION_INVALID")
    entries=reg.get("entries")
    if not isinstance(entries,list): raise EvidenceError("REGISTRY_ENTRIES_INVALID")
    active=[x for x in entries if isinstance(x,dict) and x.get("state")=="ACTIVE"]
    if len(active)!=1: raise EvidenceError("REGISTRY_ACTIVE_COUNT_INVALID")
    x=active[0]
    exact={"lease_id":LEASE,"work_unit_id":"PIPE-WU-127","generation":GEN,"base_sha":BASE,"branch":BRANCH,"holder":"chatgpt-wave5-writer","expires_at":"2026-08-30T21:01:53Z"}
    for k,v in exact.items():
        if x.get(k)!=v: raise EvidenceError("REGISTRY_LEASE_BINDING_INVALID:"+k)
    if any(isinstance(y,dict) and y is not x and y.get("state")=="ACTIVE" for y in entries):
        raise EvidenceError("REGISTRY_SECOND_ACTIVE_LEASE")
    return x

def validate(e:dict[str,Any],reg:dict[str,Any],*,check_anchors=True,root=ROOT):
    exact={
      "schema_version":1,
      "role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_CONTROLLED_EXECUTION_EVIDENCE",
      "evidence_state":"RECORDED",
      "work_unit_id":"PIPE-WU-127",
      "issue_number":302,
      "base_main_sha":BASE,
      "frontier_id":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_EXECUTION_WITH_EXISTING_AUTHORITY_ONLY",
      "predecessor_frontier_blob_sha":"62b8bd9d37203ef62a6e4e6b322829e0afb46f72",
      "branch":BRANCH,
      "next_boundary":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_STEADY_STATE_WITH_EXISTING_AUTHORITY_ONLY"}
    if not isinstance(e,dict): raise EvidenceError("EVIDENCE_OBJECT_REQUIRED")
    for k,v in exact.items():
        if e.get(k)!=v: raise EvidenceError("EVIDENCE_FIELD_INVALID:"+k)
    if check_anchors: validate_anchors(e,root=root)
    validate_registry(reg)
    p=e.get("writer_lease_prerequisite")
    if not isinstance(p,dict): raise EvidenceError("LEASE_PREREQUISITE_REQUIRED")
    lease_exact={"lease_id":LEASE,"holder":"chatgpt-wave5-writer","state":"ACTIVE","generation":GEN,"provider_state_commit_sha":PROVIDER,"registry_blob_sha":REGISTRY,"expires_at":"2026-08-30T21:01:53Z","lease_acquisition_counted_as_controlled_transaction":False}
    for k,v in lease_exact.items():
        if p.get(k)!=v: raise EvidenceError("LEASE_PREREQUISITE_INVALID:"+k)
    selected=e.get("selected_work_unit")
    selected_exact={"work_unit_id":"PIPE-WU-127","issue_number":302,"marker_state":"READY","conflict_domain":"wave5-autonomous-continuation-human-by-exception-operationalization-execution-existing-authority-only","runtime_required":False,"base_sha":BASE}
    if selected!=selected_exact: raise EvidenceError("SELECTED_WORK_UNIT_INVALID")
    t=e.get("controlled_transaction")
    if not isinstance(t,dict): raise EvidenceError("CONTROLLED_TRANSACTION_REQUIRED")
    txn_exact={"transaction_sequence":1,"transaction_count":1,"transaction_limit":1,"transaction_kind":"BOUNDED_BRANCH_CREATE","control_loop_decision":"PLAN_EXISTING_BOUNDED_BRANCH_CREATE","execution_admission_decision":"ADMIT_EXISTING_WRITER_LEASE_AUTHORITY","delegated_authority_identity":"EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY","target_action":"BOUNDED_NON_MAIN_BRANCH_CREATE_PATH","operationalization_outcome":"CONTINUE_UNDER_EXISTING_AUTHORITY_ONLY","automatic_continuation_permitted":True,"automatic_replay_permitted":False,"operationalizer_mutation_authority":False,"executor_grant_canonical":True,"delegated_grant_canonical":True,"fresh_control_loop_required":True,"fresh_execution_admission_required":True,"readback_matches_expected_transaction":True}
    for k,v in txn_exact.items():
        if t.get(k)!=v: raise EvidenceError("TRANSACTION_FIELD_INVALID:"+k)
    before=t.get("provider_state_before",{}); after=t.get("provider_state_after",{})
    for obj,name in ((before,"BEFORE"),(after,"AFTER")):
        if obj.get("state_branch_head_sha")!=PROVIDER or obj.get("registry_blob_sha")!=REGISTRY or obj.get("registry_generation")!=GEN or obj.get("exact_work_unit_lease_present") is not True or obj.get("exact_work_unit_lease_state")!="ACTIVE":
            raise EvidenceError("PROVIDER_STATE_"+name+"_INVALID")
    if after.get("fresh_readback_completed") is not True: raise EvidenceError("PROVIDER_AFTER_READBACK_REQUIRED")
    b0=t.get("branch_state_before",{})
    if b0.get("preflight_completed") is not True or b0.get("branch_present") is not False: raise EvidenceError("BRANCH_PREFLIGHT_INVALID")
    r=t.get("transaction_result",{})
    result_exact={"delegated_transaction_performed":True,"provider_state_mutation_performed":False,"branch_mutation_performed":True,"branch_created":True,"branch_head_sha":BASE,"branch_base_sha":BASE}
    if r!=result_exact: raise EvidenceError("TRANSACTION_RESULT_INVALID")
    b1=t.get("branch_state_after",{})
    if b1!={"fresh_readback_completed":True,"branch_present":True,"branch_head_sha":BASE,"compare_status":"identical","ahead_by":0,"behind_by":0}: raise EvidenceError("BRANCH_READBACK_INVALID")
    m=t.get("main_state_after",{})
    if m!={"fresh_readback_completed":True,"main_sha":BASE,"main_unchanged":True}: raise EvidenceError("MAIN_READBACK_INVALID")
    boundaries=e.get("boundary_validation")
    if not isinstance(boundaries,dict) or set(boundaries)!={"OWNER_ESCALATION_REQUIRED","WAIT_ONLY","STOP_ONLY","SEPARATE_AUTHORITY_REQUIRED","BLOCKED"}: raise EvidenceError("BOUNDARY_SET_INVALID")
    for name,v in boundaries.items():
        if not isinstance(v,dict) or v.get("mutation_permitted") is not False: raise EvidenceError("BOUNDARY_MUTATION_INVALID:"+name)
    if boundaries["OWNER_ESCALATION_REQUIRED"].get("automatic_replay_permitted") is not False or boundaries["OWNER_ESCALATION_REQUIRED"].get("owner_visible") is not True: raise EvidenceError("OWNER_BOUNDARY_INVALID")
    if boundaries["WAIT_ONLY"].get("automatic_replay_permitted") is not False: raise EvidenceError("WAIT_REPLAY_INVALID")
    if boundaries["STOP_ONLY"].get("terminal") is not True: raise EvidenceError("STOP_TERMINAL_INVALID")
    if boundaries["SEPARATE_AUTHORITY_REQUIRED"].get("fail_closed") is not True or boundaries["BLOCKED"].get("fail_closed") is not True: raise EvidenceError("FAIL_CLOSED_BOUNDARY_INVALID")
    for k in FALSE_FIELDS:
        if e.get(k) is not False: raise EvidenceError("FORBIDDEN_TRUE:"+k)
    return {"status":"VALID","work_unit_id":"PIPE-WU-127","transaction_kind":"BOUNDED_BRANCH_CREATE","transaction_count":1,"next_boundary":e["next_boundary"]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--evidence",default=str(EVIDENCE_PATH)); ap.add_argument("--registry",required=True); a=ap.parse_args()
    try:
        out=validate(load_json(a.evidence),load_json(a.registry)); print(json.dumps(out,indent=2,sort_keys=True)); return 0
    except EvidenceError as exc:
        print(json.dumps({"status":"BLOCKED","reason":str(exc)},indent=2,sort_keys=True)); return 2
if __name__=="__main__": raise SystemExit(main())
