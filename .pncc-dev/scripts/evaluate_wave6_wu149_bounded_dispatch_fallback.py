#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
import importlib.util
import json
import hashlib

ROOT=Path(__file__).resolve().parents[2]
CONTRACT=ROOT/".pncc-dev/contracts/wave6-wu149-bounded-dispatch-fallback.json"
WU137_ACT=ROOT/".pncc-dev/contracts/wave6-hbe-periodic-health-drift-activation-wu137.json"
WU137_EVAL=ROOT/".pncc-dev/scripts/evaluate_wave6_hbe_periodic_health_drift_wu137.py"

class FallbackError(ValueError): pass

def blob_sha(path: Path)->str:
    b=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def load(path:Path)->Any:
    return json.loads(path.read_text(encoding="utf-8"))

def validate_contract(c:Any, *, check_anchors:bool=True)->dict[str,Any]:
    if not isinstance(c,dict) or c.get("schema_version")!=1 or c.get("role")!="WAVE6_WU149_BOUNDED_DISPATCH_FALLBACK":
        raise FallbackError("CONTRACT_IDENTITY_INVALID")
    if c.get("state")!="BOUNDED_DISPATCH_FALLBACK_ACTIVE_READ_ONLY":
        raise FallbackError("CONTRACT_STATE_INVALID")
    w=c.get("work_unit") or {}
    if w!={"id":"PIPE-WU-149","issue":347,"base_sha":"d526d9cdfbf8227c0147b2fbc088bfdf4aa9ca47","branch":"agent/PIPE-WU-149-bounded-dispatch-fallback","runtime_required":False}:
        raise FallbackError("WORK_UNIT_BINDING_INVALID")
    t=c.get("trigger") or {}
    if t.get("type")!="workflow_dispatch" or any(t.get(k) is not False for k in ("schedule_present","repository_dispatch_present","external_scheduler_present","external_token_present")):
        raise FallbackError("TRIGGER_SCOPE_INVALID")
    con=c.get("concurrency") or {}
    if con.get("cancel_in_progress") is not True or con.get("catch_up_burst_forbidden") is not True:
        raise FallbackError("CONCURRENCY_INVALID")
    expected={"contents":"read","issues":"read","pull_requests":"read","actions":"read","checks":"read"}
    if c.get("permissions")!=expected:
        raise FallbackError("PERMISSIONS_NOT_EXACT_READ_ONLY")
    if not isinstance(c.get("authority"),dict) or any(c["authority"].values()):
        raise FallbackError("AUTHORITY_PRESENT")
    d=c.get("delegation") or {}
    if check_anchors:
        if blob_sha(WU137_ACT)!=d.get("wu137_activation_blob") or blob_sha(WU137_EVAL)!=d.get("wu137_evaluator_blob"):
            raise FallbackError("WU137_ANCHOR_DRIFT")
    if c.get("claims")!={"repairs_github_schedule_delivery":False,"replaces_wu137_schedule":False,"replaces_wu144_observer":False}:
        raise FallbackError("OVERCLAIM_INVALID")
    return c

def evaluate(snapshot:Any, contract:Any=None)->dict[str,Any]:
    try:
        c=validate_contract(contract if contract is not None else load(CONTRACT))
        spec=importlib.util.spec_from_file_location("wu137",WU137_EVAL)
        m=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(m)
        result=m.evaluate(snapshot)
        if result.get("provider_mutation_performed") is not False or result.get("runtime_mutation_performed") is not False or result.get("authority_granted") is not False:
            raise FallbackError("DELEGATED_RESULT_AUTHORITY_INVALID")
        return {
          "schema_version":1,"role":"WAVE6_WU149_BOUNDED_DISPATCH_FALLBACK_RESULT",
          "state":"PASS" if result.get("outcome")=="HEALTHY" else "SIGNAL",
          "outcome":result.get("outcome"),"reasons":result.get("reasons",[]),"route":result.get("route"),
          "provider_mutation_performed":False,"runtime_mutation_performed":False,"authority_granted":False,
          "claims_schedule_repaired":False
        }
    except (FallbackError, Exception) as exc:
        return {"schema_version":1,"role":"WAVE6_WU149_BOUNDED_DISPATCH_FALLBACK_RESULT","state":"BLOCKED",
                "outcome":"BLOCKED","reasons":[str(exc)],"route":"FAIL_CLOSED_OWNER_NOTIFICATION_IF_ACTIONABLE",
                "provider_mutation_performed":False,"runtime_mutation_performed":False,"authority_granted":False,
                "claims_schedule_repaired":False}

def main()->int:
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--snapshot",type=Path,required=True); args=ap.parse_args()
    r=evaluate(load(args.snapshot)); print(json.dumps(r,sort_keys=True))
    return 0 if r["outcome"]=="HEALTHY" else 1

if __name__=="__main__": raise SystemExit(main())
