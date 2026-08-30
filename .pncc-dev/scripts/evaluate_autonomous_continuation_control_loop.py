#!/usr/bin/env python3
"""PLAN_ONLY fail-closed autonomous continuation control-loop composition."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
POLICY_PATH=ROOT/".pncc-dev/contracts/autonomous-continuation-control-loop-policy.json"
SHA40=re.compile(r"^[0-9a-f]{40}$")
FALSE_AUTHORITIES=(
"provider_mutation_authority","issue_create_authority","issue_update_authority","issue_close_authority",
"branch_mutation_authority","pull_request_mutation_authority","writer_lease_mutation_authority","workflow_rerun_authority",
"merge_authority","runtime_action_authority","product_runtime_mutation_authority","adwf_binding_mutation_authority",
"adwf_repository_mutation_authority","release_tag_promotion_authority","ruleset_policy_mutation_authority",
"private_evidence_publication_authority","reserve_1080_lifecycle_mutation_authority","primary_1081_lifecycle_mutation_authority")

class ControlLoopError(ValueError): pass

def _strict(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise ControlLoopError("DUPLICATE_KEY:"+k)
        out[k]=v
    return out

def load_json(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8-sig"),object_pairs_hook=_strict)
    except (OSError,UnicodeError,json.JSONDecodeError) as e:
        raise ControlLoopError(f"INVALID_JSON:{Path(path).as_posix()}:{type(e).__name__}") from e

def git_blob_sha_path(path):
    b=Path(path).read_bytes(); return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def validate_policy(p):
    if p.get("schema_version")!=1 or p.get("role")!="AUTONOMOUS_CONTINUATION_CONTROL_LOOP_POLICY":
        raise ControlLoopError("POLICY_IDENTITY_INVALID")
    exact={"mode":"PLAN_ONLY_FAIL_CLOSED","repository":"kmephis-ai/VPS-Control-PNCC","default_branch":"main",
           "snapshot_role":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_SNAPSHOT",
           "continuation_role":"PROVIDER_TRUTH_CONTINUATION_DECISION",
           "ci_role":"EXACT_HEAD_CI_INSPECTION_CLASSIFICATION_DECISION",
           "next_boundary":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_EXECUTION_ADMISSION"}
    for k,v in exact.items():
        if p.get(k)!=v: raise ControlLoopError("POLICY_FIELD_INVALID:"+k)
    required=("provider_truth_fresh_required","exact_current_main_binding_required","selected_runtime_required_must_be_false",
              "selected_issue_must_be_open","exact_lease_binding_required_when_present",
              "exact_non_main_work_unit_branch_required_when_present","exact_pr_branch_head_binding_required_when_present",
              "ci_decision_required_for_open_pr","post_merge_stale_base_recovery_allowed",
              "post_merge_recovery_requires_exact_selector_stale_base","merged_pr_main_readback_required",
              "merged_pr_requires_released_lease")
    for k in required:
        if p.get(k) is not True: raise ControlLoopError("POLICY_REQUIRED_TRUE:"+k)
    decisions=p.get("decisions")
    if not isinstance(decisions,list) or len(decisions)!=len(set(decisions)) or "BLOCKED" not in decisions:
        raise ControlLoopError("POLICY_DECISIONS_INVALID")
    delegation=p.get("delegation")
    if not isinstance(delegation,dict) or set(delegation)!=set(decisions):
        raise ControlLoopError("POLICY_DELEGATION_INVALID")
    paths,blobs=p.get("anchor_paths"),p.get("anchor_blobs")
    if not isinstance(paths,dict) or not isinstance(blobs,dict) or set(paths)!=set(blobs):
        raise ControlLoopError("POLICY_ANCHOR_MAP_INVALID")
    for k in FALSE_AUTHORITIES:
        if p.get(k) is not False: raise ControlLoopError("POLICY_AUTHORITY_PRESENT:"+k)

def validate_anchor_map(p,*,root=ROOT,blob_reader=git_blob_sha_path):
    for k,rel in sorted(p["anchor_paths"].items()):
        path=root/rel
        if not path.is_file(): raise ControlLoopError("ANCHOR_MISSING:"+k)
        if blob_reader(path)!=p["anchor_blobs"][k]: raise ControlLoopError("ANCHOR_DRIFT:"+k)

def _out(decision,p,*,reasons=None,selected=None,ci_decision=None,execution=None):
    return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION",
            "state":"PLAN_ONLY_CONTROL_LOOP_BLOCKED" if decision=="BLOCKED" else "PLAN_ONLY_CONTROL_LOOP_PASS",
            "decision":decision,"reasons":reasons or [],"delegated_authority":p["delegation"][decision],
            "selected_work_unit_id":None if not selected else selected.get("work_unit_id"),
            "selected_issue_number":None if not selected else selected.get("issue"),
            "ci_decision":ci_decision,"execution_state":execution,
            "provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,
            "pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,
            "merge_performed":False,"runtime_action_performed":False,"product_runtime_mutation_performed":False,
            "next_boundary":p["next_boundary"]}

def _sha(value,field):
    if not isinstance(value,str) or SHA40.fullmatch(value) is None: raise ControlLoopError("SHA_INVALID:"+field)
    return value

def _no_mutation(component,prefix,fields):
    for field in fields:
        if component.get(field) is not False: raise ControlLoopError(prefix+"_MUTATION_REPORTED:"+field)

def _validate_continuation(c,p,current_main):
    if not isinstance(c,dict) or c.get("schema_version")!=1 or c.get("role")!=p["continuation_role"]:
        raise ControlLoopError("CONTINUATION_IDENTITY_INVALID")
    _no_mutation(c,"CONTINUATION",("provider_mutation_performed","issue_mutation_performed","writer_lease_mutation_performed","merge_performed","runtime_action_performed"))
    decision=c.get("decision")
    if decision not in {"CONTINUE_SELECTED_WORK_UNIT","PLAN_MATERIALIZATION","WAITING_RUNTIME","NO_FRONTIER","BLOCKED"}:
        raise ControlLoopError("CONTINUATION_DECISION_INVALID")
    if decision=="CONTINUE_SELECTED_WORK_UNIT":
        selected=c.get("selected")
        if not isinstance(selected,dict) or selected.get("classification")!="EXECUTABLE_READ_ONLY_SELECTION":
            raise ControlLoopError("SELECTED_WORK_UNIT_INVALID")
        if selected.get("runtime_required") is not False: raise ControlLoopError("SELECTED_RUNTIME_REQUIRED")
        if selected.get("base_sha")!=current_main: raise ControlLoopError("SELECTED_BASE_MAIN_MISMATCH")
        if not isinstance(selected.get("issue"),int) or isinstance(selected.get("issue"),bool) or selected["issue"]<1:
            raise ControlLoopError("SELECTED_ISSUE_INVALID")
        if not isinstance(selected.get("work_unit_id"),str) or not selected["work_unit_id"]:
            raise ControlLoopError("SELECTED_WORK_UNIT_ID_INVALID")
        return decision,selected
    if c.get("selected") is not None: raise ControlLoopError("UNEXPECTED_SELECTED_WORK_UNIT")
    return decision,None

def _post_merge_stale_selected(c,current_main):
    if c.get("decision")!="BLOCKED": raise ControlLoopError("POST_MERGE_CONTINUATION_NOT_BLOCKED")
    selector=c.get("selector_result")
    if not isinstance(selector,dict) or selector.get("schema_version")!=2 or selector.get("state")!="READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS":
        raise ControlLoopError("POST_MERGE_SELECTOR_RESULT_INVALID")
    if selector.get("provider_mutation_performed") is not False: raise ControlLoopError("POST_MERGE_SELECTOR_MUTATION_REPORTED")
    if selector.get("decision")!="NO_EXECUTABLE_WORK_UNIT" or selector.get("orchestration_disposition")!="BLOCKED":
        raise ControlLoopError("POST_MERGE_SELECTOR_DISPOSITION_INVALID")
    canonical=selector.get("canonical_work_units")
    if not isinstance(canonical,list): raise ControlLoopError("POST_MERGE_CANONICAL_LIST_REQUIRED")
    nonterminal=[x for x in canonical if isinstance(x,dict) and x.get("classification")!="TERMINAL"]
    if len(nonterminal)!=1: raise ControlLoopError("POST_MERGE_EXACT_SINGLE_NONTERMINAL_REQUIRED")
    selected=nonterminal[0]
    if selected.get("classification")!="STALE_BASE" or selected.get("reason")!="BASE_DOES_NOT_MATCH_DEFAULT_HEAD":
        raise ControlLoopError("POST_MERGE_EXACT_STALE_BASE_REQUIRED")
    if selected.get("runtime_required") is not False or selected.get("base_sha")==current_main:
        raise ControlLoopError("POST_MERGE_STALE_BASE_BINDING_INVALID")
    if not isinstance(selected.get("issue"),int) or isinstance(selected.get("issue"),bool) or selected["issue"]<1:
        raise ControlLoopError("POST_MERGE_ISSUE_INVALID")
    if not isinstance(selected.get("work_unit_id"),str) or not selected["work_unit_id"]:
        raise ControlLoopError("POST_MERGE_WORK_UNIT_ID_INVALID")
    return selected

def _validate_ci(ci,p,pr_number,pr_head):
    if not isinstance(ci,dict) or ci.get("schema_version")!=1 or ci.get("role")!=p["ci_role"]:
        raise ControlLoopError("CI_IDENTITY_INVALID")
    _no_mutation(ci,"CI",("provider_mutation_performed","workflow_rerun_performed","branch_mutation_performed",
                           "pull_request_mutation_performed","writer_lease_mutation_performed","merge_performed",
                           "runtime_action_performed","product_runtime_mutation_performed"))
    decision=ci.get("decision")
    if decision not in {"CI_SUCCESS","CI_PENDING","HARNESS_OR_VALIDATION_DEFECT_CANDIDATE",
                        "PRODUCT_RUNTIME_DEFECT_CANDIDATE","PROVIDER_ENVIRONMENT_AMBIGUITY","BLOCKED"}:
        raise ControlLoopError("CI_DECISION_INVALID")
    if ci.get("pr_number")!=pr_number or ci.get("pr_head_sha")!=pr_head:
        raise ControlLoopError("CI_PR_BINDING_MISMATCH")
    return decision

def _validate_execution(e,selected):
    if not isinstance(e,dict): raise ControlLoopError("EXECUTION_STATE_REQUIRED")
    if e.get("work_unit_id")!=selected["work_unit_id"] or e.get("issue_number")!=selected["issue"]:
        raise ControlLoopError("EXECUTION_SELECTED_BINDING_MISMATCH")
    if e.get("issue_open") is not True: raise ControlLoopError("SELECTED_ISSUE_NOT_OPEN")
    lease=e.get("lease_state")
    if lease not in {"NONE","ACTIVE","RELEASED"}: raise ControlLoopError("LEASE_STATE_INVALID")
    exact=e.get("lease_exact_binding")
    if lease=="NONE":
        if exact is not False: raise ControlLoopError("LEASE_NONE_BINDING_FLAG_INVALID")
    elif exact is not True: raise ControlLoopError("LEASE_EXACT_BINDING_REQUIRED")
    branch_exists=e.get("branch_exists")
    if not isinstance(branch_exists,bool): raise ControlLoopError("BRANCH_EXISTS_BOOLEAN_REQUIRED")
    return lease,branch_exists

def evaluate_control_loop(s,*,policy=None,root=ROOT,check_anchors=True,blob_reader=git_blob_sha_path):
    p=policy or load_json(POLICY_PATH)
    try:
        validate_policy(p)
        if check_anchors: validate_anchor_map(p,root=root,blob_reader=blob_reader)
        if not isinstance(s,dict) or s.get("schema_version")!=1 or s.get("role")!=p["snapshot_role"]:
            raise ControlLoopError("SNAPSHOT_IDENTITY_INVALID")
        if s.get("repository")!=p["repository"] or s.get("default_branch")!=p["default_branch"]:
            raise ControlLoopError("PROVIDER_IDENTITY_MISMATCH")
        if s.get("provider_truth_fresh") is not True: raise ControlLoopError("PROVIDER_TRUTH_NOT_FRESH")
        current_main=_sha(s.get("current_main_sha"),"current_main_sha")
        c=s.get("continuation_decision")
        cdecision,selected=_validate_continuation(c,p,current_main)

        if cdecision=="BLOCKED":
            e=s.get("execution_state")
            if not isinstance(e,dict) or e.get("post_merge_recovery") is not True:
                return _out("BLOCKED",p,reasons=["CONTINUATION_BLOCKED"])
            selected=_post_merge_stale_selected(c,current_main)
            lease,branch_exists=_validate_execution(e,selected)
            if lease!="RELEASED" or not branch_exists: raise ControlLoopError("POST_MERGE_RELEASED_LEASE_AND_BRANCH_REQUIRED")
            branch=e.get("branch_name"); branch_head=e.get("branch_head_sha")
            if not isinstance(branch,str) or not branch.startswith("agent/"+selected["work_unit_id"]+"-") or branch=="main":
                raise ControlLoopError("POST_MERGE_WORK_UNIT_BRANCH_INVALID")
            _sha(branch_head,"branch_head_sha")
            pr=e.get("pull_request")
            if not isinstance(pr,dict) or pr.get("state")!="MERGED": raise ControlLoopError("POST_MERGE_PR_STATE_INVALID")
            if pr.get("head_sha")!=branch_head or pr.get("base_sha")!=selected.get("base_sha"):
                raise ControlLoopError("POST_MERGE_PR_BRANCH_BASE_BINDING_INVALID")
            merge_sha=_sha(pr.get("merge_commit_sha"),"merge_commit_sha")
            if merge_sha!=current_main: raise ControlLoopError("POST_MERGE_MAIN_READBACK_MISMATCH")
            return _out("PLAN_EXISTING_MERGE_CLOSE_AUTHORITY_PATH",p,selected=selected,execution=e)
        if cdecision=="PLAN_MATERIALIZATION": return _out("PLAN_EXISTING_MATERIALIZATION_TRANSACTION",p)
        if cdecision=="WAITING_RUNTIME": return _out("WAIT_FOR_PRIVATE_RUNTIME",p)
        if cdecision=="NO_FRONTIER": return _out("STOP_NO_FRONTIER",p)

        e=s.get("execution_state")
        lease,branch_exists=_validate_execution(e,selected)
        branch=e.get("branch_name"); branch_head=e.get("branch_head_sha"); pr=e.get("pull_request")
        if not branch_exists:
            if branch is not None or branch_head is not None: raise ControlLoopError("ABSENT_BRANCH_FIELDS_PRESENT")
            if pr is not None: raise ControlLoopError("PR_WITHOUT_BRANCH")
            if lease=="NONE": return _out("PLAN_EXISTING_WRITER_LEASE_ACQUISITION",p,selected=selected,execution=e)
            if lease=="ACTIVE": return _out("PLAN_EXISTING_BOUNDED_BRANCH_CREATE",p,selected=selected,execution=e)
            raise ControlLoopError("RELEASED_LEASE_WITHOUT_BRANCH")
        if not isinstance(branch,str) or not branch.startswith("agent/"+selected["work_unit_id"]+"-") or branch=="main":
            raise ControlLoopError("WORK_UNIT_BRANCH_INVALID")
        _sha(branch_head,"branch_head_sha")
        if lease=="NONE": raise ControlLoopError("BRANCH_WITHOUT_LEASE")
        if pr is None:
            if lease!="ACTIVE": raise ControlLoopError("RELEASED_LEASE_WITHOUT_PR")
            decision="CONTINUE_EXISTING_BOUNDED_BRANCH" if branch_head==current_main else "PLAN_EXISTING_PULL_REQUEST_CREATE"
            return _out(decision,p,selected=selected,execution=e)
        if not isinstance(pr,dict): raise ControlLoopError("PULL_REQUEST_OBJECT_REQUIRED")
        number=pr.get("number")
        if not isinstance(number,int) or isinstance(number,bool) or number<1: raise ControlLoopError("PR_NUMBER_INVALID")
        if pr.get("state")!="OPEN": raise ControlLoopError("PR_STATE_INVALID")
        if pr.get("base_sha")!=current_main: raise ControlLoopError("PR_BASE_MAIN_MISMATCH")
        if pr.get("head_sha")!=branch_head: raise ControlLoopError("PR_HEAD_BRANCH_MISMATCH")
        ci_decision=_validate_ci(s.get("ci_decision"),p,number,branch_head)
        if ci_decision=="BLOCKED": return _out("BLOCKED",p,reasons=["CI_BLOCKED"],selected=selected,ci_decision=ci_decision,execution=e)
        if ci_decision=="CI_PENDING": return _out("WAIT_FOR_EXACT_HEAD_CI",p,selected=selected,ci_decision=ci_decision,execution=e)
        if ci_decision in {"HARNESS_OR_VALIDATION_DEFECT_CANDIDATE","PRODUCT_RUNTIME_DEFECT_CANDIDATE","PROVIDER_ENVIRONMENT_AMBIGUITY"}:
            return _out("PLAN_CLASSIFIED_FAILURE_RECOVERY",p,selected=selected,ci_decision=ci_decision,execution=e)
        if ci_decision!="CI_SUCCESS": raise ControlLoopError("CI_DECISION_UNHANDLED")
        if lease=="ACTIVE": return _out("PLAN_EXISTING_WRITER_LEASE_RELEASE",p,selected=selected,ci_decision=ci_decision,execution=e)
        return _out("PLAN_EXISTING_MERGE_CLOSE_AUTHORITY_PATH",p,selected=selected,ci_decision=ci_decision,execution=e)
    except (ControlLoopError,KeyError,TypeError) as e:
        try: return _out("BLOCKED",p,reasons=[str(e)])
        except Exception:
            return {"schema_version":1,"role":"AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION","state":"PLAN_ONLY_CONTROL_LOOP_BLOCKED","decision":"BLOCKED","reasons":[str(e)],"delegated_authority":None,"provider_mutation_performed":False,"issue_mutation_performed":False,"branch_mutation_performed":False,"pull_request_mutation_performed":False,"writer_lease_mutation_performed":False,"workflow_rerun_performed":False,"merge_performed":False,"runtime_action_performed":False,"product_runtime_mutation_performed":False,"next_boundary":None}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--policy",default=str(POLICY_PATH)); a=ap.parse_args()
    p=load_json(a.policy); r=evaluate_control_loop(load_json(a.input),policy=p); print(json.dumps(r,indent=2,sort_keys=True))
    return 2 if r["decision"]=="BLOCKED" else 0

if __name__=="__main__": raise SystemExit(main())
