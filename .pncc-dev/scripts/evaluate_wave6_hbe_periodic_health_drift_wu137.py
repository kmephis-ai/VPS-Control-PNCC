#!/usr/bin/env python3
"""PIPE-WU-137 periodic read-only Human-by-Exception pipeline health/drift evaluator."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ACTIVATION_PATH = ROOT / ".pncc-dev/contracts/wave6-hbe-periodic-health-drift-activation-wu137.json"

class EvaluationError(ValueError):
    pass

def _strict(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise EvaluationError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out

def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc

def parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EvaluationError("TIME_INVALID:" + name)
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise EvaluationError("TIME_INVALID:" + name) from exc

def full_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value)

def validate_activation(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise EvaluationError("ACTIVATION_OBJECT_REQUIRED")
    exact = {
        "schema_version": 1,
        "role": "WAVE6_HBE_PERIODIC_HEALTH_DRIFT_ACTIVATION",
        "activation_state": "OWNER_AUTHORIZED_ACTIVE",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "next_boundary": "EXACT_HEAD_HOSTED_CI_THEN_EXISTING_REUSABLE_MERGE_CLOSE_AUTHORITY",
    }
    for key, expected in exact.items():
        if obj.get(key) != expected:
            raise EvaluationError("ACTIVATION_FIELD_INVALID:" + key)

    work = obj.get("work_unit")
    if work != {
        "work_unit_id": "PIPE-WU-137",
        "issue_number": 322,
        "conflict_domain": "wave6-hbe-periodic-health-drift-activation-existing-authority-only",
        "base_sha": "107f0e3ac66f3fa53bddf6ad30f1afbbccc49ada",
        "branch": "agent/PIPE-WU-137-wave6-hbe-periodic-health-drift-activation",
        "runtime_required": False,
    }:
        raise EvaluationError("WORK_UNIT_BINDING_INVALID")

    proposal = obj.get("proposal_binding")
    if not isinstance(proposal, dict) or proposal.get("blob_sha") != "7605105488aafad7400c26c13a5c8f5515d40a02":
        raise EvaluationError("PROPOSAL_BINDING_INVALID")

    authorization = obj.get("owner_authorization")
    if not isinstance(authorization, dict):
        raise EvaluationError("OWNER_AUTHORIZATION_REQUIRED")
    if authorization.get("issue_number") != 322:
        raise EvaluationError("OWNER_AUTHORIZATION_ISSUE_INVALID")
    if authorization.get("authorized_base_sha") != work["base_sha"]:
        raise EvaluationError("OWNER_AUTHORIZATION_BASE_INVALID")
    if authorization.get("authorized_proposal_blob_sha") != proposal["blob_sha"]:
        raise EvaluationError("OWNER_AUTHORIZATION_PROPOSAL_INVALID")
    if authorization.get("authorized_cadence_seconds") != 3600:
        raise EvaluationError("OWNER_AUTHORIZATION_CADENCE_INVALID")

    monitoring = obj.get("monitoring")
    if not isinstance(monitoring, dict):
        raise EvaluationError("MONITORING_REQUIRED")
    if monitoring.get("mode") != "READ_ONLY_PROVIDER_TRUTH_ONLY":
        raise EvaluationError("MONITORING_MODE_INVALID")
    if monitoring.get("cadence_seconds") != 3600 or monitoring.get("cron_utc") != "17 * * * *":
        raise EvaluationError("MONITORING_CADENCE_INVALID")
    if monitoring.get("snapshot_freshness_max_seconds") != 300 or monitoring.get("future_clock_skew_max_seconds") != 30:
        raise EvaluationError("MONITORING_FRESHNESS_INVALID")
    if monitoring.get("maximum_single_run_seconds") != 600:
        raise EvaluationError("MONITORING_MAX_RUN_INVALID")
    if monitoring.get("overlap_policy") != "SKIP_IF_PREVIOUS_RUN_ACTIVE":
        raise EvaluationError("MONITORING_OVERLAP_INVALID")
    if monitoring.get("missed_run_policy") != "NO_CATCH_UP_BURST_REEVALUATE_FRESH_PROVIDER_TRUTH":
        raise EvaluationError("MONITORING_MISSED_RUN_INVALID")
    required = ["repo-integrity", "powershell-static", "truth-contract"]
    if monitoring.get("required_check_contexts") != required:
        raise EvaluationError("MONITORING_REQUIRED_CHECKS_INVALID")

    ruleset = obj.get("ruleset_binding")
    if ruleset != {
        "ruleset_id": 21585301,
        "enforcement": "active",
        "activation_observed_bypass_actor_count": 0,
        "current_user_can_bypass": "never",
        "ruleset_updated_at": "2026-08-26T21:32:07.589+03:00",
        "bypass_actor_list_revalidation_via_read_only_token": "UNAVAILABLE_BY_GITHUB_API_DESIGN",
        "bypass_drift_detection_policy": "PIN_ZERO_AT_ACTIVATION_AND_DETECT_RULESET_UPDATED_AT_PLUS_EFFECTIVE_RUNNER_BYPASS_CAPABILITY",
        "strict_required_status_checks_policy": True,
        "required_check_contexts": required,
    }:
        raise EvaluationError("RULESET_BINDING_INVALID")

    authority = obj.get("authority")
    if not isinstance(authority, dict) or not authority:
        raise EvaluationError("AUTHORITY_MAP_REQUIRED")
    for key, value in authority.items():
        if value is not False:
            raise EvaluationError("AUTHORITY_PRESENT:" + str(key))
    return obj

def _result(outcome: str, reasons: list[str], activation: dict[str, Any]) -> dict[str, Any]:
    routing = activation["monitoring"]["outcome_routing"]
    return {
        "schema_version": 1,
        "role": "WAVE6_HBE_PERIODIC_HEALTH_DRIFT_RESULT",
        "outcome": outcome,
        "reasons": reasons,
        "route": routing[outcome],
        "provider_mutation_performed": False,
        "runtime_mutation_performed": False,
        "authority_granted": False,
    }

def evaluate(snapshot: Any, *, now: datetime | None = None, activation: Any = None) -> dict[str, Any]:
    try:
        a = validate_activation(activation if activation is not None else load_json(ACTIVATION_PATH))
        if not isinstance(snapshot, dict):
            raise EvaluationError("SNAPSHOT_OBJECT_REQUIRED")
        expected_fields = {
            "observed_at", "repository", "main_sha", "checkout_sha", "provider_state_sha",
            "registry_generation", "frontier_state", "proposal_blob_sha",
            "authorization_issue_state", "authorization_tokens_present",
            "ruleset_id", "ruleset_enforcement", "ruleset_updated_at",
            "ruleset_current_user_can_bypass", "ruleset_rule_types",
            "strict_required_status_checks_policy", "required_check_contexts",
            "required_check_conclusions", "owner_boundary_requested"
        }
        if set(snapshot) != expected_fields:
            raise EvaluationError("SNAPSHOT_FIELDS_INVALID")

        observed = parse_time(snapshot.get("observed_at"), "SNAPSHOT_OBSERVED_AT")
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        age = (reference - observed).total_seconds()
        if age > a["monitoring"]["snapshot_freshness_max_seconds"] or age < -a["monitoring"]["future_clock_skew_max_seconds"]:
            return _result("BLOCKED", ["STALE_OR_FUTURE_PROVIDER_SNAPSHOT"], a)

        drift: list[str] = []
        if snapshot.get("repository") != a["repository"]:
            drift.append("REPOSITORY_IDENTITY_DRIFT")

        for field in ("main_sha", "checkout_sha", "provider_state_sha"):
            if not full_sha(snapshot.get(field)):
                raise EvaluationError("SHA_INVALID:" + field)
        if snapshot["main_sha"] != snapshot["checkout_sha"]:
            drift.append("MAIN_IDENTITY_DRIFT")
        if snapshot.get("frontier_state") != "NONE":
            drift.append("CANONICAL_FRONTIER_DRIFT")
        if snapshot.get("proposal_blob_sha") != a["proposal_binding"]["blob_sha"]:
            drift.append("PROPOSAL_BINDING_DRIFT")

        generation = snapshot.get("registry_generation")
        if not isinstance(generation, int) or isinstance(generation, bool):
            raise EvaluationError("REGISTRY_GENERATION_INVALID")
        if generation < a["writer_lease_acquisition_snapshot"]["generation"]:
            drift.append("PROVIDER_STATE_GENERATION_REGRESSION")

        if snapshot.get("ruleset_id") != a["ruleset_binding"]["ruleset_id"]:
            drift.append("RULESET_ID_DRIFT")
        if snapshot.get("ruleset_enforcement") != a["ruleset_binding"]["enforcement"]:
            drift.append("RULESET_ENFORCEMENT_DRIFT")
        if snapshot.get("ruleset_updated_at") != a["ruleset_binding"]["ruleset_updated_at"]:
            drift.append("RULESET_UPDATED_AT_DRIFT")
        if snapshot.get("ruleset_current_user_can_bypass") != a["ruleset_binding"]["current_user_can_bypass"]:
            return _result("OWNER_EXCEPTION_REQUIRED", ["RULESET_BYPASS_CAPABILITY_DRIFT"], a)
        rule_types = snapshot.get("ruleset_rule_types")
        if not isinstance(rule_types, list) or sorted(rule_types) != sorted(["deletion","non_fast_forward","pull_request","required_status_checks"]):
            drift.append("RULESET_RULE_TYPES_DRIFT")

        if snapshot.get("strict_required_status_checks_policy") is not True:
            drift.append("STRICT_REQUIRED_CHECK_POLICY_DRIFT")
        required = a["monitoring"]["required_check_contexts"]
        contexts = snapshot.get("required_check_contexts")
        if not isinstance(contexts, list) or sorted(contexts) != sorted(required):
            drift.append("REQUIRED_CHECK_CONTEXT_DRIFT")
        conclusions = snapshot.get("required_check_conclusions")
        if not isinstance(conclusions, dict) or set(conclusions) != set(required):
            raise EvaluationError("REQUIRED_CHECK_CONCLUSIONS_INVALID")
        for context in required:
            if conclusions.get(context) != "success":
                drift.append("REQUIRED_CHECK_NOT_SUCCESS:" + context)

        if snapshot.get("authorization_issue_state") not in {"open", "closed"}:
            raise EvaluationError("AUTHORIZATION_ISSUE_STATE_INVALID")
        if snapshot.get("authorization_tokens_present") is not True:
            return _result("OWNER_EXCEPTION_REQUIRED", ["OWNER_AUTHORIZATION_BINDING_NOT_VISIBLE"], a)
        if snapshot.get("owner_boundary_requested") is not False:
            return _result("OWNER_EXCEPTION_REQUIRED", ["OWNER_BOUNDARY_REQUESTED"], a)

        if drift:
            return _result("DRIFT_DETECTED", sorted(set(drift)), a)
        return _result("HEALTHY", [], a)
    except EvaluationError as exc:
        fallback = activation if isinstance(activation, dict) and isinstance(activation.get("monitoring"), dict) else None
        route = "FAIL_CLOSED_OWNER_NOTIFICATION_IF_ACTIONABLE"
        if fallback:
            route = fallback["monitoring"].get("outcome_routing", {}).get("BLOCKED", route)
        return {
            "schema_version": 1,
            "role": "WAVE6_HBE_PERIODIC_HEALTH_DRIFT_RESULT",
            "outcome": "BLOCKED",
            "reasons": [str(exc)],
            "route": route,
            "provider_mutation_performed": False,
            "runtime_mutation_performed": False,
            "authority_granted": False,
        }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--now")
    args = parser.parse_args()
    now = parse_time(args.now, "NOW") if args.now else None
    result = evaluate(load_json(args.snapshot), now=now)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "HEALTHY" else 1

if __name__ == "__main__":
    raise SystemExit(main())
