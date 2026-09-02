#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import argparse
import importlib.util
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
REPO = "kmephis-ai/VPS-Control-PNCC"
STATE_BRANCH = "pncc-provider-state"
REGISTRY_PATH = ".pncc-state/writer-lease-registry.json"
CONTRACT_PATH = ROOT / ".pncc-dev/contracts/wave6-wu149-writer-lease-cas-executor.json"
GRANT_PATH = ROOT / ".pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json"
WORK_UNIT_RE = re.compile(r"<!--\s*PNCC-WORK-UNIT(?P<attrs>.*?)-->", re.I | re.S)
REQUEST_RE = re.compile(r"<!--\s*PNCC-LEASE-CAS-REQUEST(?P<attrs>.*?)-->", re.I | re.S)
SHA40 = re.compile(r"^[0-9a-f]{40}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
ALLOWED_ACTIONS = {"ACQUIRE", "RELEASE"}
HOLDER = "chatgpt-wave5-writer"
LEASE_SECONDS = 3600

class ExecutorError(RuntimeError):
    pass

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def git_blob_sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def parse_attrs(raw: str, required: set[str], optional: set[str] | None = None) -> dict[str,str]:
    optional = optional or set()
    attrs: dict[str,str] = {}
    for token in raw.strip().split():
        if "=" not in token:
            raise ExecutorError("MARKER_TOKEN_INVALID")
        k,v = token.split("=",1)
        k=k.strip().lower(); v=v.strip()
        if not k or not v or k in attrs:
            raise ExecutorError("MARKER_ATTR_INVALID_OR_DUPLICATE")
        attrs[k]=v
    if set(attrs) - required - optional:
        raise ExecutorError("MARKER_UNKNOWN_ATTR")
    if required - set(attrs):
        raise ExecutorError("MARKER_MISSING_ATTR")
    return attrs

def parse_work_unit(body: str) -> dict[str,Any]:
    matches=list(WORK_UNIT_RE.finditer(body or ""))
    if len(matches)!=1:
        raise ExecutorError("WORK_UNIT_MARKER_COUNT")
    a=parse_attrs(matches[0].group("attrs"),
        {"schema","id","state","conflict_domain","base","runtime_required"},
        {"branch"})
    if a["schema"]!="1" or a["state"].upper() not in {"READY","ACTIVE"}:
        raise ExecutorError("WORK_UNIT_NOT_EXECUTABLE")
    if not SHA40.fullmatch(a["base"]):
        raise ExecutorError("WORK_UNIT_BASE_INVALID")
    if a["runtime_required"].lower()!="false":
        raise ExecutorError("RUNTIME_REQUIRED_FORBIDDEN")
    branch=a.get("branch")
    if not branch or branch=="main":
        raise ExecutorError("BOUNDED_NON_MAIN_BRANCH_REQUIRED")
    return {
        "work_unit_id":a["id"], "conflict_domain":a["conflict_domain"],
        "base_sha":a["base"], "branch":branch, "runtime_required":False,
    }

def parse_request(body: str) -> dict[str,str]:
    matches=list(REQUEST_RE.finditer(body or ""))
    if len(matches)!=1:
        raise ExecutorError("REQUEST_MARKER_COUNT")
    a=parse_attrs(matches[0].group("attrs"),
        {"schema","action","request_id","lease_id","expected_state_head","expected_registry_blob"})
    if a["schema"]!="1":
        raise ExecutorError("REQUEST_SCHEMA_INVALID")
    action=a["action"].upper()
    if action not in ALLOWED_ACTIONS:
        raise ExecutorError("REQUEST_ACTION_INVALID")
    if not UUID_RE.fullmatch(a["request_id"]) or not UUID_RE.fullmatch(a["lease_id"]):
        raise ExecutorError("REQUEST_UUID_INVALID")
    if not SHA40.fullmatch(a["expected_state_head"]) or not SHA40.fullmatch(a["expected_registry_blob"]):
        raise ExecutorError("REQUEST_CAS_INVALID")
    a["action"]=action
    return a

def parse_time(value: str, name: str) -> datetime:
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except Exception as exc:
        raise ExecutorError("TIMESTAMP_INVALID:"+name) from exc
    if d.tzinfo is None:
        raise ExecutorError("TIMESTAMP_TZ_REQUIRED:"+name)
    return d.astimezone(timezone.utc)

def fmt_time(d: datetime) -> str:
    return d.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def _validate_registry_shape(registry: Any) -> None:
    if not isinstance(registry,dict) or registry.get("schema_version")!=1 or registry.get("role")!="WRITER_LEASE_REGISTRY":
        raise ExecutorError("REGISTRY_IDENTITY_INVALID")
    if not isinstance(registry.get("generation"),int) or isinstance(registry.get("generation"),bool) or registry["generation"]<0:
        raise ExecutorError("REGISTRY_GENERATION_INVALID")
    if not isinstance(registry.get("entries"),list):
        raise ExecutorError("REGISTRY_ENTRIES_INVALID")
    ids=set()
    for x in registry["entries"]:
        if not isinstance(x,dict):
            raise ExecutorError("LEASE_ENTRY_INVALID")
        lid=x.get("lease_id")
        if not isinstance(lid,str) or lid in ids:
            raise ExecutorError("LEASE_ID_INVALID_OR_DUPLICATE")
        ids.add(lid)

def build_acquire_registry(registry: dict[str,Any], wu: dict[str,Any], req: dict[str,str], now: datetime) -> dict[str,Any]:
    _validate_registry_shape(registry)
    if req["action"]!="ACQUIRE":
        raise ExecutorError("ACTION_NOT_ACQUIRE")
    if any(x.get("lease_id")==req["lease_id"] for x in registry["entries"]):
        raise ExecutorError("LEASE_ID_ALREADY_EXISTS")
    for x in registry["entries"]:
        if x.get("state")!="ACTIVE":
            continue
        exp=parse_time(str(x.get("expires_at","")), "lease.expires_at")
        if exp <= now:
            continue
        if x.get("conflict_domain")==wu["conflict_domain"] or x.get("work_unit_id")==wu["work_unit_id"]:
            raise ExecutorError("ACTIVE_UNEXPIRED_CONFLICT")
    out=deepcopy(registry)
    new_generation=registry["generation"]+1
    acquired=fmt_time(now)
    out["generation"]=new_generation
    out["entries"].append({
        "schema_version":1, "role":"WRITER_LEASE", "lease_id":req["lease_id"],
        "work_unit_id":wu["work_unit_id"], "conflict_domain":wu["conflict_domain"],
        "holder":HOLDER, "base_sha":wu["base_sha"], "branch":wu["branch"],
        "state":"ACTIVE", "generation":new_generation, "acquired_at":acquired,
        "heartbeat_at":acquired, "expires_at":fmt_time(now+timedelta(seconds=LEASE_SECONDS)),
    })
    if out["entries"][:-1] != registry["entries"]:
        raise ExecutorError("HISTORICAL_ENTRY_DRIFT")
    return out

def build_release_registry(registry: dict[str,Any], wu: dict[str,Any], req: dict[str,str], now: datetime) -> dict[str,Any]:
    _validate_registry_shape(registry)
    if req["action"]!="RELEASE":
        raise ExecutorError("ACTION_NOT_RELEASE")
    matches=[(i,x) for i,x in enumerate(registry["entries"]) if x.get("lease_id")==req["lease_id"]]
    if len(matches)!=1:
        raise ExecutorError("RELEASE_LEASE_NOT_UNIQUE")
    idx,lease=matches[0]
    expected={
        "work_unit_id":wu["work_unit_id"], "conflict_domain":wu["conflict_domain"],
        "holder":HOLDER, "base_sha":wu["base_sha"], "branch":wu["branch"], "state":"ACTIVE"
    }
    if any(lease.get(k)!=v for k,v in expected.items()):
        raise ExecutorError("RELEASE_BINDING_MISMATCH")
    if parse_time(str(lease.get("expires_at","")), "lease.expires_at") <= now:
        raise ExecutorError("RELEASE_EXPIRED_LEASE_FORBIDDEN")
    out=deepcopy(registry)
    out["entries"][idx]["state"]="RELEASED"
    for i,(old,new) in enumerate(zip(registry["entries"],out["entries"])):
        if i==idx:
            allowed=dict(old); allowed["state"]="RELEASED"
            if new!=allowed:
                raise ExecutorError("RELEASE_MUTATED_EXTRA_FIELDS")
        elif new!=old:
            raise ExecutorError("HISTORICAL_ENTRY_DRIFT")
    if out["generation"]!=registry["generation"]:
        raise ExecutorError("RELEASE_GENERATION_DRIFT")
    return out

def validate_contract_and_anchors() -> None:
    c=load_json(CONTRACT_PATH)
    if c.get("role")!="WRITER_LEASE_CAS_EXECUTOR_WU149":
        raise ExecutorError("EXECUTOR_CONTRACT_INVALID")
    if git_blob_sha(GRANT_PATH.read_bytes()) != c["authority_source"]["blob_sha"]:
        raise ExecutorError("GRANT_BLOB_DRIFT")
    mapping={
      ".pncc-dev/contracts/writer-lease-lifecycle-autonomous-execution-policy.json":"lifecycle_policy",
      ".pncc-dev/contracts/writer-lease-claim-admission-policy.json":"claim_admission_policy",
      ".pncc-dev/contracts/writer-lease-registry-topology.json":"registry_topology",
      ".pncc-dev/scripts/select_provider_work_unit.py":"selector",
      ".pncc-dev/scripts/evaluate_writer_lease_claim_admission.py":"claim_evaluator",
      ".pncc-dev/scripts/evaluate_writer_lease_lifecycle.py":"lifecycle_evaluator",
      ".pncc-dev/scripts/validate_state.py":"state_validator",
    }
    for path,key in mapping.items():
        if git_blob_sha((ROOT/path).read_bytes()) != c["bound_anchor_blobs"][key]:
            raise ExecutorError("ANCHOR_BLOB_DRIFT:"+key)
    if any(c["authority"].values()):
        raise ExecutorError("EXECUTOR_NEW_AUTHORITY_PRESENT")
    if c["cas"].get("force_ref_update") is not False:
        raise ExecutorError("FORCE_REF_UPDATE_NOT_FORBIDDEN")

def gh(method: str, path: str, token: str, body: Any=None) -> Any:
    url="https://api.github.com/repos/"+REPO+path
    headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
             "Authorization":"Bearer "+token,"User-Agent":"pncc-writer-lease-cas-executor"}
    data=None if body is None else json.dumps(body,separators=(",",":")).encode()
    req=urllib.request.Request(url,headers=headers,data=data,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read()
            return json.loads(raw.decode()) if raw else None
    except urllib.error.HTTPError as exc:
        raise ExecutorError(f"GITHUB_HTTP_{exc.code}:{method}:{path}") from exc
    except (urllib.error.URLError,UnicodeError,json.JSONDecodeError) as exc:
        raise ExecutorError("GITHUB_IO_FAILED:"+type(exc).__name__) from exc

def import_selector():
    p=ROOT/".pncc-dev/scripts/select_provider_work_unit.py"
    spec=importlib.util.spec_from_file_location("pncc_selector",p); m=importlib.util.module_from_spec(spec)
    assert spec.loader; spec.loader.exec_module(m); return m

def import_claim():
    p=ROOT/".pncc-dev/scripts/evaluate_writer_lease_claim_admission.py"
    spec=importlib.util.spec_from_file_location("pncc_claim",p); m=importlib.util.module_from_spec(spec)
    assert spec.loader; spec.loader.exec_module(m); return m

def live_transaction(issue_number: int, token: str, repository_owner: str) -> dict[str,Any]:
    validate_contract_and_anchors()
    issue=gh("GET",f"/issues/{issue_number}",token)
    if issue.get("pull_request") is not None or issue.get("state")!="open":
        raise ExecutorError("CANONICAL_OPEN_ISSUE_REQUIRED")
    if (issue.get("user") or {}).get("login") != repository_owner:
        raise ExecutorError("ISSUE_AUTHOR_NOT_REPOSITORY_OWNER")
    body=issue.get("body") or ""
    wu=parse_work_unit(body); req=parse_request(body)
    main=gh("GET","/git/ref/heads/main",token)["object"]["sha"]
    if main != wu["base_sha"]:
        raise ExecutorError("WORK_UNIT_BASE_NOT_FRESH_MAIN")

    state_ref=gh("GET",f"/git/ref/heads/{STATE_BRANCH}",token)["object"]["sha"]
    if state_ref != req["expected_state_head"]:
        raise ExecutorError("STATE_HEAD_CAS_MISMATCH")
    content=gh("GET",f"/contents/{REGISTRY_PATH}?ref={urllib.parse.quote(STATE_BRANCH,safe='')}",token)
    import base64
    registry_bytes=base64.b64decode(content["content"])
    observed_blob=content["sha"]
    if observed_blob != req["expected_registry_blob"] or git_blob_sha(registry_bytes)!=observed_blob:
        raise ExecutorError("REGISTRY_BLOB_CAS_MISMATCH")
    registry=json.loads(registry_bytes.decode("utf-8"))

    selector=import_selector()
    default_head, issues=selector.fetch_live_provider_truth(REPO,"main",token)
    orchestration=selector.select_from_provider_issues(
        issues,repository=REPO,default_branch="main",default_head_sha=default_head,
        observed_at=fmt_time(datetime.now(timezone.utc)))
    selected=orchestration.get("selected") or {}
    if orchestration.get("decision")!="SELECTED" or selected.get("issue")!=issue_number:
        raise ExecutorError("DETERMINISTIC_SELECTION_MISMATCH")
    for key in ("work_unit_id","conflict_domain","base_sha","branch"):
        if selected.get(key)!=wu[key]:
            raise ExecutorError("SELECTED_WORK_UNIT_BINDING_MISMATCH:"+key)

    now=datetime.now(timezone.utc).replace(microsecond=0)
    if req["action"]=="ACQUIRE":
        claim=import_claim()
        decision=claim.evaluate_claim_admission(
            orchestration,registry["entries"],holder=HOLDER,now_iso=fmt_time(now))
        if decision.get("decision")!="CLAIM_ELIGIBLE":
            raise ExecutorError("CLAIM_NOT_ELIGIBLE")
        new_registry=build_acquire_registry(registry,wu,req,now)
    else:
        new_registry=build_release_registry(registry,wu,req,now)

    state_ref2=gh("GET",f"/git/ref/heads/{STATE_BRANCH}",token)["object"]["sha"]
    content2=gh("GET",f"/contents/{REGISTRY_PATH}?ref={urllib.parse.quote(STATE_BRANCH,safe='')}",token)
    if state_ref2!=state_ref or content2["sha"]!=observed_blob:
        raise ExecutorError("PREWRITE_PROVIDER_DRIFT")

    new_bytes=json.dumps(new_registry,separators=(",",":"),ensure_ascii=False).encode()
    blob=gh("POST","/git/blobs",token,{"content":new_bytes.decode(),"encoding":"utf-8"})["sha"]
    if blob != git_blob_sha(new_bytes):
        raise ExecutorError("CREATED_BLOB_IDENTITY_MISMATCH")
    parent=gh("GET",f"/git/commits/{state_ref}",token)
    tree=gh("POST","/git/trees",token,{
        "base_tree":parent["tree"]["sha"],
        "tree":[{"path":REGISTRY_PATH,"mode":"100644","type":"blob","sha":blob}]
    })["sha"]
    commit=gh("POST","/git/commits",token,{
        "message":f"{wu['work_unit_id']} {req['action'].lower()} Writer Lease {req['lease_id']}",
        "tree":tree,"parents":[state_ref]
    })["sha"]
    gh("PATCH",f"/git/refs/heads/{STATE_BRANCH}",token,{"sha":commit,"force":False})

    rb_ref=gh("GET",f"/git/ref/heads/{STATE_BRANCH}",token)["object"]["sha"]
    rb=gh("GET",f"/contents/{REGISTRY_PATH}?ref={urllib.parse.quote(STATE_BRANCH,safe='')}",token)
    if rb_ref!=commit or rb["sha"]!=blob:
        raise ExecutorError("POSTWRITE_READBACK_MISMATCH")
    return {
        "schema_version":1,"role":"WRITER_LEASE_CAS_EXECUTION_RESULT","state":"PASS",
        "action":req["action"],"request_id":req["request_id"],"lease_id":req["lease_id"],
        "work_unit_id":wu["work_unit_id"],"provider_state_head":commit,
        "registry_blob_sha":blob,"registry_generation":new_registry["generation"],
        "force_ref_update":False,"readback":"PASS"
    }

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--issue-number",type=int,required=True)
    ap.add_argument("--repository-owner",required=True)
    args=ap.parse_args()
    if os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise ExecutorError("REPOSITORY_MISMATCH")
    token=os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ExecutorError("GITHUB_TOKEN_REQUIRED")
    result=live_transaction(args.issue_number,token,args.repository_owner)
    print(json.dumps(result,separators=(",",":"),sort_keys=True))
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except ExecutorError as exc:
        print("WRITER_LEASE_CAS_EXECUTOR=BLOCKED")
        print("ERROR="+str(exc))
        raise SystemExit(2)
