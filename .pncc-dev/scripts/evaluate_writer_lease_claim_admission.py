#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import argparse
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev" / "contracts" / "writer-lease-claim-admission-policy.json"
STATE_SPEC = importlib.util.spec_from_file_location("pncc_state", ROOT / ".pncc-dev" / "scripts" / "validate_state.py")
state = importlib.util.module_from_spec(STATE_SPEC)
assert STATE_SPEC.loader is not None
STATE_SPEC.loader.exec_module(state)


class ClaimAdmissionError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClaimAdmissionError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def _parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ClaimAdmissionError(f"TIMESTAMP_INVALID:{field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ClaimAdmissionError(f"TIMESTAMP_TIMEZONE_REQUIRED:{field}")
    return parsed


def _validate_policy(policy: dict[str, Any]) -> None:
    expected_false = {
        "provider_mutation_authority",
        "writer_lease_acquisition_authority",
        "writer_lease_heartbeat_authority",
        "writer_lease_release_authority",
        "writer_lease_steal_authority",
        "branch_creation_authority",
        "autonomous_merge_authority",
        "autonomous_issue_close_authority",
        "runtime_action_authority",
        "promotion_release_tag_authority",
        "ruleset_policy_mutation_authority",
    }
    if policy.get("schema_version") != 1 or policy.get("role") != "WRITER_LEASE_CLAIM_ADMISSION_POLICY":
        raise ClaimAdmissionError("POLICY_IDENTITY_INVALID")
    if policy.get("mode") != "READ_ONLY_ADVISORY":
        raise ClaimAdmissionError("POLICY_MODE_INVALID")
    if policy.get("required_orchestration_schema_version") != 2:
        raise ClaimAdmissionError("POLICY_ORCHESTRATION_SCHEMA_INVALID")
    if policy.get("required_orchestration_state") != "READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS":
        raise ClaimAdmissionError("POLICY_ORCHESTRATION_STATE_INVALID")
    if policy.get("required_orchestration_disposition") != "EXECUTABLE":
        raise ClaimAdmissionError("POLICY_DISPOSITION_INVALID")
    if policy.get("required_selection_classification") != "EXECUTABLE_READ_ONLY_SELECTION":
        raise ClaimAdmissionError("POLICY_SELECTION_CLASSIFICATION_INVALID")
    if policy.get("existing_writer_lease_contract") != "WRITER_LEASE" or policy.get("existing_writer_lease_schema_version") != 1:
        raise ClaimAdmissionError("POLICY_LEASE_CONTRACT_INVALID")
    if policy.get("active_lease_conflict_policy") != "BLOCK_ANY_UNEXPIRED_ACTIVE_LEASE_IN_CONFLICT_DOMAIN":
        raise ClaimAdmissionError("POLICY_ACTIVE_CONFLICT_INVALID")
    if policy.get("historical_lease_policy") != "OBSERVE_RELEASED_OR_EXPIRED_NEVER_REUSE_AS_ACTIVE":
        raise ClaimAdmissionError("POLICY_HISTORICAL_INVALID")
    if policy.get("holder_policy") != "NONEMPTY_EXPLICIT_HOLDER_REQUIRED":
        raise ClaimAdmissionError("POLICY_HOLDER_INVALID")
    if policy.get("base_policy") != "SELECTION_BASE_MUST_EQUAL_DEFAULT_BRANCH_HEAD":
        raise ClaimAdmissionError("POLICY_BASE_INVALID")
    if policy.get("claim_decisions") != ["CLAIM_ELIGIBLE", "BLOCKED"]:
        raise ClaimAdmissionError("POLICY_DECISIONS_INVALID")
    if any(policy.get(name) is not False for name in expected_false):
        raise ClaimAdmissionError("POLICY_MUTATION_AUTHORITY_PRESENT")
    if policy.get("next_boundary_if_eligible") != "SEPARATE_EXPLICIT_WRITER_LEASE_ACQUISITION_AUTHORITY_DESIGN":
        raise ClaimAdmissionError("POLICY_NEXT_BOUNDARY_INVALID")


def evaluate_claim_admission(orchestration: dict[str, Any], leases: list[Any], *, holder: str, now_iso: str, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or _load_json(POLICY_PATH)
    _validate_policy(policy)
    if not isinstance(holder, str) or not holder.strip():
        return _blocked("HOLDER_REQUIRED")
    now = _parse_time(now_iso, "now")
    if not isinstance(orchestration, dict):
        return _blocked("ORCHESTRATION_OBJECT_REQUIRED")
    if orchestration.get("schema_version") != 2:
        return _blocked("ORCHESTRATION_SCHEMA_MISMATCH")
    if orchestration.get("state") != policy["required_orchestration_state"]:
        return _blocked("ORCHESTRATION_STATE_MISMATCH")
    if orchestration.get("orchestration_disposition") != policy["required_orchestration_disposition"]:
        return _blocked("ORCHESTRATION_NOT_EXECUTABLE")
    if orchestration.get("decision") != "SELECTED":
        return _blocked("ORCHESTRATION_SELECTION_REQUIRED")
    selected = orchestration.get("selected")
    if not isinstance(selected, dict):
        return _blocked("SELECTED_WORK_UNIT_REQUIRED")
    required = {"work_unit_id", "conflict_domain", "base_sha", "classification", "runtime_required"}
    if not required.issubset(selected):
        return _blocked("SELECTED_WORK_UNIT_SHAPE_INVALID")
    if selected.get("classification") != policy["required_selection_classification"]:
        return _blocked("SELECTED_CLASSIFICATION_INVALID")
    if selected.get("runtime_required") is not False:
        return _blocked("SELECTED_RUNTIME_REQUIRED")
    default_head = orchestration.get("default_branch_head_sha")
    if selected.get("base_sha") != default_head:
        return _blocked("SELECTION_BASE_STALE")
    if not isinstance(leases, list):
        return _blocked("LEASE_INVENTORY_LIST_REQUIRED")

    seen_ids: set[str] = set()
    historical = 0
    for raw in leases:
        try:
            lease = state.validate_writer_lease(raw)
        except state.ContractError as exc:
            return _blocked("LEASE_INVENTORY_INVALID:" + str(exc))
        lease_id = lease["lease_id"]
        if lease_id in seen_ids:
            return _blocked("LEASE_INVENTORY_DUPLICATE_ID")
        seen_ids.add(lease_id)
        if lease["state"] in {"RELEASED", "EXPIRED"}:
            historical += 1
            continue
        if lease["state"] != "ACTIVE":
            return _blocked("LEASE_STATE_UNCLASSIFIED")
        expires = _parse_time(lease["expires_at"], "lease.expires_at")
        heartbeat = _parse_time(lease["heartbeat_at"], "lease.heartbeat_at")
        if heartbeat > now:
            return _blocked("ACTIVE_LEASE_FUTURE_HEARTBEAT")
        if expires <= now:
            historical += 1
            continue
        if lease["conflict_domain"] == selected["conflict_domain"]:
            return _blocked("ACTIVE_CONFLICT_DOMAIN_LEASE_PRESENT")
        if lease["work_unit_id"] == selected["work_unit_id"]:
            return _blocked("ACTIVE_WORK_UNIT_LEASE_PRESENT")

    return {
        "schema_version": 1,
        "role": "WRITER_LEASE_CLAIM_ADMISSION_DECISION",
        "state": "READ_ONLY_CLAIM_ADMISSION_PASS",
        "decision": "CLAIM_ELIGIBLE",
        "reasons": [],
        "holder": holder,
        "work_unit_id": selected["work_unit_id"],
        "conflict_domain": selected["conflict_domain"],
        "base_sha": selected["base_sha"],
        "historical_lease_count": historical,
        "provider_mutation_performed": False,
        "writer_lease_acquired": False,
        "writer_lease_updated": False,
        "writer_lease_stolen": False,
        "next_boundary": policy["next_boundary_if_eligible"],
    }


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "WRITER_LEASE_CLAIM_ADMISSION_DECISION",
        "state": "READ_ONLY_CLAIM_ADMISSION_BLOCKED",
        "decision": "BLOCKED",
        "reasons": [reason],
        "provider_mutation_performed": False,
        "writer_lease_acquired": False,
        "writer_lease_updated": False,
        "writer_lease_stolen": False,
        "next_boundary": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orchestration", required=True)
    parser.add_argument("--leases", required=True)
    parser.add_argument("--holder", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = evaluate_claim_admission(
            _load_json(Path(args.orchestration)),
            _load_json(Path(args.leases)),
            holder=args.holder,
            now_iso=args.now,
        )
    except ClaimAdmissionError as exc:
        result = _blocked(str(exc))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["decision"] == "CLAIM_ELIGIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
