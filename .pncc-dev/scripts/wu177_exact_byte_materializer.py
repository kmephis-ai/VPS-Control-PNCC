#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, re, subprocess, sys, time, urllib.error, urllib.request

REPO = "kmephis-ai/VPS-Control-PNCC"
ISSUE = 399
WU = "PIPE-WU-175"
BRANCH = "agent/PIPE-WU-175-v702-activation-wu172-fix"
WU172_PR = 394
WU172_PATH = "src/windows-v7/modules/V7-StatusCenter.ps1"
WU172_BLOB = "6c4a8ddcaea7f4c651b6d4be74d925358d81f3c5"
MAIN_PATH = "src/windows-v7/VPS-Control-v7.ps1"
HISTORICAL_MAIN_BLOB = "44f7e6433881733f4aa5ca251e33bc3e2cd98988"
ROOT = "src/windows-v7"
MANIFEST = "src/windows-v7/VPS-Control-v7-SHA256.txt"
CANDIDATE = ".pncc-dev/candidate-source.json"
RECIPE = "build/windows-v7-candidate-recipe.json"
PROVENANCE = ".pncc-dev/provenance/canonical-source-v7.0.2-patch.json"
OLD_PROVENANCE = ".pncc-dev/provenance/canonical-source-v7.0.1-patch.json"
MARKER = "PNCC-EXACT-BYTE-MATERIALIZER-REQUEST"
POSTWRITE_READBACK_ATTEMPTS = 6
POSTWRITE_READBACK_DELAY_SECONDS = 1

class Blocked(RuntimeError): pass

def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def run(*args, input_bytes=None):
    p = subprocess.run(args, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise Blocked(f"COMMAND_FAILED:{' '.join(args)}:{p.stderr.decode(errors='replace')[-500:]}")
    return p.stdout

def git_object_bytes(commit_sha, path):
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha): raise Blocked("GIT_OBJECT_COMMIT_SHA_INVALID")
    if path.startswith("/") or ".." in path.split("/"): raise Blocked("GIT_OBJECT_PATH_INVALID")
    return run("git", "show", f"{commit_sha}:{path}")

def git_object_bytes_optional(commit_sha, path):
    try:
        return git_object_bytes(commit_sha, path)
    except Blocked as e:
        if path == PROVENANCE and "COMMAND_FAILED:git show" in str(e): return None
        raise

def tracked_source_paths(base):
    raw = run("git", "ls-tree", "-r", "--name-only", base, "--", ROOT).decode("utf-8")
    paths = sorted(x.strip() for x in raw.splitlines() if x.strip())
    if not paths: raise Blocked("CANONICAL_SOURCE_TREE_EMPTY")
    if MANIFEST not in paths: raise Blocked("CANONICAL_MANIFEST_NOT_TRACKED")
    return paths

def load_json_object(base, path):
    try: return json.loads(git_object_bytes(base, path).decode("utf-8-sig"))
    except Exception as e: raise Blocked(f"BASE_JSON_INVALID:{path}:{e}")

def api(path, token, method="GET", payload=None):
    url = "https://api.github.com" + path
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "pncc-wu177-materializer"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise Blocked(f"GITHUB_HTTP_{e.code}:{path}:{body[:500]}")

def parse_request(body):
    lines = [x.strip() for x in body.splitlines() if MARKER in x]
    if len(lines) != 1: raise Blocked("REQUEST_MARKER_COUNT")
    m = re.search(r"<!--\s*" + MARKER + r"\s+(\{.*\})\s*-->", lines[0])
    if not m: raise Blocked("REQUEST_MARKER_FORMAT")
    try: obj = json.loads(m.group(1))
    except Exception: raise Blocked("REQUEST_JSON_INVALID")
    allowed = {"schema_version","action","work_unit","branch","base_sha","expected_head_sha","plan_sha256","paths"}
    if set(obj) - allowed: raise Blocked("REQUEST_UNKNOWN_FIELDS")
    if obj.get("schema_version") != 1 or obj.get("work_unit") != WU or obj.get("branch") != BRANCH:
        raise Blocked("REQUEST_SCOPE_MISMATCH")
    if obj.get("action") not in ("PLAN","EXECUTE","REPAIR_PLAN","REPAIR_EXECUTE"): raise Blocked("REQUEST_ACTION")
    for k in ("base_sha","expected_head_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(obj.get(k,""))): raise Blocked("REQUEST_SHA")
    if obj["branch"] == "main": raise Blocked("DEFAULT_BRANCH_FORBIDDEN")
    return obj

def checkout_clean():
    if run("git","status","--porcelain").strip(): raise Blocked("DIRTY_CHECKOUT")

def checkout_exact(base):
    if run("git","rev-parse","HEAD").decode().strip() != base: raise Blocked("CHECKOUT_NOT_EXACT_BASE")
    checkout_clean()

def get_pr_file_bytes():
    run("git","fetch","--no-tags","origin",f"refs/pull/{WU172_PR}/head")
    data = run("git","show",f"FETCH_HEAD:{WU172_PATH}")
    if git_blob_sha(data) != WU172_BLOB: raise Blocked("WU172_BLOB_MISMATCH")
    return data

def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

def assemble(base):
    changes = {}
    source_paths = tracked_source_paths(base)
    base_bytes = {p: git_object_bytes(base, p) for p in source_paths}
    wu172 = get_pr_file_bytes()
    for rel in source_paths:
        if rel == MANIFEST: continue
        original = base_bytes[rel]
        data = wu172 if rel == WU172_PATH else original
        data = data.replace(b"7.0.1", b"7.0.2")
        if b"7.0.1" in data: raise Blocked(f"RESIDUAL_7_0_1:{rel}")
        if data != original: changes[rel] = data
    if MAIN_PATH not in changes: raise Blocked("MAIN_SCRIPT_NOT_CHANGED")
    if WU172_PATH not in changes or git_blob_sha(changes[WU172_PATH]) != WU172_BLOB:
        raise Blocked("WU172_TARGET_BLOB_MISMATCH")
    rows=[]; inventory=[]
    for rel in source_paths:
        if rel == MANIFEST: continue
        relroot = rel[len(ROOT)+1:]
        data = changes.get(rel, base_bytes[rel])
        rows.append(f"{sha256(data)}  {relroot.replace('/', chr(92))}")
        inventory.append({"bytes":len(data),"path":relroot,"sha256":sha256(data)})
    manifest=("# VPS Control Center v7.0.2 deterministic canonical Git-blob source manifest\n"+"\n".join(rows)+"\n").encode()
    changes[MANIFEST]=manifest
    inventory.append({"bytes":len(manifest),"path":"VPS-Control-v7-SHA256.txt","sha256":sha256(manifest)})
    inventory.sort(key=lambda x:x["path"])
    candidate=load_json_object(base,CANDIDATE)
    candidate["candidate_version"]="7.0.2"; candidate["provenance_path"]=PROVENANCE
    candidate["runtime_authority"]=False; candidate["promotion_authority"]=False
    changes[CANDIDATE]=json_bytes(candidate)
    recipe=load_json_object(base,RECIPE)
    recipe["candidate_version"]="7.0.2"; recipe["output_filename"]="VPS-Control-v7.0.2.zip"
    recipe["runtime_authority"]=False; recipe["promotion_authority"]=False
    changes[RECIPE]=json_bytes(recipe)
    load_json_object(base,OLD_PROVENANCE)
    prov={
      "activation":{"builder_introduced":True,"candidate_artifact_generated":False,"exact_base_main_sha":base,"work_unit":WU},
      "baseline":{"activated_candidate_version":"7.0.2","embedded_version":"7.0.2","previous_runtime_version":"7.0.1","remediated_files":["modules/V7-StatusCenter.ps1"],"remediated_file_git_blob_sha":{"modules/V7-StatusCenter.ps1":WU172_BLOB},"remediation_class":"PRODUCT_DEFECT_STATUS_CENTER_RESERVE_ROUTING_CONTROL_STATE_CONSISTENCY","requires_version_bump_before_build":False},
      "hash_semantics":"CANONICAL_GIT_BLOB_BYTES","inventory":inventory,
      "parent":{"previous_release_version":"7.0.1","previous_provenance_path":OLD_PROVENANCE},
      "provenance_id":"PNCC_CANONICAL_SOURCE_V7_0_2_PATCH_V1",
      "safety":{"artifact_exists":False,"build_authority":False,"build_input_ready":True,"ci_is_runtime_truth":False,"promotion_authority":False,"runtime_authority":False,"stable_done":False},
      "schema_version":3,"source_identity_semantic":"UNBUILT_V7_0_2_PATCH_SOURCE_BASELINE","source_root":ROOT}
    changes[PROVENANCE]=json_bytes(prov)
    filtered={}
    for p,d in changes.items():
        before=git_object_bytes_optional(base,p)
        if before != d: filtered[p]=d
    return filtered

def make_plan(base, expected_head, changes, mode):
    if not changes: raise Blocked("EMPTY_PLAN")
    paths=[{"path":p,"git_blob_sha":git_blob_sha(d),"bytes":len(d),"sha256":sha256(d)} for p,d in sorted(changes.items())]
    obj={"schema_version":1,"mode":mode,"work_unit":WU,"branch":BRANCH,"base_sha":base,"expected_head_sha":expected_head,"paths":paths}
    canonical=json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return obj,sha256(canonical)

def plan(base, expected_head):
    changes=assemble(base)
    obj,ph=make_plan(base,expected_head,changes,"FULL")
    return obj,ph,changes

def repair_plan(base, expected_head):
    desired=assemble(base)
    delta={}
    for p,d in desired.items():
        current=git_object_bytes(expected_head,p)
        if current != d: delta[p]=d
    obj,ph=make_plan(base,expected_head,delta,"REPAIR_DELTA")
    return obj,ph,delta

def verify_execute_request(req, obj, ph):
    if req.get("plan_sha256") != ph: raise Blocked("PLAN_SHA_MISMATCH")
    requested=req.get("paths")
    if not isinstance(requested,list): raise Blocked("PATH_ALLOWLIST_MISSING")
    compact=[{"path":x["path"],"git_blob_sha":x["git_blob_sha"]} for x in obj["paths"]]
    if requested != compact: raise Blocked("PATH_ALLOWLIST_MISMATCH")
    for x in requested:
        if not str(x["path"]).startswith(("src/windows-v7/",".pncc-dev/","build/")): raise Blocked("PATH_OUTSIDE_WU175")

def read_ref_until(token, expected_sha, attempts=POSTWRITE_READBACK_ATTEMPTS, delay=POSTWRITE_READBACK_DELAY_SECONDS):
    seen=[]
    for i in range(attempts):
        rbref=api(f"/repos/{REPO}/git/ref/heads/{BRANCH}",token)
        actual=rbref["object"]["sha"]
        seen.append(actual)
        if actual == expected_sha: return actual
        if i + 1 < attempts: time.sleep(delay)
    raise Blocked("POSTWRITE_REF_MISMATCH:"+",".join(seen))

def execute_common(req, obj, ph, changes, token, require_head_equals_base):
    verify_execute_request(req,obj,ph)
    branch_ref=api(f"/repos/{REPO}/git/ref/heads/{BRANCH}",token)
    current=branch_ref["object"]["sha"]
    if current != req["expected_head_sha"]: raise Blocked("BRANCH_HEAD_MOVED")
    if require_head_equals_base and current != req["base_sha"]: raise Blocked("EXECUTE_REQUIRES_UNMUTATED_EXACT_BASE")
    base_commit=api(f"/repos/{REPO}/git/commits/{current}",token)
    tree_entries=[]
    for item in obj["paths"]:
        data=changes[item["path"]]
        created=api(f"/repos/{REPO}/git/blobs",token,"POST",{"content":base64.b64encode(data).decode(),"encoding":"base64"})
        if created["sha"] != item["git_blob_sha"]: raise Blocked("CREATED_BLOB_SHA_MISMATCH")
        rb=api(f"/repos/{REPO}/git/blobs/{created['sha']}",token)
        rbdata=base64.b64decode(rb["content"].replace("\n",""))
        if rbdata != data or git_blob_sha(rbdata) != created["sha"]: raise Blocked("IMMUTABLE_BLOB_READBACK_MISMATCH")
        tree_entries.append({"path":item["path"],"mode":"100644","type":"blob","sha":created["sha"]})
    tree=api(f"/repos/{REPO}/git/trees",token,"POST",{"base_tree":base_commit["tree"]["sha"],"tree":tree_entries})
    message="PIPE-WU-175 repair canonical v7.0.2 evidence" if obj["mode"]=="REPAIR_DELTA" else "PIPE-WU-175 materialize exact v7.0.2 assembly"
    commit=api(f"/repos/{REPO}/git/commits",token,"POST",{"message":message,"tree":tree["sha"],"parents":[current]})
    api(f"/repos/{REPO}/git/refs/heads/{BRANCH}",token,"PATCH",{"sha":commit["sha"],"force":False})
    read_ref_until(token,commit["sha"])
    print(f"MATERIALIZER_EXECUTE=SUCCESS\nMODE={obj['mode']}\nCREATED_COMMIT={commit['sha']}\nPLAN_SHA256={ph}")

def emit_plan(obj,ph):
    main_item=next((x for x in obj["paths"] if x["path"] == MAIN_PATH),None)
    print("MATERIALIZER_PLAN=READY")
    print("MODE="+obj["mode"])
    print("PLAN_SHA256="+ph)
    if main_item: print("DERIVED_MAIN_BLOB="+main_item["git_blob_sha"])
    print("HISTORICAL_MAIN_BLOB="+HISTORICAL_MAIN_BLOB)
    print("PLAN_JSON="+json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--issue-number",type=int,required=True); ap.add_argument("--repository",required=True)
    a=ap.parse_args()
    if a.repository != REPO or a.issue_number != ISSUE: raise Blocked("INVOCATION_SCOPE")
    token=os.environ.get("GITHUB_TOKEN","")
    if not token: raise Blocked("TOKEN_MISSING")
    issue=api(f"/repos/{REPO}/issues/{ISSUE}",token)
    req=parse_request(issue["body"] or "")
    action=req["action"]
    if action in ("PLAN","EXECUTE"):
        checkout_exact(req["base_sha"])
        obj,ph,changes=plan(req["base_sha"],req["expected_head_sha"])
    else:
        checkout_clean()
        branch_ref=api(f"/repos/{REPO}/git/ref/heads/{BRANCH}",token)
        if branch_ref["object"]["sha"] != req["expected_head_sha"]: raise Blocked("REPAIR_EXPECTED_HEAD_MISMATCH")
        obj,ph,changes=repair_plan(req["base_sha"],req["expected_head_sha"])
    if action in ("PLAN","REPAIR_PLAN"):
        emit_plan(obj,ph); return
    execute_common(req,obj,ph,changes,token,require_head_equals_base=(action=="EXECUTE"))

if __name__ == "__main__":
    try: main()
    except Blocked as e:
        print("MATERIALIZER=BLOCKED"); print("ERROR="+str(e)); sys.exit(2)
