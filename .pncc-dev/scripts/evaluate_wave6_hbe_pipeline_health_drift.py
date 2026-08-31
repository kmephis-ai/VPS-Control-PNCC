#!/usr/bin/env python3
"""Read-only Wave 6 Human-by-Exception pipeline health/drift evaluator for PIPE-WU-135."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev/contracts/wave6-hbe-pipeline-health-drift-assessment-policy.json"
ASSESSMENT_PATH = ROOT / ".pncc-dev/contracts/wave6-hbe-pipeline-health-drift-assessment-wu135.json"

class AssessmentError(ValueError):
    pass

def _strict(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AssessmentError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out

def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssessmentError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc

def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()

def parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AssessmentError("TIME_INVALID:" + name)
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AssessmentError("TIME_INVALID:" + name) from exc
    return dt.astimezone(timezone.utc)

def _false_authority_map(obj: Any, name: str) -> None:
    if not isinstance(obj, dict) or not obj:
        raise AssessmentError(name + "_MAP_REQUIRED")
    for key, value in obj.items():
        if value is not False:
            raise AssessmentError(name + "_AUTHORITY_PRESENT:" + str(key))

def validate_policy(policy: Any, root: Path = ROOT, check_anchors: bool = True) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise AssessmentError("POLICY_OBJECT_REQUIRED")
    exact = {
        "schema_version": 1,
        "role": "WAVE6_HBE_PIPELINE_HEALTH_DRIFT_ASSESSMENT_POLICY",
        "mode": "READ_ONLY_FAIL_CLOSED",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "work_unit_id": "PIPE-WU-135",
        "issue_number": 318,
        "base_sha": "55c1ff6ea4b43ce7b8a6735c3475a996ef49cc4c",
        "frontier_id": "WAVE6_HBE_PIPELINE_HEALTH_DRIFT_READ_ONLY_ASSESSMENT_EXISTING_AUTHORITY_ONLY",
        "ruleset_enforcement_required": "ACTIVE_NO_BYPASS",
        "next_boundary": "WAVE6_PERIODIC_HEALTH_DRIFT_AUTHORITY_PROPOSAL_PREPARATION",
        "predecessor_frontier_blob_sha": "c9f16baebd6ba5416e176b76fe69e32387e93786",
    }
    for key, expected in exact.items():
        if policy.get(key) != expected:
            raise AssessmentError("POLICY_FIELD_INVALID:" + key)
    if policy.get("outcomes") != ["HEALTHY", "DRIFT_DETECTED", "OWNER_EXCEPTION_REQUIRED", "BLOCKED"]:
        raise AssessmentError("POLICY_OUTCOMES_INVALID")
    if policy.get("freshness_max_seconds") != 300 or policy.get("future_clock_skew_max_seconds") != 30:
        raise AssessmentError("POLICY_FRESHNESS_INVALID")
    required_checks = policy.get("required_check_contexts")
    if required_checks != ["repo-integrity", "powershell-static", "truth-contract"]:
        raise AssessmentError("POLICY_REQUIRED_CHECKS_INVALID")
    boundary_fields = policy.get("boundary_request_fields")
    if not isinstance(boundary_fields, list) or len(boundary_fields) != 11 or len(set(boundary_fields)) != len(boundary_fields):
        raise AssessmentError("POLICY_BOUNDARY_FIELDS_INVALID")
    paths, blobs = policy.get("anchor_paths"), policy.get("anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict) or set(paths) != set(blobs) or len(paths) < 8:
        raise AssessmentError("POLICY_ANCHORS_INVALID")
    if check_anchors:
        for name, rel in sorted(paths.items()):
            if not isinstance(rel, str):
                raise AssessmentError("ANCHOR_PATH_INVALID:" + name)
            p = root / rel
            if not p.is_file():
                raise AssessmentError("ANCHOR_MISSING:" + name)
            actual = blob_sha(p)
            if actual != blobs[name]:
                raise AssessmentError(f"ANCHOR_DRIFT:{name}:{actual}")
    authority_keys = [k for k in policy if k.endswith("_authority")]
    if not authority_keys:
        raise AssessmentError("POLICY_AUTHORITY_FLAGS_MISSING")
    for key in authority_keys:
        if policy[key] is not False:
            raise AssessmentError("POLICY_AUTHORITY_PRESENT:" + key)
    return policy

def validate_assessment(assessment: Any, policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(assessment, dict):
        raise AssessmentError("ASSESSMENT_OBJECT_REQUIRED")
    exact = {
        "schema_version": 1,
        "role": "WAVE6_HBE_PIPELINE_HEALTH_DRIFT_ASSESSMENT",
        "assessment_state": "BASELINE_HEALTHY_EXISTING_AUTHORITY_ONLY",
        "next_boundary": policy["next_boundary"],
    }
    for key, expected in exact.items():
        if assessment.get(key) != expected:
            raise AssessmentError("ASSESSMENT_FIELD_INVALID:" + key)
    work = assessment.get("work_unit")
    if work != {
        "work_unit_id": "PIPE-WU-135",
        "issue_number": 318,
        "conflict_domain": "wave6-hbe-pipeline-health-drift-read-only-assessment-existing-authority-only",
        "base_sha": policy["base_sha"],
        "branch": "agent/PIPE-WU-135-wave6-hbe-pipeline-health-drift-read-only-assessment",
        "runtime_required": False,
    }:
        raise AssessmentError("ASSESSMENT_WORK_UNIT_INVALID")
    binding = assessment.get("policy_binding")
    if binding != {
        "path": ".pncc-dev/contracts/wave6-hbe-pipeline-health-drift-assessment-policy.json",
        "blob_sha": "8ab59b82d5ff5503c534424929017122ab03b363",
    }:
        raise AssessmentError("ASSESSMENT_POLICY_BINDING_INVALID")
    baseline = assessment.get("provider_baseline")
    if not isinstance(baseline, dict):
        raise AssessmentError("ASSESSMENT_PROVIDER_BASELINE_INVALID")
    required_baseline = {
        "main_sha": policy["base_sha"],
        "provider_state_acquisition_sha": "f0a96f140b25e22e8c02dfe65d625b7d0220ae8a",
        "registry_blob_sha": "c4b4f6aee90d46f214edb674b1f012c915ed2737",
        "registry_generation": 46,
        "writer_lease_id": "e95d9207-7d86-4f03-83fe-535bb19b485e",
        "selected_work_unit_id": "PIPE-WU-135",
        "selected_work_unit_issue_number": 318,
    }
    if baseline != required_baseline:
        raise AssessmentError("ASSESSMENT_PROVIDER_BASELINE_MISMATCH")
    dimensions = assessment.get("health_dimensions")
    if not isinstance(dimensions, list) or {x.get("id") for x in dimensions if isinstance(x, dict)} != {
        "FRESH_PROVIDER_TRUTH","MAIN_IDENTITY","CANONICAL_WORK_UNIT","PROVIDER_STATE",
        "RULESET_ENFORCEMENT","REQUIRED_CHECK_CONTEXTS","AUTHORITY_BOUNDARIES"
    }:
        raise AssessmentError("ASSESSMENT_DIMENSIONS_INVALID")
    routing = assessment.get("outcome_routing")
    if not isinstance(routing, dict) or set(routing) != set(policy["outcomes"]):
        raise AssessmentError("ASSESSMENT_ROUTING_INVALID")
    if any("NO_MUTATION" not in value for value in routing.values()):
        raise AssessmentError("ASSESSMENT_ROUTING_MUTATION_RISK")
    _false_authority_map(assessment.get("assessment_output_authority"), "ASSESSMENT_OUTPUT")
    successor = assessment.get("successor_frontier")
    if successor != {
        "frontier_id": "WAVE6_HBE_PERIODIC_HEALTH_DRIFT_AUTHORITY_PROPOSAL_PREPARATION_EXISTING_AUTHORITY_ONLY",
        "blob_sha": "0fcd62f95ca491d70faddc07a251baed0524f876",
        "authority_granted": False,
    }:
        raise AssessmentError("ASSESSMENT_SUCCESSOR_INVALID")
    return assessment

def re_full_sha(value: str) -> bool:
    return len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)

def _result(outcome: str, reasons: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "WAVE6_HBE_PIPELINE_HEALTH_DRIFT_ASSESSMENT_RESULT",
        "outcome": outcome,
        "reasons": reasons,
        "provider_mutation_performed": False,
        "periodic_schedule_created": False,
        "unattended_mutation_authority_granted": False,
        "authority_granted": False,
        "next_boundary": policy["next_boundary"] if outcome == "HEALTHY" else "RECONCILE_BEFORE_ANY_MUTATION",
    }

def evaluate(snapshot: Any, *, now: datetime | None = None, policy: Any = None,
             assessment: Any = None, root: Path = ROOT, check_anchors: bool = True) -> dict[str, Any]:
    try:
        p = validate_policy(policy if policy is not None else load_json(POLICY_PATH), root, check_anchors)
        a = validate_assessment(assessment if assessment is not None else load_json(ASSESSMENT_PATH), p)
        if not isinstance(snapshot, dict):
            raise AssessmentError("SNAPSHOT_OBJECT_REQUIRED")
        required = set(p["required_provider_fields"])
        if set(snapshot) != required:
            raise AssessmentError("SNAPSHOT_FIELDS_INVALID")
        if snapshot.get("repository") != p["repository"]:
            return _result("DRIFT_DETECTED", ["REPOSITORY_IDENTITY_DRIFT"], p)
        observed = parse_time(snapshot.get("observed_at"), "SNAPSHOT_OBSERVED_AT")
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        age = (reference - observed).total_seconds()
        if age > p["freshness_max_seconds"] or age < -p["future_clock_skew_max_seconds"]:
            return _result("BLOCKED", ["STALE_OR_FUTURE_PROVIDER_SNAPSHOT"], p)
        drift = []
        if snapshot.get("main_sha") != p["base_sha"]:
            drift.append("MAIN_SHA_DRIFT")
        if snapshot.get("selected_work_unit_id") != "PIPE-WU-135" or snapshot.get("selected_work_unit_issue_number") != 318 or snapshot.get("selected_work_unit_state") != "OPEN_READY":
            drift.append("CANONICAL_WORK_UNIT_DRIFT")
        state_sha = snapshot.get("provider_state_sha")
        if not isinstance(state_sha, str) or re_full_sha(state_sha) is False:
            raise AssessmentError("PROVIDER_STATE_SHA_INVALID")
        generation = snapshot.get("registry_generation")
        if not isinstance(generation, int) or isinstance(generation, bool):
            raise AssessmentError("REGISTRY_GENERATION_INVALID")
        if generation < a["provider_baseline"]["registry_generation"]:
            drift.append("PROVIDER_STATE_GENERATION_REGRESSION")
        if snapshot.get("ruleset_enforcement") != p["ruleset_enforcement_required"]:
            drift.append("RULESET_ENFORCEMENT_DRIFT")
        checks = snapshot.get("required_check_contexts")
        if not isinstance(checks, list) or sorted(checks) != sorted(p["required_check_contexts"]):
            drift.append("REQUIRED_CHECK_CONTEXT_DRIFT")
        boundary = snapshot.get("boundary_requests")
        if not isinstance(boundary, dict) or set(boundary) != set(p["boundary_request_fields"]) or any(type(v) is not bool for v in boundary.values()):
            raise AssessmentError("BOUNDARY_REQUESTS_INVALID")
        if any(boundary.values()):
            active = sorted(k for k, v in boundary.items() if v)
            return _result("OWNER_EXCEPTION_REQUIRED", ["OWNER_BOUNDARY:" + x for x in active], p)
        if drift:
            return _result("DRIFT_DETECTED", sorted(drift), p)
        return _result("HEALTHY", [], p)
    except AssessmentError as exc:
        return {
            "schema_version": 1,
            "role": "WAVE6_HBE_PIPELINE_HEALTH_DRIFT_ASSESSMENT_RESULT",
            "outcome": "BLOCKED",
            "reasons": [str(exc)],
            "provider_mutation_performed": False,
            "periodic_schedule_created": False,
            "unattended_mutation_authority_granted": False,
            "authority_granted": False,
            "next_boundary": "RECONCILE_BEFORE_ANY_MUTATION",
        }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--now")
    parser.add_argument("--no-anchor-check", action="store_true")
    args = parser.parse_args()
    now = parse_time(args.now, "NOW") if args.now else None
    result = evaluate(load_json(args.snapshot), now=now, check_anchors=not args.no_anchor_check)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "HEALTHY" else 1

if __name__ == "__main__":
    raise SystemExit(main())
