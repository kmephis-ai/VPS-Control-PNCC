#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import argparse
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev" / "contracts" / "writer-lease-lifecycle-autonomous-execution-policy.json"
STATE_SPEC = importlib.util.spec_from_file_location("pncc_state", ROOT / ".pncc-dev" / "scripts" / "validate_state.py")
state = importlib.util.module_from_spec(STATE_SPEC)
assert STATE_SPEC.loader is not None
STATE_SPEC.loader.exec_module(state)


class LifecycleError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def _parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise LifecycleError(f"TIMESTAMP_INVALID:{field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LifecycleError(f"TIMESTAMP_TIMEZONE_REQUIRED:{field}")
    return parsed


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "WRITER_LEASE_LIFECYCLE_DECISION",
        "decision": "BLOCKED",
        "reasons": [reason],
        "provider_mutation_performed": False,
        "autonomous_execution_admitted": False,
    }


def _validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema_version") != 1 or policy.get("role") != "WRITER_LEASE_LIFECYCLE_AUTONOMOUS_EXECUTION_POLICY":
        raise LifecycleError("POLICY_IDENTITY_INVALID")
    if policy.get("mode") != "READ_ONLY_ADVISORY":
        raise LifecycleError("POLICY_MODE_INVALID")
    mutation_authorities = (
        "autonomous_execution_authority",
        "heartbeat_authority",
        "release_authority",
        "lease_acquisition_authority",
        "provider_state_write_authority",
        "autonomous_merge_authority",
        "autonomous_issue_close_authority",
        "runtime_action_authority",
        "product_runtime_mutation_authority",
        "adwf_binding_mutation_authority",
        "promotion_release_tag_authority",
        "ruleset_policy_mutation_authority",
        "private_evidence_publication_authority",
        "reserve_1080_lifecycle_mutation_authority",
        "primary_1081_lifecycle_mutation_authority",
    )
    if any(policy.get(k) is not False for k in mutation_authorities):
        raise LifecycleError("POLICY_MUTATION_AUTHORITY_PRESENT")
    if policy.get("autonomous_execution_requires_explicit_authority") is not True:
        raise LifecycleError("POLICY_EXPLICIT_AUTHORITY_REQUIREMENT_INVALID")
    if policy.get("natural_expiry_policy") != "EXPIRED_BY_TIME_IS_HISTORICAL_WITHOUT_PROVIDER_WRITE":
        raise LifecycleError("POLICY_EXPIRY_INVALID")
    if policy.get("historical_entry_reuse_forbidden") is not True:
        raise LifecycleError("POLICY_HISTORICAL_REUSE_INVALID")


def evaluate_lifecycle(
    lease_raw: Any,
    *,
    action: str,
    holder: str,
    work_unit_id: str,
    conflict_domain: str,
    base_sha: str,
    branch: str,
    now_iso: str,
    fresh_provider_truth: bool,
    explicit_autonomous_authority: bool,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or _load_json(POLICY_PATH)
    _validate_policy(policy)
    try:
        lease = state.validate_writer_lease(lease_raw)
    except state.ContractError as exc:
        return _blocked("LEASE_INVALID:" + str(exc))
    if action not in {"HEARTBEAT", "RELEASE", "AUTONOMOUS_EXECUTION"}:
        return _blocked("ACTION_INVALID")
    try:
        now = _parse_time(now_iso, "now")
        expires = _parse_time(lease["expires_at"], "lease.expires_at")
    except LifecycleError as exc:
        return _blocked(str(exc))
    if lease["state"] in {"RELEASED", "EXPIRED"} or expires <= now:
        return {
            "schema_version": 1,
            "role": "WRITER_LEASE_LIFECYCLE_DECISION",
            "decision": "NATURALLY_EXPIRED" if expires <= now else "BLOCKED",
            "reasons": [] if expires <= now else ["LEASE_NOT_ACTIVE"],
            "provider_mutation_performed": False,
            "autonomous_execution_admitted": False,
        }
    if lease["state"] != "ACTIVE":
        return _blocked("LEASE_NOT_ACTIVE")
    bindings = {
        "holder": holder,
        "work_unit_id": work_unit_id,
        "conflict_domain": conflict_domain,
        "base_sha": base_sha,
        "branch": branch,
    }
    for key, expected in bindings.items():
        if not isinstance(expected, str) or not expected or lease.get(key) != expected:
            return _blocked("BINDING_MISMATCH:" + key)
    if not fresh_provider_truth:
        return _blocked("FRESH_PROVIDER_TRUTH_REQUIRED")
    if action == "HEARTBEAT":
        return {
            "schema_version": 1,
            "role": "WRITER_LEASE_LIFECYCLE_DECISION",
            "decision": "HEARTBEAT_ELIGIBLE",
            "reasons": [],
            "provider_mutation_performed": False,
            "autonomous_execution_admitted": False,
        }
    if action == "RELEASE":
        return {
            "schema_version": 1,
            "role": "WRITER_LEASE_LIFECYCLE_DECISION",
            "decision": "RELEASE_ELIGIBLE",
            "reasons": [],
            "provider_mutation_performed": False,
            "autonomous_execution_admitted": False,
        }
    if not explicit_autonomous_authority:
        return _blocked("EXPLICIT_AUTONOMOUS_AUTHORITY_REQUIRED")
    if policy.get("autonomous_execution_authority") is not False:
        return _blocked("POLICY_AUTHORITY_DRIFT")
    return {
        "schema_version": 1,
        "role": "WRITER_LEASE_LIFECYCLE_DECISION",
        "decision": "BLOCKED",
        "reasons": ["DESIGN_ONLY_POLICY_REQUIRES_SEPARATE_AUTHORITY_CONTRACT"],
        "provider_mutation_performed": False,
        "autonomous_execution_admitted": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--lease", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--holder", required=True)
    p.add_argument("--work-unit-id", required=True)
    p.add_argument("--conflict-domain", required=True)
    p.add_argument("--base-sha", required=True)
    p.add_argument("--branch", required=True)
    p.add_argument("--now", required=True)
    p.add_argument("--fresh-provider-truth", action="store_true")
    p.add_argument("--explicit-autonomous-authority", action="store_true")
    args = p.parse_args()
    try:
        result = evaluate_lifecycle(
            _load_json(Path(args.lease)),
            action=args.action,
            holder=args.holder,
            work_unit_id=args.work_unit_id,
            conflict_domain=args.conflict_domain,
            base_sha=args.base_sha,
            branch=args.branch,
            now_iso=args.now,
            fresh_provider_truth=args.fresh_provider_truth,
            explicit_autonomous_authority=args.explicit_autonomous_authority,
        )
    except LifecycleError as exc:
        result = _blocked(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] in {"HEARTBEAT_ELIGIBLE", "RELEASE_ELIGIBLE", "NATURALLY_EXPIRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
