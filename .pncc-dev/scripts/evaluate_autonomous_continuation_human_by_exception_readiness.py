#!/usr/bin/env python3
"""Fail-closed Human-by-Exception readiness evaluator for PIPE-WU-119."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-rubric.json"
ASSESSMENT_PATH = ROOT / ".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-assessment-wu119.json"

class ReadinessError(ValueError):
    pass

def _strict(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ReadinessError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out

def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc

def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()

def parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReadinessError("TIME_INVALID:" + name)
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ReadinessError("TIME_INVALID:" + name) from exc
    if dt.tzinfo is None:
        raise ReadinessError("TIME_NAIVE:" + name)
    return dt.astimezone(timezone.utc)

def require_false_map(obj: Any, name: str) -> None:
    if not isinstance(obj, dict) or not obj:
        raise ReadinessError(name + "_MAP_REQUIRED")
    for key, value in obj.items():
        if value is not False:
            raise ReadinessError(name + "_AUTHORITY_PRESENT:" + key)

def validate_rubric(rubric: Any) -> dict[str, Any]:
    if not isinstance(rubric, dict):
        raise ReadinessError("RUBRIC_OBJECT_REQUIRED")
    exact = {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_RUBRIC",
        "mode": "ASSESSMENT_ONLY_FAIL_CLOSED",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "next_boundary": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_DECISION",
    }
    for key, expected in exact.items():
        if rubric.get(key) != expected:
            raise ReadinessError("RUBRIC_FIELD_INVALID:" + key)
    if rubric.get("classifications") != [
        "AUTONOMOUS_SAFE", "WAIT_ONLY", "STOP_ONLY", "SEPARATE_AUTHORITY_REQUIRED", "OWNER_ESCALATION_REQUIRED"
    ]:
        raise ReadinessError("RUBRIC_CLASSIFICATIONS_INVALID")
    principles = rubric.get("principles")
    if not isinstance(principles, dict) or not principles or any(value is not True for value in principles.values()):
        raise ReadinessError("RUBRIC_PRINCIPLES_INVALID")
    criteria = rubric.get("criteria")
    if not isinstance(criteria, list) or len(criteria) < 10:
        raise ReadinessError("RUBRIC_CRITERIA_INVALID")
    ids = set()
    for row in criteria:
        if not isinstance(row, dict) or set(row) != {"id", "classification", "requirement"}:
            raise ReadinessError("RUBRIC_CRITERION_SHAPE_INVALID")
        if row["classification"] not in rubric["classifications"]:
            raise ReadinessError("RUBRIC_CRITERION_CLASS_INVALID")
        if row["id"] in ids:
            raise ReadinessError("RUBRIC_CRITERION_DUPLICATE:" + row["id"])
        ids.add(row["id"])
    required_ids = {
        "PROVIDER_TRUTH_FRESH", "BOUNDED_SINGLE_TRANSACTION", "POST_TRANSACTION_READBACK",
        "EXACT_HEAD_CI_CLASSIFICATION", "CLEAN_MULTI_SESSION_RESUME", "PROVIDER_READBACK_PENDING",
        "UNKNOWN_TRANSACTION_OUTCOME", "CLASSIFIED_FAILURE", "EXPIRED_ACTIVE_LEASE_HISTORY",
        "STALE_LEASE_HYGIENE_REMEDIATION", "RUNTIME_NODE_UNAVAILABLE",
        "PHYSICAL_RUNTIME_OR_PRODUCT_MUTATION", "RELEASE_TAG_RULESET_SECURITY_ADWF"
    }
    if ids != required_ids:
        raise ReadinessError("RUBRIC_CRITERION_SET_INVALID")
    require_false_map(rubric.get("authority_flags"), "RUBRIC")
    return rubric

def validate_anchors(assessment: dict[str, Any], root: Path = ROOT) -> None:
    paths = assessment.get("anchor_paths")
    blobs = assessment.get("anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict) or set(paths) != set(blobs) or len(paths) < 25:
        raise ReadinessError("ANCHOR_MAP_INVALID")
    for name, rel in sorted(paths.items()):
        if not isinstance(rel, str) or not rel.startswith(".pncc-dev/"):
            raise ReadinessError("ANCHOR_PATH_INVALID:" + name)
        path = root / rel
        if not path.is_file():
            raise ReadinessError("ANCHOR_MISSING:" + name)
        actual = blob_sha(path)
        if actual != blobs[name]:
            raise ReadinessError(f"ANCHOR_DRIFT:{name}:{actual}")

def _active_lease_rows(registry: dict[str, Any], reference: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise ReadinessError("REGISTRY_ENTRIES_INVALID")
    stale = []
    current = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReadinessError("REGISTRY_ENTRY_INVALID")
        lease_id = entry.get("lease_id")
        if not isinstance(lease_id, str) or not lease_id or lease_id in seen:
            raise ReadinessError("REGISTRY_LEASE_ID_INVALID")
        seen.add(lease_id)
        state = entry.get("state")
        if state == "ACTIVE":
            expiry = parse_time(entry.get("expires_at"), "LEASE_EXPIRES:" + lease_id)
            if expiry <= reference:
                stale.append(entry)
            else:
                current.append(entry)
        elif state not in {"RELEASED", "EXPIRED"}:
            raise ReadinessError("REGISTRY_STATE_INVALID:" + str(state))
    return stale, current

def _expected_stale(assessment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = assessment.get("stale_active_history")
    if not isinstance(rows, list) or not rows:
        raise ReadinessError("ASSESSMENT_STALE_HISTORY_REQUIRED")
    out = {}
    for row in rows:
        keys = {
            "lease_id", "work_unit_id", "generation", "expires_at", "state",
            "current_ownership_eligible", "classification", "remediation"
        }
        if not isinstance(row, dict) or set(row) != keys:
            raise ReadinessError("ASSESSMENT_STALE_ROW_INVALID")
        if row["state"] != "ACTIVE" or row["current_ownership_eligible"] is not False:
            raise ReadinessError("ASSESSMENT_STALE_OWNERSHIP_INVALID")
        if row["classification"] != "STOP_ONLY" or row["remediation"] != "SEPARATE_AUTHORITY_REQUIRED":
            raise ReadinessError("ASSESSMENT_STALE_CLASSIFICATION_INVALID")
        if row["lease_id"] in out:
            raise ReadinessError("ASSESSMENT_STALE_DUPLICATE")
        out[row["lease_id"]] = row
    return out

def evaluate(registry: Any, *, rubric: Any = None, assessment: Any = None,
             root: Path = ROOT, check_anchors: bool = True) -> dict[str, Any]:
    r = validate_rubric(rubric if rubric is not None else load_json(RUBRIC_PATH))
    a = assessment if assessment is not None else load_json(ASSESSMENT_PATH)
    if not isinstance(a, dict):
        raise ReadinessError("ASSESSMENT_OBJECT_REQUIRED")
    exact = {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_ASSESSMENT",
        "assessment_state": "COMPLETE_WITH_BLOCKERS",
        "readiness_verdict": "NOT_READY_FOR_HIGHER_AUTONOMY",
        "decision_boundary_ready": True,
        "authority_granted": False,
        "repository": r["repository"],
        "default_branch": r["default_branch"],
        "next_boundary": r["next_boundary"],
    }
    for key, expected in exact.items():
        if a.get(key) != expected:
            raise ReadinessError("ASSESSMENT_FIELD_INVALID:" + key)
    expected_work = {
        "work_unit_id": "PIPE-WU-119",
        "issue_number": 286,
        "base_sha": "1e028aff8f67d8f438f78dadf6036a2875e2a989",
        "runtime_required": False,
        "branch": "agent/PIPE-WU-119-autonomous-continuation-human-by-exception-readiness-assessment",
    }
    if a.get("work_unit") != expected_work:
        raise ReadinessError("ASSESSMENT_WORK_UNIT_BINDING_INVALID")
    reference = parse_time(a.get("assessment_reference_time"), "ASSESSMENT_REFERENCE")
    provider = a.get("provider_snapshot")
    if provider != {
        "state_branch_head_sha": "779085e68a22b225ffaa2ad2ed4957c65d889ab9",
        "registry_blob_sha": "732278a9ec581a10d2e501c60c87318fd5328be7",
        "registry_generation": 27,
    }:
        raise ReadinessError("ASSESSMENT_PROVIDER_BINDING_INVALID")
    if not isinstance(registry, dict) or registry.get("schema_version") != 1 or registry.get("role") != "WRITER_LEASE_REGISTRY":
        raise ReadinessError("REGISTRY_IDENTITY_INVALID")
    if registry.get("generation") != provider["registry_generation"]:
        raise ReadinessError("REGISTRY_GENERATION_MISMATCH")
    stale, current = _active_lease_rows(registry, reference)
    expected_stale = _expected_stale(a)
    actual_stale = {entry["lease_id"]: entry for entry in stale}
    if set(actual_stale) != set(expected_stale):
        raise ReadinessError("STALE_ACTIVE_SET_MISMATCH")
    for lease_id, row in expected_stale.items():
        entry = actual_stale[lease_id]
        for key in ("work_unit_id", "generation", "expires_at"):
            if entry.get(key) != row[key]:
                raise ReadinessError("STALE_ACTIVE_BINDING_MISMATCH:" + lease_id + ":" + key)
    expected_current = {
        "lease_id": "46d88f55-b9a4-4587-8499-5a26655ceb9b",
        "work_unit_id": "PIPE-WU-119",
        "generation": 27,
        "base_sha": "1e028aff8f67d8f438f78dadf6036a2875e2a989",
        "branch": "agent/PIPE-WU-119-autonomous-continuation-human-by-exception-readiness-assessment",
        "state": "ACTIVE",
        "expires_at": "2026-08-30T16:25:00Z",
        "current_ownership_eligible": True,
    }
    if a.get("current_writer") != expected_current:
        raise ReadinessError("CURRENT_WRITER_ASSESSMENT_INVALID")
    if len(current) != 1:
        raise ReadinessError("CURRENT_ACTIVE_WRITER_COUNT_INVALID")
    entry = current[0]
    for key in ("lease_id", "work_unit_id", "generation", "base_sha", "branch", "state", "expires_at"):
        if entry.get(key) != expected_current[key]:
            raise ReadinessError("CURRENT_WRITER_REGISTRY_MISMATCH:" + key)
    capabilities = a.get("capability_matrix")
    if not isinstance(capabilities, list) or len(capabilities) < 10:
        raise ReadinessError("CAPABILITY_MATRIX_INVALID")
    classes = set(r["classifications"])
    if any(not isinstance(row, dict) or row.get("classification") not in classes for row in capabilities):
        raise ReadinessError("CAPABILITY_CLASSIFICATION_INVALID")
    blockers = a.get("residual_blockers")
    if not isinstance(blockers, list) or {x.get("id") for x in blockers if isinstance(x, dict)} != {
        "STALE_ACTIVE_LEASE_HISTORY", "OWNER_CONTROLLED_RUNTIME_AND_SECURITY_BOUNDARIES"
    }:
        raise ReadinessError("RESIDUAL_BLOCKERS_INVALID")
    stale_blocker = next(x for x in blockers if x["id"] == "STALE_ACTIVE_LEASE_HISTORY")
    if stale_blocker.get("count") != len(stale) or stale_blocker.get("classification") != "SEPARATE_AUTHORITY_REQUIRED":
        raise ReadinessError("STALE_BLOCKER_INVALID")
    public = a.get("public_safety")
    if not isinstance(public, dict) or not public or any(value is not False for value in public.values()):
        raise ReadinessError("PUBLIC_SAFETY_INVALID")
    require_false_map(a.get("assessment_output_authority"), "ASSESSMENT_OUTPUT")
    if check_anchors:
        validate_anchors(a, root)
    return {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_DECISION_INPUT",
        "state": "ASSESSMENT_VALIDATED_WITH_BLOCKERS",
        "readiness_verdict": "NOT_READY_FOR_HIGHER_AUTONOMY",
        "decision_boundary_ready": True,
        "current_writer_lease_id": expected_current["lease_id"],
        "current_registry_generation": registry["generation"],
        "stale_active_history_count": len(stale),
        "stale_active_history_lease_ids": sorted(actual_stale),
        "stale_history_current_ownership_eligible": False,
        "separate_hygiene_authority_required": True,
        "authority_granted": False,
        "next_boundary": r["next_boundary"],
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--no-anchor-check", action="store_true")
    args = parser.parse_args()
    try:
        out = evaluate(load_json(args.registry), check_anchors=not args.no_anchor_check)
    except ReadinessError as exc:
        print(json.dumps({"state": "ASSESSMENT_BLOCKED", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(out, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
