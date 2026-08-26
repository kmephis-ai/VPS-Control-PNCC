#!/usr/bin/env python3
"""Deterministic PNCC durable-development-state validation.

Repository state is a contract/checkpoint layer. Fresh provider truth always wins.
This module deliberately uses the Python standard library only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[2]
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
WU_ID = re.compile(r"^[A-Z][A-Z0-9_-]*-[0-9]+$")
FAILURE_CLASSES = {None, "VALIDATOR_DEFECT", "HARNESS_DEFECT", "ENVIRONMENT_OR_BASELINE_BLOCKER", "PRODUCT_DEFECT"}
CHECK_STATES = {"SUCCESS", "FAILURE", "PENDING", "MISSING"}
RUNTIME_STATES = {"NOT_REQUIRED", "NOT_VERIFIED", "RUNTIME_VERIFIED"}
SOURCE_PLANES = {"GITHUB_HOSTED", "PRIVATE_RUNTIME"}


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
    if v["state"] not in {"READY", "ACTIVE", "BLOCKED", "VERIFYING", "DONE", "SUPERSEDED"}:
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
    if snapshot["pr_state"] not in {"OPEN", "CLOSED", "MERGED", "NONE"}:
        raise ContractError("PROVIDER_PR_STATE_INVALID")
    if not isinstance(snapshot["checks"], dict) or any(state not in CHECK_STATES for state in snapshot["checks"].values()):
        raise ContractError("PROVIDER_CHECK_STATE_INVALID")
    _nonempty(snapshot["observed_at"], "provider_snapshot.observed_at")
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


def validate_schema_documents(root: Path = ROOT) -> None:
    expected = {
        "work-unit.schema.json": "PNCC Current Work Unit Contract v1",
        "session-checkpoint.schema.json": "PNCC Session Checkpoint Contract v1",
        "runtime-ledger.schema.json": "PNCC Runtime Ledger Contract v1",
        "evidence-index.schema.json": "PNCC Evidence Index Contract v1",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-examples", action="store_true")
    parser.parse_args()
    try:
        validate_examples(ROOT)
        print(json.dumps({
            "status": "PASS",
            "contract": "PNCC_DURABLE_DEVELOPMENT_STATE_V1",
            "provider_truth_precedence": "ENFORCED",
            "runtime_from_github_ci": "FORBIDDEN"
        }, indent=2))
        return 0
    except ContractError as exc:
        print(json.dumps({"status": "BLOCK", "reason": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
