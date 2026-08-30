#!/usr/bin/env python3
"""Fail-closed Human-by-Exception readiness decision evaluator for PIPE-WU-120."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-decision-wu120.json"
ASSESSMENT_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-assessment-wu119.json"
RUBRIC_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-rubric.json"


class DecisionError(ValueError):
    pass


def _strict(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DecisionError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DecisionError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DecisionError("TIME_INVALID:" + name)
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise DecisionError("TIME_INVALID:" + name) from exc
    return dt.astimezone(timezone.utc)


def require_false_map(obj: Any, name: str) -> None:
    if not isinstance(obj, dict) or not obj:
        raise DecisionError(name + "_MAP_REQUIRED")
    for key, value in obj.items():
        if value is not False:
            raise DecisionError(name + "_AUTHORITY_OR_SAFETY_FLAG:" + key)


def active_sets(registry: dict[str, Any], reference: datetime):
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise DecisionError("REGISTRY_ENTRIES_INVALID")
    stale, current = [], []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise DecisionError("REGISTRY_ENTRY_INVALID")
        lease_id = entry.get("lease_id")
        if not isinstance(lease_id, str) or not lease_id or lease_id in seen:
            raise DecisionError("REGISTRY_LEASE_ID_INVALID")
        seen.add(lease_id)
        state = entry.get("state")
        if state == "ACTIVE":
            expiry = parse_time(entry.get("expires_at"), "LEASE_EXPIRES:" + lease_id)
            (stale if expiry <= reference else current).append(entry)
        elif state not in {"RELEASED", "EXPIRED"}:
            raise DecisionError("REGISTRY_STATE_INVALID:" + str(state))
    return stale, current


def validate_assessment(decision: dict[str, Any], assessment: Any, rubric: Any, root: Path,
                        *, check_blobs: bool = True) -> None:
    if not isinstance(assessment, dict):
        raise DecisionError("ASSESSMENT_OBJECT_REQUIRED")
    if assessment.get("schema_version") != 1 or assessment.get("role") != "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_ASSESSMENT":
        raise DecisionError("ASSESSMENT_IDENTITY_INVALID")
    if assessment.get("assessment_state") != "COMPLETE_WITH_BLOCKERS":
        raise DecisionError("ASSESSMENT_STATE_INVALID")
    if assessment.get("readiness_verdict") != "NOT_READY_FOR_HIGHER_AUTONOMY":
        raise DecisionError("ASSESSMENT_VERDICT_INVALID")
    if assessment.get("decision_boundary_ready") is not True or assessment.get("authority_granted") is not False:
        raise DecisionError("ASSESSMENT_AUTHORITY_BOUNDARY_INVALID")
    stale = assessment.get("stale_active_history")
    if not isinstance(stale, list) or len(stale) != 4:
        raise DecisionError("ASSESSMENT_STALE_HISTORY_INVALID")
    expected_ids = set(decision["stale_history_decision"]["lease_ids"])
    if {x.get("lease_id") for x in stale if isinstance(x, dict)} != expected_ids:
        raise DecisionError("ASSESSMENT_STALE_ID_SET_INVALID")
    if not isinstance(rubric, dict) or rubric.get("mode") != "ASSESSMENT_ONLY_FAIL_CLOSED":
        raise DecisionError("RUBRIC_MODE_INVALID")
    if check_blobs:
        if blob_sha(root / decision["assessment_input"]["path"]) != decision["assessment_input"]["blob_sha"]:
            raise DecisionError("ASSESSMENT_BLOB_DRIFT")
        if blob_sha(root / decision["rubric_input"]["path"]) != decision["rubric_input"]["blob_sha"]:
            raise DecisionError("RUBRIC_BLOB_DRIFT")


def evaluate(registry: Any, *, decision: Any = None, assessment: Any = None, rubric: Any = None,
             root: Path = ROOT, check_anchors: bool = True) -> dict[str, Any]:
    d = decision if decision is not None else load_json(DECISION_PATH)
    a = assessment if assessment is not None else load_json(ASSESSMENT_PATH)
    r = rubric if rubric is not None else load_json(RUBRIC_PATH)
    if not isinstance(d, dict):
        raise DecisionError("DECISION_OBJECT_REQUIRED")

    exact = {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_DECISION",
        "decision_state": "FINAL_DEFERRED_WITH_REQUIRED_REMEDIATION",
        "decision_outcome": "DEFER_AND_REMEDIATE",
        "higher_autonomy_authorized": False,
        "authority_granted": False,
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "next_boundary": "WRITER_LEASE_REGISTRY_HISTORICAL_STATE_RECONCILIATION",
    }
    for key, expected in exact.items():
        if d.get(key) != expected:
            raise DecisionError("DECISION_FIELD_INVALID:" + key)

    expected_work = {
        "work_unit_id": "PIPE-WU-120",
        "issue_number": 288,
        "base_sha": "bc8173ab6d5e46f99cf1f4b8ad85e3da398d0d44",
        "branch": "agent/PIPE-WU-120-autonomous-continuation-human-by-exception-readiness-decision",
        "runtime_required": False,
    }
    if d.get("work_unit") != expected_work:
        raise DecisionError("WORK_UNIT_BINDING_INVALID")

    reference = parse_time(d.get("decision_reference_time"), "DECISION_REFERENCE")
    provider = d.get("provider_snapshot")
    if provider != {
        "state_branch_head_sha": "09924cbcd2258559092643661f8999237dceb931",
        "registry_blob_sha": "3c9ff9e63a5974e54e69e6163f241eac36c0b5ba",
        "registry_generation": 28,
    }:
        raise DecisionError("PROVIDER_SNAPSHOT_INVALID")

    if not isinstance(registry, dict) or registry.get("schema_version") != 1 or registry.get("role") != "WRITER_LEASE_REGISTRY":
        raise DecisionError("REGISTRY_IDENTITY_INVALID")
    if registry.get("generation") != 28:
        raise DecisionError("REGISTRY_GENERATION_INVALID")

    stale, current = active_sets(registry, reference)
    stale_decision = d.get("stale_history_decision")
    if not isinstance(stale_decision, dict):
        raise DecisionError("STALE_DECISION_REQUIRED")
    expected_stale_ids = {
        "3bf7a003-1e8e-4ab2-910d-0c1d4aba9b03",
        "38a86545-e9b7-47eb-9b6e-3c9974bbd020",
        "9c2dcb40-26dc-4dce-aa4f-c1be79a66983",
        "ee8b93cb-c629-4f69-82c6-25793fd10d8f",
    }
    if set(stale_decision.get("lease_ids", [])) != expected_stale_ids or stale_decision.get("count") != 4:
        raise DecisionError("STALE_DECISION_SET_INVALID")
    if {x.get("lease_id") for x in stale} != expected_stale_ids:
        raise DecisionError("STALE_PROVIDER_SET_INVALID")
    required_stale = {
        "all_expired_at_decision_reference": True,
        "current_ownership_eligible": False,
        "historical_state_reconciliation_required": True,
        "historical_state_mutation_performed_in_wu120": False,
        "classification": "SEPARATE_AUTHORITY_REQUIRED",
    }
    for key, expected in required_stale.items():
        if stale_decision.get(key) != expected:
            raise DecisionError("STALE_DECISION_FIELD_INVALID:" + key)

    current_writer = d.get("current_writer")
    expected_current = {
        "lease_id": "c8d937b3-b408-43b8-a61d-aa45fb767cf1",
        "work_unit_id": "PIPE-WU-120",
        "generation": 28,
        "base_sha": "bc8173ab6d5e46f99cf1f4b8ad85e3da398d0d44",
        "branch": "agent/PIPE-WU-120-autonomous-continuation-human-by-exception-readiness-decision",
        "state": "ACTIVE",
        "expires_at": "2026-08-30T16:54:00Z",
        "current_ownership_eligible": True,
    }
    if current_writer != expected_current:
        raise DecisionError("CURRENT_WRITER_DECISION_INVALID")
    if len(current) != 1:
        raise DecisionError("CURRENT_WRITER_COUNT_INVALID")
    for key in ("lease_id", "work_unit_id", "generation", "base_sha", "branch", "state", "expires_at"):
        if current[0].get(key) != expected_current[key]:
            raise DecisionError("CURRENT_WRITER_PROVIDER_MISMATCH:" + key)

    reasons = d.get("decision_reasons")
    if not isinstance(reasons, list) or {x.get("id") for x in reasons if isinstance(x, dict)} != {
        "STALE_ACTIVE_LEASE_HISTORY", "OWNER_CONTROLLED_RUNTIME_AND_SECURITY_BOUNDARIES"
    }:
        raise DecisionError("DECISION_REASONS_INVALID")
    capabilities = d.get("proven_existing_capabilities")
    if not isinstance(capabilities, list) or len(capabilities) != 8 or len(set(capabilities)) != 8:
        raise DecisionError("PROVEN_CAPABILITIES_INVALID")
    constraints = d.get("decision_constraints")
    if not isinstance(constraints, dict) or not constraints or any(value is not True for value in constraints.values()):
        raise DecisionError("DECISION_CONSTRAINTS_INVALID")
    require_false_map(d.get("authority_flags"), "DECISION_AUTHORITY")
    require_false_map(d.get("public_safety"), "PUBLIC_SAFETY")
    validate_assessment(d, a, r, root, check_blobs=check_anchors)

    return {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_DECISION_RESULT",
        "state": "READINESS_DECISION_VALIDATED_DEFER_AND_REMEDIATE",
        "decision_outcome": "DEFER_AND_REMEDIATE",
        "higher_autonomy_authorized": False,
        "authority_granted": False,
        "registry_generation": 28,
        "current_writer_lease_id": expected_current["lease_id"],
        "stale_active_history_count": 4,
        "stale_history_current_ownership_eligible": False,
        "historical_state_reconciliation_required": True,
        "next_boundary": d["next_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--no-anchor-check", action="store_true")
    args = parser.parse_args()
    try:
        out = evaluate(load_json(args.registry), check_anchors=not args.no_anchor_check)
    except DecisionError as exc:
        print(json.dumps({"state": "READINESS_DECISION_BLOCKED", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
