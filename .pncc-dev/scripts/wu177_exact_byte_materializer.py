#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, pathlib, re, subprocess, sys, urllib.error, urllib.request

REPO = "kmephis-ai/VPS-Control-PNCC"
ISSUE = 399
WU = "PIPE-WU-175"
BRANCH = "agent/PIPE-WU-175-v702-activation-wu172-fix"
WU172_PR = 394
WU172_PATH = "src/windows-v7/modules/V7-StatusCenter.ps1"
WU172_BLOB = "6c4a8ddcaea7f4c651b6d4be74d925358d81f3c5"
MAIN_PATH = "src/windows-v7/VPS-Control-v7.ps1"
MAIN_BLOB = "44f7e6433881733f4aa5ca251e33bc3e2cd98988"
MANIFEST = "src/windows-v7/VPS-Control-v7-SHA256.txt"
CANDIDATE = ".pncc-dev/candidate-source.json"
RECIPE = "build/windows-v7-candidate-recipe.json"
PROVENANCE = ".pncc-dev/provenance/canonical-source-v7.0.2-patch.json"
OLD_PROVENANCE = ".pncc-dev/provenance/canonical-source-v7.0.1-patch.json"
MARKER = "PNCC-EXACT-BYTE-MATERIALIZER-REQUEST"

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
    if obj.get("action") not in ("PLAN","EXECUTE"): raise Blocked("REQUEST_ACTION")
    for k in ("base_sha","expected_head_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(obj.get(k,""))): raise Blocked("REQUEST_SHA")
    if obj["branch"] == "main": raise Blocked("DEFAULT_BRANCH_FORBIDDEN")
    return obj

def checkout_exact(base):
    if run("git","rev-parse","HEAD").decode().strip() != base: raise Blocked("CHECKOUT_NOT_EXACT_BASE")
    if run("git","status","--porcelain").strip(): raise Blocked("DIRTY_CHECKOUT")

def get_pr_file_bytes():
    run("git","fetch","--no-tags","origin",f"refs/pull/{WU172_PR}/head")
    data = run("git","show",f"FETCH_HEAD:{WU172_PATH}")
    if git_blob_sha(data) != WU172_BLOB: raise Blocked("WU172_BLOB_MISMATCH")
    return data

def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

def assemble(base):
    root = pathlib.Path("src/windows-v7")
    changes = {}
    wu172 = get_pr_file_bytes()
    for p in sorted(x for x in root.rglob("*") if x.is_file() and x.as_posix() != MANIFEST):
        rel = p.as_posix()
        data = wu172 if rel == WU172_PATH else p.read_bytes()
        data = data.replace(b"7.0.1", b"7.0.2")
        if b"7.0.1" in data: raise Blocked(f"RESIDUAL_7_0_1:{rel}")
        if data != p.read_bytes(): changes[rel] = data
    if MAIN_PATH not in changes or git_blob_sha(changes[MAIN_PATH]) != MAIN_BLOB:
        raise Blocked("MAIN_SCRIPT_BLOB_MISMATCH")
    if WU172_PATH not in changes or git_blob_sha(changes[WU172_PATH]) != WU172_BLOB:
        raise Blocked("WU172_TARGET_BLOB_MISMATCH")

    rows=[]
    inventory=[]
    for p in sorted(x for x in root.rglob("*") if x.is_file() and x.as_posix() != MANIFEST):
        relroot=p.relative_to(root).as_posix()
        data=changes.get(p.as_posix(),p.read_bytes())
        rows.append(f"{sha256(data)}  {relroot.replace('/', chr(92))}")
        inventory.append({"bytes":len(data),"path":relroot,"sha256":sha256(data)})
    manifest=("# VPS Control Center v7.0.2 deterministic canonical Git-blob source manifest\n"+"\n".join(rows)+"\n").encode()
    changes[MANIFEST]=manifest
    inventory.append({"bytes":len(manifest),"path":"VPS-Control-v7-SHA256.txt","sha256":sha256(manifest)})
    inventory.sort(key=lambda x:x["path"])

    candidate=json.loads(pathlib.Path(CANDIDATE).read_text(encoding="utf-8-sig"))
    candidate["candidate_version"]="7.0.2"
    candidate["provenance_path"]=PROVENANCE
    candidate["runtime_authority"]=False; candidate["promotion_authority"]=False
    changes[CANDIDATE]=json_bytes(candidate)

    recipe=json.loads(pathlib.Path(RECIPE).read_text(encoding="utf-8-sig"))
    recipe["candidate_version"]="7.0.2"; recipe["output_filename"]="VPS-Control-v7.0.2.zip"
    recipe["runtime_authority"]=False; recipe["promotion_authority"]=False
    changes[RECIPE]=json_bytes(recipe)

    old=json.loads(pathlib.Path(OLD_PROVENANCE).read_text(encoding="utf-8-sig"))
    prov={
      "activation":{"builder_introduced":True,"candidate_artifact_generated":False,"exact_base_main_sha":base,"work_unit":WU},
      "baseline":{"activated_candidate_version":"7.0.2","embedded_version":"7.0.2","previous_runtime_version":"7.0.1","remediated_files":["modules/V7-StatusCenter.ps1"],"remediated_file_git_blob_sha":{"modules/V7-StatusCenter.ps1":WU172_BLOB},"remediation_class":"PRODUCT_DEFECT_STATUS_CENTER_RESERVE_ROUTING_CONTROL_STATE_CONSISTENCY","requires_version_bump_before_build":False},
      "hash_semantics":"CANONICAL_GIT_BLOB_BYTES","inventory":inventory,
      "parent":{"previous_release_version":"7.0.1","previous_provenance_path":OLD_PROVENANCE},
      "provenance_id":"PNCC_CANONICAL_SOURCE_V7_0_2_PATCH_V1",
      "safety":{"artifact_exists":False,"build_authority":False,"build_input_ready":True,"ci_is_runtime_truth":False,"promotion_authority":False,"runtime_authority":False,"stable_done":False},
      "schema_version":3,"source_identity_semantic":"UNBUILT_V7_0_2_PATCH_SOURCE_BASELINE","source_root":"src/windows-v7"}
    changes[PROVENANCE]=json_bytes(prov)
    # Do not retain accidental same-byte entries.
    return {p:d for p,d in changes.items() if not pathlib.Path(p).exists() or d != pathlib.Path(p).read_bytes()}

def plan(base, expected_head):
    changes=assemble(base)
    if not changes: raise Blocked("EMPTY_PLAN")
    paths=[{"path":p,"git_blob_sha":git_blob_sha(d),"bytes":len(d),"sha256":sha256(d)} for p,d in sorted(changes.items())]
    obj={"schema_version":1,"work_unit":WU,"branch":BRANCH,"base_sha":base,"expected_head_sha":expected_head,"paths":paths}
    canonical=json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return obj,sha256(canonical),changes

def verify_execute_request(req, obj, ph):
    if req.get("plan_sha256") != ph: raise Blocked("PLAN_SHA_MISMATCH")
    requested=req.get("paths")
    if not isinstance(requested,list): raise Blocked("PATH_ALLOWLIST_MISSING")
    compact=[{"path":x["path"],"git_blob_sha":x["git_blob_sha"]} for x in obj["paths"]]
    if requested != compact: raise Blocked("PATH_ALLOWLIST_MISMATCH")
    for x in requested:
        if not str(x["path"]).startswith(("src/windows-v7/",".pncc-dev/","build/")): raise Blocked("PATH_OUTSIDE_WU175")

def execute(req, obj, ph, changes, token):
    verify_execute_request(req,obj,ph)
    branch_ref=api(f"/repos/{REPO}/git/ref/heads/{BRANCH}",token)
    current=branch_ref["object"]["sha"]
    if current != req["expected_head_sha"]: raise Blocked("BRANCH_HEAD_MOVED")
    if current != req["base_sha"]: raise Blocked("EXECUTE_REQUIRES_UNMUTATED_EXACT_BASE")
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
    commit=api(f"/repos/{REPO}/git/commits",token,"POST",{"message":"PIPE-WU-175 materialize exact v7.0.2 assembly","tree":tree["sha"],"parents":[current]})
    api(f"/repos/{REPO}/git/refs/heads/{BRANCH}",token,"PATCH",{"sha":commit["sha"],"force":False})
    rbref=api(f"/repos/{REPO}/git/ref/heads/{BRANCH}",token)
    if rbref["object"]["sha"] != commit["sha"]: raise Blocked("POSTWRITE_REF_MISMATCH")
    print(f"MATERIALIZER_EXECUTE=SUCCESS\nCREATED_COMMIT={commit['sha']}\nPLAN_SHA256={ph}")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--issue-number",type=int,required=True); ap.add_argument("--repository",required=True)
    a=ap.parse_args()
    if a.repository != REPO or a.issue_number != ISSUE: raise Blocked("INVOCATION_SCOPE")
    token=os.environ.get("GITHUB_TOKEN","")
    if not token: raise Blocked("TOKEN_MISSING")
    issue=api(f"/repos/{REPO}/issues/{ISSUE}",token)
    req=parse_request(issue["body"] or "")
    checkout_exact(req["base_sha"])
    obj,ph,changes=plan(req["base_sha"],req["expected_head_sha"])
    if req["action"] == "PLAN":
        print("MATERIALIZER_PLAN=READY")
        print("PLAN_SHA256="+ph)
        print("PLAN_JSON="+json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False))
        return
    execute(req,obj,ph,changes,token)

if __name__ == "__main__":
    try: main()
    except Blocked as e:
        print("MATERIALIZER=BLOCKED"); print("ERROR="+str(e)); sys.exit(2)
