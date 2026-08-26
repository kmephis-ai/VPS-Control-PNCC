#!/usr/bin/env python3
"""Deterministic PNCC durable-development-state validation.

Repository state is a contract/checkpoint layer. Fresh provider truth always wins.
This module deliberately uses the Python standard library only.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import argparse
import json
import re
import uuid

ROOT = Path(__file__).resolve().parents[2]
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
WU_ID = re.compile(r"^[A-Z][A-Z0-9_-]*-[0-9]+$")
FAILURE_CLASSES = {None, "VALIDATOR_DEFECT", "HARNESS_DEFECT", "ENVIRONMENT_OR_BASELINE_BLOCKER", "PRODUCT_DEFECT"}
CHECK_STATES = {"SUCCESS", "FAILURE", "PENDING", "MISSING"}
RUNTIME_STATES = {"NOT_REQUIRED", "NOT_VERIFIED", "RUNTIME_VERIFIED"}
SOURCE_PLANES = {"GITHUB_HOSTED", "PRIVATE_RUNTIME"}
WORK_UNIT_STATES = {"READY", "ACTIVE", "BLOCKED", "VERIFYING", "DONE", "SUPERSEDED"}
LEASE_STATES = {"ACTIVE", "RELEASED", "EXPIRED"}
PR_STATES = {"OPEN", "CLOSED", "MERGED", "NONE"}
WORK_UNIT_MARKER = re.compile(
    r"<!--\s*PNCC-WORK-UNIT\s+schema=1\s+id=([^\s]+)\s+state=([^\s]+)\s+"
    r"conflict_domain=([^\s]+)\s+branch=([^\s]+)\s+base=([0-9a-f]{40})\s+"
    r"runtime_required=(true|false)\s*-->",
    re.IGNORECASE,
)


class ContractError(ValueError):
    pass


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ContractError(f"DUPLICATE_KEY:{key}")
        out[key] = value
    return out


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError, ContractError) as exc:
        raise ContractError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def _object(value: Any, role: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{role}:OBJECT_REQUIRED")
    if value.get("schema_version") != 1 or value.get("role") != role:
        raise ContractError(f"{role}:IDENTITY_INVALID")
    return value


def _required(value: dict[str, Any], names: set[str], role: str) -> None:
    missing = sorted(names - set(value))
    extra = sorted(set(value) - names)
    if missing:
        raise ContractError(f"{role}:MISSING:{','.join(missing)}")
    if extra:
        raise ContractError(f"{role}:UNKNOWN:{','.join(extra)}")


def _sha40(value: Any, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or SHA40.fullmatch(value) is None:
        raise ContractError(f"SHA40_REQUIRED:{field}")


def _nonempty(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"NONEMPTY_REQUIRED:{field}")


def _string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ContractError(f"STRING_LIST_REQUIRED:{field}")
    if len(value) != len(set(value)):
        raise ContractError(f"LIST_DUPLICATE:{field}")


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"TIMESTAMP_REQUIRED:{field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"TIMESTAMP_INVALID:{field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"TIMESTAMP_TIMEZONE_REQUIRED:{field}")
    return parsed


def validate_work_unit(value: Any) -> dict[str, Any]:
    v = _object(value, "CURRENT_WORK_UNIT")
    fields = {
        "schema_version", "role", "work_unit_id", "goal", "base_sha", "subject_sha", "branch", "pr", "conflict_domain", "state",
        "scope", "forbidden_scope", "required_checks", "runtime_required", "failure_class", "blockers", "exit_criteria",
        "evidence_refs", "next_natural_boundary"
    }
    _required(v, fields, "CURRENT_WORK_UNIT")
    if not isinstance(v["work_unit_id"], str) or WU_ID.fullmatch(v["work_unit_id"]) is None:
        raise ContractError("WORK_UNIT_ID_INVALID")
    for field in ("goal", "branch", "conflict_domain", "next_natural_boundary"):
        _nonempty(v[field], field)
    _sha40(v["base_sha"], "base_sha")
    _sha40(v["subject_sha"], "subject_sha", nullable=True)
    if v["pr"] is not None and (not isinstance(v["pr"], int) or isinstance(v["pr"], bool) or v["pr"] < 1):
        raise ContractError("PR_INVALID")
    if v["state"] not in WORK_UNIT_STATES:
        raise ContractError("WORK_UNIT_STATE_INVALID")
    for field in ("scope", "forbidden_scope", "required_checks", "blockers", "exit_criteria", "evidence_refs"):
        _string_list(v[field], field)
    if not isinstance(v["runtime_required"], bool):
        raise ContractError("RUNTIME_REQUIRED_BOOLEAN")
    if v["failure_class"] not in FAILURE_CLASSES:
        raise ContractError("FAILURE_CLASS_INVALID")
    if v["state"] in {"VERIFYING", "DONE"} and v["subject_sha"] is None:
        raise ContractError("SUBJECT_SHA_REQUIRED_FOR_VERIFIED_STATE")
    if v["state"] == "DONE":
        if v["blockers"]:
            raise ContractError("DONE_WITH_BLOCKERS")
        if not v["evidence_refs"]:
            raise ContractError("DONE_WITHOUT_EVIDENCE")
        if v["failure_class"] is not None:
            raise ContractError("DONE_WITH_FAILURE_CLASS")
    return v


def validate_checkpoint(value: Any) -> dict[str, Any]:
    v = _object(value, "SESSION_CHECKPOINT")
    fields = {"schema_version", "role", "checkpoint_id", "work_unit_id", "recorded_subject_sha", "branch", "pr", "provider_snapshot", "runtime_status", "blockers", "evidence_refs", "next_natural_boundary"}
    _required(v, fields, "SESSION_CHECKPOINT")
    for field in ("checkpoint_id", "branch", "next_natural_boundary"):
        _nonempty(v[field], field)
    if not isinstance(v["work_unit_id"], str) or WU_ID.fullmatch(v["work_unit_id"]) is None:
        raise ContractError("CHECKPOINT_WORK_UNIT_ID_INVALID")
    _sha40(v["recorded_subject_sha"], "recorded_subject_sha")
    if v["pr"] is not None and (not isinstance(v["pr"], int) or isinstance(v["pr"], bool) or v["pr"] < 1):
        raise ContractError("CHECKPOINT_PR_INVALID")
    snapshot = v["provider_snapshot"]
    if not isinstance(snapshot, dict) or set(snapshot) != {"observed_head_sha", "pr_state", "checks", "observed_at"}:
        raise ContractError("PROVIDER_SNAPSHOT_INVALID")
    _sha40(snapshot["observed_head_sha"], "provider_snapshot.observed_head_sha")
    if snapshot["pr_state"] not in PR_STATES:
        raise ContractError("PROVIDER_PR_STATE_INVALID")
    if not isinstance(snapshot["checks"], dict) or any(state not in CHECK_STATES for state in snapshot["checks"].values()):
        raise ContractError("PROVIDER_CHECK_STATE_INVALID")
    _timestamp(snapshot["observed_at"], "provider_snapshot.observed_at")
    if v["runtime_status"] not in RUNTIME_STATES:
        raise ContractError("CHECKPOINT_RUNTIME_STATE_INVALID")
    for field in ("blockers", "evidence_refs"):
        _string_list(v[field], field)
    return v


def validate_runtime_ledger(value: Any) -> dict[str, Any]:
    v = _object(value, "RUNTIME_LEDGER")
    _required(v, {"schema_version", "role", "entries"}, "RUNTIME_LEDGER")
    if not isinstance(v["entries"], list):
        raise ContractError("RUNTIME_ENTRIES_REQUIRED")
    ids: set[str] = set()
    for item in v["entries"]:
        if not isinstance(item, dict) or set(item) != {"entry_id", "work_unit_id", "subject_sha", "status", "source_plane", "evidence_refs"}:
            raise ContractError("RUNTIME_ENTRY_SHAPE_INVALID")
        _nonempty(item["entry_id"], "runtime.entry_id")
        if item["entry_id"] in ids:
            raise ContractError("RUNTIME_ENTRY_DUPLICATE")
        ids.add(item["entry_id"])
        if not isinstance(item["work_unit_id"], str) or WU_ID.fullmatch(item["work_unit_id"]) is None:
            raise ContractError("RUNTIME_WORK_UNIT_ID_INVALID")
        _sha40(item["subject_sha"], "runtime.subject_sha")
        if item["status"] not in RUNTIME_STATES or item["source_plane"] not in SOURCE_PLANES:
            raise ContractError("RUNTIME_CLASSIFICATION_INVALID")
        _string_list(item["evidence_refs"], "runtime.evidence_refs")
        if item["status"] == "RUNTIME_VERIFIED":
            if item["source_plane"] != "PRIVATE_RUNTIME":
                raise ContractError("RUNTIME_VERIFIED_REQUIRES_PRIVATE_RUNTIME")
            if not item["evidence_refs"]:
                raise ContractError("RUNTIME_VERIFIED_REQUIRES_EVIDENCE")
    return v


def validate_evidence_index(value: Any) -> dict[str, Any]:
    v = _object(value, "EVIDENCE_INDEX")
    _required(v, {"schema_version", "role", "entries"}, "EVIDENCE_INDEX")
    if not isinstance(v["entries"], list):
        raise ContractError("EVIDENCE_ENTRIES_REQUIRED")
    ids: set[str] = set()
    for item in v["entries"]:
        expected = {"evidence_id", "work_unit_id", "subject_sha", "kind", "source_plane", "sha256", "uri", "supports_claims"}
        if not isinstance(item, dict) or set(item) != expected:
            raise ContractError("EVIDENCE_ENTRY_SHAPE_INVALID")
        for field in ("evidence_id", "kind", "uri"):
            _nonempty(item[field], f"evidence.{field}")
        if item["evidence_id"] in ids:
            raise ContractError("EVIDENCE_ID_DUPLICATE")
        ids.add(item["evidence_id"])
        if not isinstance(item["work_unit_id"], str) or WU_ID.fullmatch(item["work_unit_id"]) is None:
            raise ContractError("EVIDENCE_WORK_UNIT_ID_INVALID")
        _sha40(item["subject_sha"], "evidence.subject_sha")
        if item["source_plane"] not in SOURCE_PLANES:
            raise ContractError("EVIDENCE_SOURCE_PLANE_INVALID")
        if not isinstance(item["sha256"], str) or SHA64.fullmatch(item["sha256"]) is None:
            raise ContractError("EVIDENCE_SHA256_INVALID")
        _string_list(item["supports_claims"], "evidence.supports_claims")
        if "RUNTIME_VERIFIED" in item["supports_claims"] and item["source_plane"] != "PRIVATE_RUNTIME":
            raise ContractError("GITHUB_EVIDENCE_CANNOT_SUPPORT_RUNTIME_VERIFIED")
    return v


def validate_writer_lease(value: Any) -> dict[str, Any]:
    v = _object(value, "WRITER_LEASE")
    fields = {"schema_version", "role", "lease_id", "work_unit_id", "conflict_domain", "holder", "base_sha", "branch", "state", "generation", "acquired_at", "heartbeat_at", "expires_at"}
    _required(v, fields, "WRITER_LEASE")
    try:
        parsed_uuid = uuid.UUID(str(v["lease_id"]))
    except (ValueError, AttributeError) as exc:
        raise ContractError("LEASE_ID_INVALID") from exc
    if parsed_uuid.version not in {1, 2, 3, 4, 5} or str(parsed_uuid) != str(v["lease_id"]).lower():
        raise ContractError("LEASE_ID_INVALID")
    if not isinstance(v["work_unit_id"], str) or WU_ID.fullmatch(v["work_unit_id"]) is None:
        raise ContractError("LEASE_WORK_UNIT_ID_INVALID")
    for field in ("conflict_domain", "holder", "branch"):
        _nonempty(v[field], f"lease.{field}")
    _sha40(v["base_sha"], "lease.base_sha")
    if v["state"] not in LEASE_STATES:
        raise ContractError("LEASE_STATE_INVALID")
    if not isinstance(v["generation"], int) or isinstance(v["generation"], bool) or v["generation"] < 1:
        raise ContractError("LEASE_GENERATION_INVALID")
    acquired = _timestamp(v["acquired_at"], "lease.acquired_at")
    heartbeat = _timestamp(v["heartbeat_at"], "lease.heartbeat_at")
    expires = _timestamp(v["expires_at"], "lease.expires_at")
    if not acquired <= heartbeat < expires:
        raise ContractError("LEASE_TIME_ORDER_INVALID")
    return v


def validate_provider_truth(value: Any) -> dict[str, Any]:
    v = _object(value, "PROVIDER_TRUTH_SNAPSHOT")
    fields = {"schema_version", "role", "repository", "default_branch", "default_branch_head_sha", "branch", "branch_exists", "branch_head_sha", "pr", "pr_state", "checks", "observed_at"}
    _required(v, fields, "PROVIDER_TRUTH_SNAPSHOT")
    if not isinstance(v["repository"], str) or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", v["repository"]) is None:
        raise ContractError("PROVIDER_REPOSITORY_INVALID")
    for field in ("default_branch", "branch"):
        _nonempty(v[field], f"provider.{field}")
    _sha40(v["default_branch_head_sha"], "provider.default_branch_head_sha")
    if not isinstance(v["branch_exists"], bool):
        raise ContractError("PROVIDER_BRANCH_EXISTS_BOOLEAN")
    _sha40(v["branch_head_sha"], "provider.branch_head_sha", nullable=True)
    if v["branch_exists"] and v["branch_head_sha"] is None:
        raise ContractError("PROVIDER_EXISTING_BRANCH_REQUIRES_HEAD")
    if not v["branch_exists"] and v["branch_head_sha"] is not None:
        raise ContractError("PROVIDER_MISSING_BRANCH_MUST_NOT_HAVE_HEAD")
    if v["pr"] is not None and (not isinstance(v["pr"], int) or isinstance(v["pr"], bool) or v["pr"] < 1):
        raise ContractError("PROVIDER_PR_INVALID")
    if v["pr_state"] not in PR_STATES:
        raise ContractError("PROVIDER_PR_STATE_INVALID")
    if v["pr"] is None and v["pr_state"] != "NONE":
        raise ContractError("PROVIDER_PR_NONE_STATE_MISMATCH")
    if v["pr"] is not None and v["pr_state"] == "NONE":
        raise ContractError("PROVIDER_PR_PRESENT_STATE_MISMATCH")
    if not isinstance(v["checks"], dict) or any(not isinstance(name, str) or not name.strip() or state not in CHECK_STATES for name, state in v["checks"].items()):
        raise ContractError("PROVIDER_CHECKS_INVALID")
    _timestamp(v["observed_at"], "provider.observed_at")
    return v


def parse_work_unit_marker(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        raise ContractError("WORK_UNIT_MARKER_TEXT_REQUIRED")
    matches = WORK_UNIT_MARKER.findall(text)
    if len(matches) != 1:
        raise ContractError(f"WORK_UNIT_MARKER_COUNT:{len(matches)}")
    work_unit_id, state, conflict_domain, branch, base_sha, runtime_required = matches[0]
    if WU_ID.fullmatch(work_unit_id) is None:
        raise ContractError("WORK_UNIT_MARKER_ID_INVALID")
    if state.upper() not in WORK_UNIT_STATES:
        raise ContractError("WORK_UNIT_MARKER_STATE_INVALID")
    _nonempty(conflict_domain, "marker.conflict_domain")
    _nonempty(branch, "marker.branch")
    _sha40(base_sha, "marker.base_sha")
    return {
        "schema_version": 1,
        "work_unit_id": work_unit_id,
        "state": state.upper(),
        "conflict_domain": conflict_domain,
        "branch": branch,
        "base_sha": base_sha,
        "runtime_required": runtime_required.lower() == "true",
    }


def provider_for_checkpoint(provider_truth: dict[str, Any]) -> dict[str, Any]:
    provider = validate_provider_truth(provider_truth)
    return {
        "head_known": provider["branch_exists"] and provider["branch_head_sha"] is not None,
        "head_sha": provider["branch_head_sha"],
        "branch": provider["branch"],
        "pr": provider["pr"],
        "pr_state": provider["pr_state"],
        "checks": dict(provider["checks"]),
    }


def reconcile_checkpoint(checkpoint: dict[str, Any], provider: dict[str, Any]) -> dict[str, Any]:
    """Fresh provider state overrides stored checkpoint state; mismatch blocks resume."""
    validate_checkpoint(checkpoint)
    required = {"head_known", "head_sha", "branch", "pr", "pr_state", "checks"}
    if not isinstance(provider, dict) or set(provider) != required:
        return {"status": "BLOCK", "reasons": ["PROVIDER_TRUTH_INVALID"]}
    reasons: list[str] = []
    if provider["head_known"] is not True:
        reasons.append("PROVIDER_HEAD_UNKNOWN")
    try:
        _sha40(provider["head_sha"], "provider.head_sha")
    except ContractError:
        reasons.append("PROVIDER_HEAD_INVALID")
    if provider.get("head_sha") != checkpoint["recorded_subject_sha"]:
        reasons.append("STALE_CHECKPOINT_HEAD")
    if provider.get("branch") != checkpoint["branch"]:
        reasons.append("CHECKPOINT_BRANCH_MISMATCH")
    if provider.get("pr") != checkpoint["pr"]:
        reasons.append("CHECKPOINT_PR_MISMATCH")
    if provider.get("pr_state") != checkpoint["provider_snapshot"]["pr_state"]:
        reasons.append("CHECKPOINT_PR_STATE_STALE")
    checks = provider.get("checks")
    if not isinstance(checks, dict) or any(v not in CHECK_STATES for v in checks.values()):
        reasons.append("PROVIDER_CHECKS_INVALID")
    else:
        for name, stored in checkpoint["provider_snapshot"]["checks"].items():
            if checks.get(name, "MISSING") != stored:
                reasons.append(f"CHECKPOINT_CHECK_STALE:{name}")
    return {"status": "BLOCK" if reasons else "RESUME_ALLOWED", "reasons": list(dict.fromkeys(reasons))}


def reconcile_writer_lease(work_unit: dict[str, Any], lease: dict[str, Any], provider_truth: dict[str, Any], now_iso: str) -> dict[str, Any]:
    work = validate_work_unit(work_unit)
    active_lease = validate_writer_lease(lease)
    provider = validate_provider_truth(provider_truth)
    now = _timestamp(now_iso, "now")
    reasons: list[str] = []
    if active_lease["work_unit_id"] != work["work_unit_id"]:
        reasons.append("LEASE_WORK_UNIT_MISMATCH")
    if active_lease["conflict_domain"] != work["conflict_domain"]:
        reasons.append("LEASE_CONFLICT_DOMAIN_MISMATCH")
    if active_lease["base_sha"] != work["base_sha"]:
        reasons.append("LEASE_BASE_MISMATCH")
    if active_lease["branch"] != work["branch"]:
        reasons.append("LEASE_BRANCH_MISMATCH")
    if active_lease["state"] != "ACTIVE":
        reasons.append("LEASE_NOT_ACTIVE")
    heartbeat = _timestamp(active_lease["heartbeat_at"], "lease.heartbeat_at")
    expires = _timestamp(active_lease["expires_at"], "lease.expires_at")
    if heartbeat > now:
        reasons.append("LEASE_HEARTBEAT_FROM_FUTURE")
    if now >= expires:
        reasons.append("LEASE_EXPIRED")
    if provider["branch"] != work["branch"]:
        reasons.append("PROVIDER_BRANCH_MISMATCH")
    if provider["branch_exists"] is not True or provider["branch_head_sha"] is None:
        reasons.append("PROVIDER_BRANCH_UNKNOWN")
    if work["subject_sha"] is None:
        reasons.append("ACTIVE_SUBJECT_SHA_UNKNOWN")
    elif provider["branch_head_sha"] != work["subject_sha"]:
        reasons.append("WORK_UNIT_HEAD_MOVED")
    return {"status": "BLOCK" if reasons else "LEASE_VALID", "reasons": list(dict.fromkeys(reasons))}


def decide_resume(work_unit: dict[str, Any], checkpoint: dict[str, Any], lease: dict[str, Any], provider_truth: dict[str, Any], now_iso: str) -> dict[str, Any]:
    try:
        work = validate_work_unit(work_unit)
        saved = validate_checkpoint(checkpoint)
        validate_writer_lease(lease)
        provider = validate_provider_truth(provider_truth)
    except ContractError as exc:
        return {"status": "BLOCK", "reasons": [str(exc)], "next_natural_boundary": None}
    if work["state"] in {"DONE", "SUPERSEDED"}:
        return {"status": "BLOCK", "reasons": ["WORK_UNIT_NOT_RESUMABLE"], "next_natural_boundary": None}
    if work["blockers"]:
        return {"status": "BLOCK", "reasons": ["WORK_UNIT_HAS_BLOCKERS"], "next_natural_boundary": None}
    lease_result = reconcile_writer_lease(work, lease, provider, now_iso)
    if lease_result["status"] != "LEASE_VALID":
        return {"status": "BLOCK", "reasons": lease_result["reasons"], "next_natural_boundary": None}
    if saved["work_unit_id"] != work["work_unit_id"]:
        return {"status": "BLOCK", "reasons": ["CHECKPOINT_WORK_UNIT_MISMATCH"], "next_natural_boundary": None}
    checkpoint_result = reconcile_checkpoint(saved, provider_for_checkpoint(provider))
    if checkpoint_result["status"] != "RESUME_ALLOWED":
        return {"status": "BLOCK", "reasons": checkpoint_result["reasons"], "next_natural_boundary": None}
    failed = [name for name in work["required_checks"] if provider["checks"].get(name, "MISSING") == "FAILURE"]
    if failed:
        return {"status": "BLOCK", "reasons": [f"REQUIRED_CHECK_FAILED:{name}" for name in failed], "next_natural_boundary": None}
    waiting = [name for name in work["required_checks"] if provider["checks"].get(name, "MISSING") in {"PENDING", "MISSING"}]
    if waiting:
        return {"status": "WAITING_PROVIDER_CHECKS", "reasons": [f"REQUIRED_CHECK_NOT_READY:{name}" for name in waiting], "next_natural_boundary": "WAIT_FOR_REQUIRED_CHECKS"}
    if work["runtime_required"] and saved["runtime_status"] != "RUNTIME_VERIFIED":
        return {"status": "WAITING_RUNTIME", "reasons": ["PRIVATE_RUNTIME_EVIDENCE_REQUIRED"], "next_natural_boundary": "WAIT_FOR_PRIVATE_RUNTIME_EVIDENCE"}
    return {"status": "RESUME_ALLOWED", "reasons": [], "next_natural_boundary": work["next_natural_boundary"]}


def validate_schema_documents(root: Path = ROOT) -> None:
    expected = {
        "work-unit.schema.json": "PNCC Current Work Unit Contract v1",
        "session-checkpoint.schema.json": "PNCC Session Checkpoint Contract v1",
        "runtime-ledger.schema.json": "PNCC Runtime Ledger Contract v1",
        "evidence-index.schema.json": "PNCC Evidence Index Contract v1",
        "writer-lease.schema.json": "PNCC Writer Lease Contract v1",
        "provider-truth.schema.json": "PNCC Provider Truth Snapshot v1",
    }
    for name, title in expected.items():
        value = load_json(root / ".pncc-dev/schemas" / name)
        if not isinstance(value, dict) or value.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or value.get("title") != title:
            raise ContractError(f"SCHEMA_DOCUMENT_INVALID:{name}")
        if value.get("additionalProperties") is not False:
            raise ContractError(f"SCHEMA_NOT_STRICT:{name}")


def validate_examples(root: Path = ROOT) -> None:
    validate_schema_documents(root)
    examples = root / ".pncc-dev/examples"
    validate_work_unit(load_json(examples / "work-unit.valid.json"))
    validate_checkpoint(load_json(examples / "session-checkpoint.valid.json"))
    validate_runtime_ledger(load_json(examples / "runtime-ledger.valid.json"))
    validate_evidence_index(load_json(examples / "evidence-index.valid.json"))
    validate_writer_lease(load_json(examples / "writer-lease.valid.json"))
    validate_provider_truth(load_json(examples / "provider-truth.valid.json"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-examples", action="store_true")
    parser.parse_args()
    try:
        validate_examples(ROOT)
        print(json.dumps({
            "status": "PASS",
            "contract": "PNCC_DURABLE_DEVELOPMENT_STATE_V2",
            "provider_truth_precedence": "ENFORCED",
            "writer_lease": "ENFORCED",
            "runtime_from_github_ci": "FORBIDDEN"
        }, indent=2))
        return 0
    except ContractError as exc:
        print(json.dumps({"status": "BLOCK", "reason": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
