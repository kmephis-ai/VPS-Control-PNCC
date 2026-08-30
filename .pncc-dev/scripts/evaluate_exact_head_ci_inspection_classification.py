#!/usr/bin/env python3
"""Read-only exact-head CI inspection and fail-closed failure classification."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any, Callable

ROOT=Path(__file__).resolve().parents[2]
POLICY_PATH=ROOT/".pncc-dev/contracts/exact-head-ci-inspection-classification-policy.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
FALSE_AUTHORITIES=(
"provider_mutation_authority","workflow_rerun_authority","issue_mutation_authority","branch_mutation_authority",
"pull_request_mutation_authority","writer_lease_mutation_authority","merge_authority","runtime_action_authority",
"product_runtime_mutation_authority","adwf_binding_mutation_authority","adwf_repository_mutation_authority",
"release_tag_promotion_authority","ruleset_policy_mutation_authority","private_evidence_publication_authority",
"reserve_1080_lifecycle_mutation_authority","primary_1081_lifecycle_mutation_authority")

class CiInspectionError(ValueError): pass

def _strict(pairs):
    d={}
    for k,v in pairs:
        if k in d: raise CiInspectionError("DUPLICATE_KEY:"+k)
        d[k]=v
    return d

def load_json(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
    except (OSError,UnicodeError,json.JSONDecodeError) as e:
        raise CiInspectionError(f"INVALID_JSON:{Path(path).as_posix()}:{type(e).__name__}") from e

def git_blob_sha_path(path):
    b=Path(path).read_bytes()
    return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def validate_policy(p):
    if p.get("schema_version")!=1 or p.get("role")!="EXACT_HEAD_CI_INSPECTION_CLASSIFICATION_POLICY":
        raise CiInspectionError("POLICY_IDENTITY_INVALID")
    exact={"mode":"READ_ONLY_FAIL_CLOSED","repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main",
    "snapshot_role":"EXACT_HEAD_CI_PROVIDER_SNAPSHOT","completed_status":"completed","success_conclusion":"success",
    "failure_attribution_policy":"EXPLICIT_EVIDENCE_REQUIRED_NEVER_INFER_FROM_WORKFLOW_NAME",
    "failure_attribution_source":"HOSTED_CI_JOB_STEP_LOG_OR_MACHINE_EVIDENCE",
    "mixed_failure_classification_policy":"PROVIDER_ENVIRONMENT_AMBIGUITY",
    "missing_failure_attribution_policy":"PROVIDER_ENVIRONMENT_AMBIGUITY",
    "next_boundary":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_INTEGRATION"}
    for k,v in exact.items():
        if p.get(k)!=v: raise CiInspectionError("POLICY_FIELD_INVALID:"+k)
    for k in ("provider_truth_fresh_required","inventory_complete_required","effective_inventory_required",
              "superseded_runs_accounted_for_required","exact_pr_head_binding_required","unique_effective_workflow_name_required"):
        if p.get(k) is not True: raise CiInspectionError("POLICY_REQUIRED_TRUE:"+k)
    if p.get("decisions")!=["CI_SUCCESS","CI_PENDING","HARNESS_OR_VALIDATION_DEFECT_CANDIDATE",
        "PRODUCT_RUNTIME_DEFECT_CANDIDATE","PROVIDER_ENVIRONMENT_AMBIGUITY","BLOCKED"]:
        raise CiInspectionError("POLICY_DECISIONS_INVALID")
    paths,blobs=p.get("anchor_paths"),p.get("anchor_blobs")
    if not isinstance(paths,dict) or not isinstance(blobs,dict) or set(paths)!=set(blobs):
        raise CiInspectionError("POLICY_ANCHOR_MAP_INVALID")
    if set(p.get("next_boundaries",{}))!=set(p["decisions"]): raise CiInspectionError("POLICY_NEXT_BOUNDARIES_INVALID")
    for k in FALSE_AUTHORITIES:
        if p.get(k) is not False: raise CiInspectionError("POLICY_AUTHORITY_PRESENT:"+k)

def validate_anchor_map(p,*,root=ROOT,blob_reader=git_blob_sha_path):
    for k,rel in sorted(p["anchor_paths"].items()):
        path=root/rel
        if not path.is_file(): raise CiInspectionError("ANCHOR_MISSING:"+k)
        if blob_reader(path)!=p["anchor_blobs"][k]: raise CiInspectionError("ANCHOR_DRIFT:"+k)

def _out(decision,p,**kw):
    return {"schema_version":1,"role":"EXACT_HEAD_CI_INSPECTION_CLASSIFICATION_DECISION",
    "state":"READ_ONLY_CI_INSPECTION_BLOCKED" if decision=="BLOCKED" else "READ_ONLY_CI_INSPECTION_PASS",
    "decision":decision,"reasons":kw.get("reasons",[]),"pr_number":kw.get("pr_number"),
    "pr_head_sha":kw.get("pr_head_sha"),"workflow_count":kw.get("workflow_count",0),
    "pending_workflows":kw.get("pending_workflows",[]),"failed_workflows":kw.get("failed_workflows",[]),
    "failure_classification_evidence":kw.get("evidence",[]),"provider_mutation_performed":False,
    "workflow_rerun_performed":False,"branch_mutation_performed":False,"pull_request_mutation_performed":False,
    "writer_lease_mutation_performed":False,"merge_performed":False,"runtime_action_performed":False,
    "product_runtime_mutation_performed":False,"next_boundary":p["next_boundaries"][decision]}

def _attr(raw,p,name):
    if raw is None: return None,None
    if not isinstance(raw,dict): raise CiInspectionError("FAILURE_ATTRIBUTION_OBJECT_REQUIRED:"+name)
    c=raw.get("classification")
    if c not in p["failure_attribution_classes"]: raise CiInspectionError("FAILURE_ATTRIBUTION_CLASS_INVALID:"+name)
    if raw.get("source")!=p["failure_attribution_source"]: raise CiInspectionError("FAILURE_ATTRIBUTION_SOURCE_INVALID:"+name)
    e=raw.get("evidence")
    if not isinstance(e,list) or not e or any(not isinstance(x,str) or not x.strip() for x in e):
        raise CiInspectionError("FAILURE_ATTRIBUTION_EVIDENCE_REQUIRED:"+name)
    h,r=raw.get("harness_or_validation_surface_implicated"),raw.get("product_runtime_surface_implicated")
    if not isinstance(h,bool) or not isinstance(r,bool): raise CiInspectionError("FAILURE_ATTRIBUTION_SURFACE_FLAGS_REQUIRED:"+name)
    if c=="HARNESS_OR_VALIDATION_DEFECT" and (not h or r): raise CiInspectionError("FAILURE_ATTRIBUTION_HARNESS_FLAGS_INVALID:"+name)
    if c=="PRODUCT_RUNTIME_DEFECT_CANDIDATE" and (not r or h): raise CiInspectionError("FAILURE_ATTRIBUTION_PRODUCT_FLAGS_INVALID:"+name)
    if c=="PROVIDER_ENVIRONMENT_AMBIGUITY" and (h or r): raise CiInspectionError("FAILURE_ATTRIBUTION_AMBIGUITY_FLAGS_INVALID:"+name)
    return c,{"workflow_name":name,**raw}

def evaluate_exact_head_ci(s,*,policy=None,root=ROOT,check_anchors=True,blob_reader=git_blob_sha_path):
    p=policy or load_json(POLICY_PATH)
    try:
        validate_policy(p)
        if check_anchors: validate_anchor_map(p,root=root,blob_reader=blob_reader)
        if not isinstance(s,dict) or s.get("schema_version")!=1 or s.get("role")!=p["snapshot_role"]:
            raise CiInspectionError("SNAPSHOT_IDENTITY_INVALID")
        for k,v in (("repository",p["repository"]),("default_branch",p["default_branch"])):
            if s.get(k)!=v: raise CiInspectionError("SNAPSHOT_"+k.upper()+"_MISMATCH")
        for k,msg in (("provider_truth_fresh","PROVIDER_TRUTH_NOT_FRESH"),("inventory_complete","CI_INVENTORY_INCOMPLETE"),
                      ("effective_inventory","CI_EFFECTIVE_INVENTORY_REQUIRED"),("superseded_runs_accounted_for","CI_SUPERSEDED_RUNS_NOT_ACCOUNTED_FOR")):
            if s.get(k) is not True: raise CiInspectionError(msg)
        n=s.get("pr_number")
        if not isinstance(n,int) or isinstance(n,bool) or n<1: raise CiInspectionError("PR_NUMBER_INVALID")
        base,head,obs=s.get("pr_base_sha"),s.get("pr_head_sha"),s.get("observed_pr_head_sha")
        for k,v in (("pr_base_sha",base),("pr_head_sha",head),("observed_pr_head_sha",obs)):
            if not isinstance(v,str) or not SHA40.fullmatch(v): raise CiInspectionError("SHA_INVALID:"+k)
        if head!=obs: raise CiInspectionError("PR_HEAD_DRIFT")
        if base==head: raise CiInspectionError("PR_BASE_HEAD_COLLISION")
        runs=s.get("workflow_runs")
        if not isinstance(runs,list) or not runs: raise CiInspectionError("WORKFLOW_RUNS_REQUIRED")
        names=set(); pending=[]; failures=[]; classes=[]; evidence=[]
        statuses=set(p["pending_statuses"])|{p["completed_status"]}
        conclusions=set(p["non_success_conclusions"])|{p["success_conclusion"]}
        for x in runs:
            if not isinstance(x,dict): raise CiInspectionError("WORKFLOW_RUN_OBJECT_REQUIRED")
            name=x.get("name"); rid=x.get("id")
            if not isinstance(rid,int) or isinstance(rid,bool) or rid<1: raise CiInspectionError("WORKFLOW_RUN_ID_INVALID")
            if not isinstance(name,str) or not name.strip(): raise CiInspectionError("WORKFLOW_NAME_INVALID")
            if name in names: raise CiInspectionError("DUPLICATE_EFFECTIVE_WORKFLOW_NAME:"+name)
            names.add(name)
            if x.get("head_sha")!=head: raise CiInspectionError("WORKFLOW_HEAD_MISMATCH:"+name)
            status=x.get("status")
            if status not in statuses: raise CiInspectionError("WORKFLOW_STATUS_UNKNOWN:"+name)
            concl=x.get("conclusion")
            if status in p["pending_statuses"]:
                if concl is not None: raise CiInspectionError("PENDING_WORKFLOW_HAS_CONCLUSION:"+name)
                pending.append(name); continue
            if concl not in conclusions: raise CiInspectionError("WORKFLOW_CONCLUSION_UNKNOWN:"+name)
            if concl==p["success_conclusion"]:
                if x.get("failure_attribution") is not None: raise CiInspectionError("SUCCESS_WORKFLOW_HAS_FAILURE_ATTRIBUTION:"+name)
                continue
            failures.append(name); c,a=_attr(x.get("failure_attribution"),p,name); classes.append(c)
            if a: evidence.append(a)
        missing=sorted(set(p["required_workflows"])-names)
        if missing: raise CiInspectionError("REQUIRED_WORKFLOW_MISSING:"+",".join(missing))
        common={"pr_number":n,"pr_head_sha":head,"workflow_count":len(runs),"failed_workflows":sorted(failures),"evidence":evidence}
        if pending: return _out("CI_PENDING",p,pending_workflows=sorted(pending),**common)
        if not failures: return _out("CI_SUCCESS",p,pr_number=n,pr_head_sha=head,workflow_count=len(runs))
        distinct=set(classes)
        if None in distinct or len(distinct)!=1 or "PROVIDER_ENVIRONMENT_AMBIGUITY" in distinct:
            d="PROVIDER_ENVIRONMENT_AMBIGUITY"
        elif distinct=={"HARNESS_OR_VALIDATION_DEFECT"}: d="HARNESS_OR_VALIDATION_DEFECT_CANDIDATE"
        elif distinct=={"PRODUCT_RUNTIME_DEFECT_CANDIDATE"}: d="PRODUCT_RUNTIME_DEFECT_CANDIDATE"
        else: d="PROVIDER_ENVIRONMENT_AMBIGUITY"
        return _out(d,p,**common)
    except (CiInspectionError,KeyError,TypeError) as e:
        return _out("BLOCKED",p,reasons=[str(e)])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--policy",default=str(POLICY_PATH)); a=ap.parse_args()
    p=load_json(a.policy); r=evaluate_exact_head_ci(load_json(a.input),policy=p); print(json.dumps(r,indent=2,sort_keys=True))
    return 2 if r["decision"]=="BLOCKED" else 0

if __name__=="__main__": raise SystemExit(main())
