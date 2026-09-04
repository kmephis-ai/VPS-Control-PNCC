#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any, Iterable

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+\.iss$")
SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
AUTH_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
REPOSITORY = "kmephis-ai/VPS-Control-PNCC"

SOURCE_KEYS = {
    "schema_version", "work_unit_id", "source_transaction_work_unit", "decision",
    "reasons", "proposal_sha256", "proposal_byte_count", "binding_request_sha256",
    "transaction_intent_sha256", "target_path", "execution_authorization_request_sha256",
    "exact_transaction_lineage_match", "target_metadata_safe", "verified",
    "durable_identity_bound", "proposal_materialized", "binding_receipt_persisted",
    "write_authorized", "compiler_execution_authorized", "build_authorized",
}

CONTRACT_KEYS = {
    "schema_version", "work_unit_id", "source_execution_authorization_work_unit",
    "repository", "base_sha", "target_branch", "target_path", "proposal_sha256",
    "proposal_byte_count", "execution_authorization_request_sha256",
    "expected_prewrite_state", "expected_prewrite_blob_sha", "force",
    "immutable_postwrite_blob_readback", "single_transaction", "consumed",
    "authorization_id", "owner_authorization_state",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _valid_sha40(value: Any) -> bool:
    return isinstance(value, str) and SHA40_RE.fullmatch(value) is not None


def _valid_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _safe_target_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 240:
        return False
    if value.startswith(("/", "\\")) or "\\" in value or ":" in value:
        return False
    if value.endswith("/") or "//" in value:
        return False
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    return SAFE_PATH_RE.fullmatch(value) is not None


def _safe_target_branch(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 200:
        return False
    if value in ("main", "master") or value.startswith(("refs/", "/")):
        return False
    if "\\" in value or ".." in value or "//" in value or value.endswith(("/", ".")):
        return False
    return SAFE_BRANCH_RE.fullmatch(value) is not None


def _valid_prewrite(state: Any, blob_sha: Any) -> bool:
    if state == "ABSENT":
        return blob_sha == ""
    if state == "EXACT_BLOB":
        return _valid_sha40(blob_sha)
    return False


def evaluate(source_receipt: Any, authorization_contract: Any) -> dict[str, Any]:
    reasons: list[str] = []

    if not isinstance(source_receipt, dict):
        reasons.append("INVALID_SOURCE_RECEIPT_TYPE")
        source_receipt = {}
    if set(source_receipt) != SOURCE_KEYS:
        reasons.append("INVALID_SOURCE_RECEIPT_KEYS")
    if source_receipt.get("schema_version") != 1:
        reasons.append("INVALID_SOURCE_RECEIPT_SCHEMA_VERSION")
    if source_receipt.get("work_unit_id") != "PIPE-WU-192":
        reasons.append("INVALID_SOURCE_RECEIPT_WORK_UNIT")
    if source_receipt.get("source_transaction_work_unit") != "PIPE-WU-191":
        reasons.append("INVALID_SOURCE_RECEIPT_SOURCE")
    if source_receipt.get("decision") != "EXECUTION_AUTHORIZATION_READY_ONLY":
        reasons.append("SOURCE_RECEIPT_NOT_EXECUTION_AUTHORIZATION_READY_ONLY")
    if source_receipt.get("reasons") != []:
        reasons.append("SOURCE_RECEIPT_REASONS_NOT_EMPTY")
    if source_receipt.get("exact_transaction_lineage_match") is not True:
        reasons.append("SOURCE_RECEIPT_LINEAGE_NOT_EXACT")
    if source_receipt.get("target_metadata_safe") is not True:
        reasons.append("SOURCE_RECEIPT_TARGET_NOT_SAFE")
    for key in (
        "verified", "durable_identity_bound", "proposal_materialized",
        "binding_receipt_persisted", "write_authorized",
        "compiler_execution_authorized", "build_authorized",
    ):
        if source_receipt.get(key) is not False:
            reasons.append("SOURCE_RECEIPT_AUTHORITY_ESCALATION")
            break

    source_proposal = source_receipt.get("proposal_sha256")
    source_count = source_receipt.get("proposal_byte_count")
    source_exec = source_receipt.get("execution_authorization_request_sha256")
    source_path = source_receipt.get("target_path")
    if not _valid_sha256(source_proposal):
        reasons.append("INVALID_SOURCE_PROPOSAL_SHA256")
    if not _valid_count(source_count):
        reasons.append("INVALID_SOURCE_PROPOSAL_BYTE_COUNT")
    if not _valid_sha256(source_exec):
        reasons.append("INVALID_SOURCE_EXECUTION_AUTHORIZATION_REQUEST_SHA256")
    if not _safe_target_path(source_path):
        reasons.append("INVALID_SOURCE_TARGET_PATH")

    if not isinstance(authorization_contract, dict):
        reasons.append("INVALID_AUTHORIZATION_CONTRACT_TYPE")
        authorization_contract = {}
    if set(authorization_contract) != CONTRACT_KEYS:
        reasons.append("INVALID_AUTHORIZATION_CONTRACT_KEYS")
    if authorization_contract.get("schema_version") != 1:
        reasons.append("INVALID_AUTHORIZATION_CONTRACT_SCHEMA_VERSION")
    if authorization_contract.get("work_unit_id") != "PIPE-WU-193":
        reasons.append("INVALID_AUTHORIZATION_CONTRACT_WORK_UNIT")
    if authorization_contract.get("source_execution_authorization_work_unit") != "PIPE-WU-192":
        reasons.append("INVALID_AUTHORIZATION_CONTRACT_SOURCE")
    if authorization_contract.get("repository") != REPOSITORY:
        reasons.append("INVALID_AUTHORIZATION_CONTRACT_REPOSITORY")

    base_sha = authorization_contract.get("base_sha")
    target_branch = authorization_contract.get("target_branch")
    target_path = authorization_contract.get("target_path")
    proposal_sha = authorization_contract.get("proposal_sha256")
    proposal_count = authorization_contract.get("proposal_byte_count")
    exec_sha = authorization_contract.get("execution_authorization_request_sha256")
    prewrite_state = authorization_contract.get("expected_prewrite_state")
    prewrite_blob = authorization_contract.get("expected_prewrite_blob_sha")
    authorization_id = authorization_contract.get("authorization_id")

    if not _valid_sha40(base_sha):
        reasons.append("INVALID_BASE_SHA")
    branch_safe = _safe_target_branch(target_branch)
    if not branch_safe:
        reasons.append("UNSAFE_TARGET_BRANCH")
    path_safe = _safe_target_path(target_path)
    if not path_safe:
        reasons.append("UNSAFE_TARGET_PATH")
    if not _valid_sha256(proposal_sha):
        reasons.append("INVALID_PROPOSAL_SHA256")
    if not _valid_count(proposal_count):
        reasons.append("INVALID_PROPOSAL_BYTE_COUNT")
    if not _valid_sha256(exec_sha):
        reasons.append("INVALID_EXECUTION_AUTHORIZATION_REQUEST_SHA256")
    prewrite_valid = _valid_prewrite(prewrite_state, prewrite_blob)
    if not prewrite_valid:
        reasons.append("INVALID_PREWRITE_EXPECTATION")
    if not isinstance(authorization_id, str) or AUTH_ID_RE.fullmatch(authorization_id) is None:
        reasons.append("INVALID_AUTHORIZATION_ID")
    if authorization_contract.get("force") is not False:
        reasons.append("FORCE_NOT_ALLOWED")
    if authorization_contract.get("immutable_postwrite_blob_readback") is not True:
        reasons.append("IMMUTABLE_POSTWRITE_READBACK_REQUIRED")
    if authorization_contract.get("single_transaction") is not True:
        reasons.append("SINGLE_TRANSACTION_REQUIRED")
    if authorization_contract.get("consumed") is not False:
        reasons.append("AUTHORIZATION_ALREADY_CONSUMED")
    if authorization_contract.get("owner_authorization_state") != "NOT_GRANTED":
        reasons.append("OWNER_AUTHORIZATION_MUST_REMAIN_NOT_GRANTED")

    if _valid_sha256(proposal_sha) and _valid_sha256(source_proposal) and proposal_sha != source_proposal:
        reasons.append("PROPOSAL_SHA256_MISMATCH")
    if _valid_count(proposal_count) and _valid_count(source_count) and proposal_count != source_count:
        reasons.append("PROPOSAL_BYTE_COUNT_MISMATCH")
    if _valid_sha256(exec_sha) and _valid_sha256(source_exec) and exec_sha != source_exec:
        reasons.append("EXECUTION_AUTHORIZATION_REQUEST_SHA256_MISMATCH")
    if path_safe and _safe_target_path(source_path) and target_path != source_path:
        reasons.append("TARGET_PATH_MISMATCH")

    contract_digest = hashlib.sha256(_canonical_bytes(authorization_contract)).hexdigest()
    reasons = sorted(set(reasons))
    ready = not reasons

    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-193",
        "source_execution_authorization_work_unit": "PIPE-WU-192",
        "decision": "WRITE_AUTHORIZATION_CONTRACT_READY_ONLY" if ready else "BLOCKED",
        "reasons": reasons,
        "repository": authorization_contract.get("repository") if authorization_contract.get("repository") == REPOSITORY else REPOSITORY,
        "base_sha": base_sha if _valid_sha40(base_sha) else "0" * 40,
        "target_branch": target_branch if branch_safe else "",
        "target_path": target_path if path_safe else "",
        "proposal_sha256": proposal_sha if _valid_sha256(proposal_sha) else "0" * 64,
        "proposal_byte_count": proposal_count if _valid_count(proposal_count) else 0,
        "execution_authorization_request_sha256": exec_sha if _valid_sha256(exec_sha) else "0" * 64,
        "expected_prewrite_state": prewrite_state if prewrite_state in ("ABSENT", "EXACT_BLOB") else "",
        "expected_prewrite_blob_sha": prewrite_blob if isinstance(prewrite_blob, str) and (prewrite_blob == "" or _valid_sha40(prewrite_blob)) else "",
        "authorization_id": authorization_id if isinstance(authorization_id, str) and AUTH_ID_RE.fullmatch(authorization_id) is not None else "",
        "write_authorization_contract_sha256": contract_digest,
        "exact_execution_lineage_match": ready,
        "target_metadata_safe": branch_safe and path_safe,
        "prewrite_expectation_valid": prewrite_valid,
        "owner_authorization_state": "NOT_GRANTED",
        "verified": False,
        "durable_identity_bound": False,
        "proposal_materialized": False,
        "binding_receipt_persisted": False,
        "write_authorized": False,
        "compiler_execution_authorized": False,
        "build_authorized": False,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-receipt", required=True)
    parser.add_argument("--authorization-contract", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        source = json.loads(args.source_receipt)
        contract = json.loads(args.authorization_contract)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": "INVALID_JSON", "detail": str(exc)}, sort_keys=True))
        return 2
    receipt = evaluate(source, contract)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["decision"] == "WRITE_AUTHORIZATION_CONTRACT_READY_ONLY" else 1


if __name__ == "__main__":
    sys.exit(main())
