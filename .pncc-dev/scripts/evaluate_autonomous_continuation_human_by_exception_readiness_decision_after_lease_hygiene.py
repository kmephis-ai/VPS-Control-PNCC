#!/usr/bin/env python3
"""Fail-closed post-hygiene Human-by-Exception readiness decision evaluator for PIPE-WU-125."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-decision-after-lease-hygiene-wu125.json"
ASSESSMENT_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-reassessment-wu124.json"

class DecisionError(ValueError):
    pass

def _strict(pairs):
    out={}
    for key,value in pairs:
        if key in out: raise DecisionError("DUPLICATE_KEY:"+key)
        out[key]=value
    return out

def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DecisionError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc

def blob_sha(path: Path) -> str:
    data=path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value,str) or not value.endswith("Z"):
        raise DecisionError("TIME_INVALID:"+name)
    try:
        return datetime.fromisoformat(value[:-1]+"+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise DecisionError("TIME_INVALID:"+name) from exc

def require_false_map(obj: Any, name: str) -> None:
    if not isinstance(obj,dict) or not obj: raise DecisionError(name+"_MAP_REQUIRED")
    for key,value in obj.items():
        if value is not False: raise DecisionError(name+"_FLAG:"+key)

def active_sets(registry: dict[str,Any], reference: datetime):
    entries=registry.get("entries")
    if not isinstance(entries,list): raise DecisionError("REGISTRY_ENTRIES_INVALID")
    stale,current=[],[]
    seen=set()
    for entry in entries:
        if not isinstance(entry,dict): raise DecisionError("REGISTRY_ENTRY_INVALID")
        lease_id=entry.get("lease_id")
        if not isinstance(lease_id,str) or not lease_id or lease_id in seen:
            raise DecisionError("REGISTRY_LEASE_ID_INVALID")
        seen.add(lease_id)
        state=entry.get("state")
        if state=="ACTIVE":
            expiry=parse_time(entry.get("expires_at"),"LEASE_EXPIRES:"+lease_id)
            (stale if expiry <= reference else current).append(entry)
        elif state not in {"RELEASED","EXPIRED"}:
            raise DecisionError("REGISTRY_STATE_INVALID:"+str(state))
    return stale,current

def evaluate(registry: Any, *, decision: Any=None, assessment: Any=None, root: Path=ROOT, check_anchors: bool=True):
    d=decision if decision is not None else load_json(DECISION_PATH)
    a=assessment if assessment is not None else load_json(ASSESSMENT_PATH)
    exact={
      "schema_version":1,
      "role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_DECISION",
      "decision_state":"FINAL_APPROVED_WITH_EXISTING_AUTHORITY_ONLY",
      "decision_outcome":"APPROVE_HUMAN_BY_EXCEPTION_WITH_EXISTING_AUTHORITY_ONLY",
      "human_by_exception_operating_mode_approved":True,
      "mode_scope":"EXISTING_CANONICAL_AUTHORITY_ONLY",
      "higher_autonomy_authorized":False,
      "authority_granted":False,
      "repository":"kmephis-ai/VPS-Control-PNCC",
      "default_branch":"main",
      "next_boundary":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_OPERATIONALIZATION_WITH_EXISTING_AUTHORITY_ONLY",
    }
    if not isinstance(d,dict): raise DecisionError("DECISION_OBJECT_REQUIRED")
    for key,expected in exact.items():
        if d.get(key)!=expected: raise DecisionError("DECISION_FIELD_INVALID:"+key)
    expected_work={"work_unit_id":"PIPE-WU-125","issue_number":298,"base_sha":"7af4f2752ea59c2c79deb78defe04ce912282019","branch":"agent/PIPE-WU-125-human-by-exception-readiness-decision-after-lease-hygiene","runtime_required":False}
    if d.get("work_unit")!=expected_work: raise DecisionError("WORK_UNIT_BINDING_INVALID")
    provider=d.get("provider_snapshot")
    if provider!={"state_branch":"pncc-provider-state","state_branch_head_sha":"1ccba33253b1c3655d3046baa7021787e7daf12f","registry_blob_sha":"91216366ba87423ffa8d189927a458c09e6a5738","registry_generation":33}:
        raise DecisionError("PROVIDER_SNAPSHOT_INVALID")
    if not isinstance(registry,dict) or registry.get("schema_version")!=1 or registry.get("role")!="WRITER_LEASE_REGISTRY":
        raise DecisionError("REGISTRY_IDENTITY_INVALID")
    if registry.get("generation")!=33: raise DecisionError("REGISTRY_GENERATION_INVALID")
    reference=parse_time(d.get("decision_reference_time"),"DECISION_REFERENCE")
    stale,current=active_sets(registry,reference)
    if stale: raise DecisionError("STALE_ACTIVE_HISTORY_NOT_ZERO")
    hygiene=d.get("lease_hygiene_decision")
    if hygiene!={"stale_active_history_count":0,"residual_blockers":[],"historical_state_reconciliation_required":False,"historical_state_mutation_performed_in_wu125":False,"classification":"CLEAR"}:
        raise DecisionError("LEASE_HYGIENE_DECISION_INVALID")
    expected_current={"lease_id":"27829f63-9bc6-4ba3-b495-4985bb36be32","work_unit_id":"PIPE-WU-125","generation":33,"base_sha":"7af4f2752ea59c2c79deb78defe04ce912282019","branch":"agent/PIPE-WU-125-human-by-exception-readiness-decision-after-lease-hygiene","state":"ACTIVE","expires_at":"2026-08-30T19:40:00Z","current_ownership_eligible":True}
    if d.get("current_writer")!=expected_current: raise DecisionError("CURRENT_WRITER_DECISION_INVALID")
    if len(current)!=1: raise DecisionError("CURRENT_WRITER_COUNT_INVALID")
    for key in ("lease_id","work_unit_id","generation","base_sha","branch","state","expires_at"):
        if current[0].get(key)!=expected_current[key]: raise DecisionError("CURRENT_WRITER_PROVIDER_MISMATCH:"+key)
    if not isinstance(a,dict) or a.get("readiness_verdict")!="READY_WITH_EXISTING_AUTHORITY_ONLY":
        raise DecisionError("ASSESSMENT_VERDICT_INVALID")
    if a.get("authority_granted") is not False: raise DecisionError("ASSESSMENT_AUTHORITY_BOUNDARY_INVALID")
    if check_anchors and blob_sha(root / d["assessment_input"]["path"])!=d["assessment_input"]["blob_sha"]:
        raise DecisionError("ASSESSMENT_BLOB_DRIFT")
    boundaries=d.get("classification_boundaries")
    if boundaries!={"automatic_continuation":"EXISTING_AUTHORITY_ONLY","wait":"WAIT_ONLY","stop":"STOP_ONLY","separate_authority":"SEPARATE_AUTHORITY_REQUIRED","owner_escalation":"OWNER_ESCALATION_REQUIRED"}:
        raise DecisionError("CLASSIFICATION_BOUNDARIES_INVALID")
    constraints=d.get("decision_constraints")
    if not isinstance(constraints,dict) or not constraints or any(v is not True for v in constraints.values()):
        raise DecisionError("DECISION_CONSTRAINTS_INVALID")
    require_false_map(d.get("authority_flags"),"DECISION_AUTHORITY")
    require_false_map(d.get("public_safety"),"PUBLIC_SAFETY")
    return {
      "schema_version":1,
      "role":"AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_DECISION_RESULT",
      "state":"READINESS_DECISION_VALIDATED_APPROVED_EXISTING_AUTHORITY_ONLY",
      "decision_outcome":d["decision_outcome"],
      "human_by_exception_operating_mode_approved":True,
      "mode_scope":"EXISTING_CANONICAL_AUTHORITY_ONLY",
      "higher_autonomy_authorized":False,
      "authority_granted":False,
      "registry_generation":33,
      "current_writer_lease_id":expected_current["lease_id"],
      "stale_active_history_count":0,
      "historical_state_reconciliation_required":False,
      "next_boundary":d["next_boundary"],
    }

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True,type=Path)
    p.add_argument("--no-anchor-check",action="store_true")
    args=p.parse_args()
    try:
        out=evaluate(load_json(args.registry),check_anchors=not args.no_anchor_check)
    except DecisionError as exc:
        print(json.dumps({"state":"READINESS_DECISION_BLOCKED","error":str(exc)},sort_keys=True))
        return 1
    print(json.dumps(out,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
