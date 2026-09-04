#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any, Iterable

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+\.iss$")
SOURCE_KEYS = {
    "schema_version",
    "work_unit_id",
    "source_binding_request_work_unit",
    "decision",
    "reasons",
    "proposal_sha256",
    "proposal_byte_count",
    "binding_request_sha256",
    "transaction_intent_sha256",
    "exact_request_lineage_match",
    "verified",
    "durable_identity_bound",
    "proposal_materialized",
    "binding_receipt_persisted",
    "compiler_execution_authorized",
    "build_authorized",
}
REQUEST_KEYS = {
    "schema_version",
    "work_unit_id",
    "source_transaction_work_unit",
    "proposal_sha256",
    "proposal_byte_count",
    "binding_request_sha256",
    "transaction_intent_sha256",
    "target_path",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


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


def evaluate(source_receipt: Any, authorization_request: Any) -> dict[str, Any]:
    reasons: list[str] = []

    if not isinstance(source_receipt, dict):
        reasons.append("INVALID_SOURCE_RECEIPT_TYPE")
        source_receipt = {}
    if set(source_receipt) != SOURCE_KEYS:
        reasons.append("INVALID_SOURCE_RECEIPT_KEYS")
    if source_receipt.get("schema_version") != 1:
        reasons.append("INVALID_SOURCE_RECEIPT_SCHEMA_VERSION")
    if source_receipt.get("work_unit_id") != "PIPE-WU-191":
        reasons.append("INVALID_SOURCE_RECEIPT_WORK_UNIT")
    if source_receipt.get("source_binding_request_work_unit") != "PIPE-WU-190":
        reasons.append("INVALID_SOURCE_RECEIPT_SOURCE")
    if source_receipt.get("decision") != "TRANSACTION_READY_ONLY":
        reasons.append("SOURCE_RECEIPT_NOT_TRANSACTION_READY_ONLY")
    if source_receipt.get("reasons") != []:
        reasons.append("SOURCE_RECEIPT_REASONS_NOT_EMPTY")
    if source_receipt.get("exact_request_lineage_match") is not True:
        reasons.append("SOURCE_RECEIPT_LINEAGE_NOT_EXACT")
    for key in (
        "verified",
        "durable_identity_bound",
        "proposal_materialized",
        "binding_receipt_persisted",
        "compiler_execution_authorized",
        "build_authorized",
    ):
        if source_receipt.get(key) is not False:
            reasons.append("SOURCE_RECEIPT_AUTHORITY_ESCALATION")
            break

    source_sha = source_receipt.get("proposal_sha256")
    source_count = source_receipt.get("proposal_byte_count")
    source_binding = source_receipt.get("binding_request_sha256")
    source_transaction = source_receipt.get("transaction_intent_sha256")
    if not _valid_sha(source_sha):
        reasons.append("INVALID_SOURCE_PROPOSAL_SHA256")
    if not _valid_count(source_count):
        reasons.append("INVALID_SOURCE_PROPOSAL_BYTE_COUNT")
    if not _valid_sha(source_binding):
        reasons.append("INVALID_SOURCE_BINDING_REQUEST_SHA256")
    if not _valid_sha(source_transaction):
        reasons.append("INVALID_SOURCE_TRANSACTION_INTENT_SHA256")

    if not isinstance(authorization_request, dict):
        reasons.append("INVALID_AUTHORIZATION_REQUEST_TYPE")
        authorization_request = {}
    if set(authorization_request) != REQUEST_KEYS:
        reasons.append("INVALID_AUTHORIZATION_REQUEST_KEYS")
    if authorization_request.get("schema_version") != 1:
        reasons.append("INVALID_AUTHORIZATION_REQUEST_SCHEMA_VERSION")
    if authorization_request.get("work_unit_id") != "PIPE-WU-192":
        reasons.append("INVALID_AUTHORIZATION_REQUEST_WORK_UNIT")
    if authorization_request.get("source_transaction_work_unit") != "PIPE-WU-191":
        reasons.append("INVALID_AUTHORIZATION_REQUEST_SOURCE")

    request_sha = authorization_request.get("proposal_sha256")
    request_count = authorization_request.get("proposal_byte_count")
    request_binding = authorization_request.get("binding_request_sha256")
    request_transaction = authorization_request.get("transaction_intent_sha256")
    target_path = authorization_request.get("target_path")

    if not _valid_sha(request_sha):
        reasons.append("INVALID_AUTHORIZATION_REQUEST_PROPOSAL_SHA256")
    if not _valid_count(request_count):
        reasons.append("INVALID_AUTHORIZATION_REQUEST_PROPOSAL_BYTE_COUNT")
    if not _valid_sha(request_binding):
        reasons.append("INVALID_AUTHORIZATION_REQUEST_BINDING_REQUEST_SHA256")
    if not _valid_sha(request_transaction):
        reasons.append("INVALID_AUTHORIZATION_REQUEST_TRANSACTION_INTENT_SHA256")
    target_safe = _safe_target_path(target_path)
    if not target_safe:
        reasons.append("UNSAFE_TARGET_PATH_METADATA")

    if _valid_sha(request_sha) and _valid_sha(source_sha) and request_sha != source_sha:
        reasons.append("PROPOSAL_SHA256_MISMATCH")
    if _valid_count(request_count) and _valid_count(source_count) and request_count != source_count:
        reasons.append("PROPOSAL_BYTE_COUNT_MISMATCH")
    if _valid_sha(request_binding) and _valid_sha(source_binding) and request_binding != source_binding:
        reasons.append("BINDING_REQUEST_SHA256_MISMATCH")
    if _valid_sha(request_transaction) and _valid_sha(source_transaction) and request_transaction != source_transaction:
        reasons.append("TRANSACTION_INTENT_SHA256_MISMATCH")

    authorization_digest = hashlib.sha256(_canonical_bytes(authorization_request)).hexdigest()
    reasons = sorted(set(reasons))
    ready = not reasons

    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-192",
        "source_transaction_work_unit": "PIPE-WU-191",
        "decision": "EXECUTION_AUTHORIZATION_READY_ONLY" if ready else "BLOCKED",
        "reasons": reasons,
        "proposal_sha256": request_sha if _valid_sha(request_sha) else "0" * 64,
        "proposal_byte_count": request_count if _valid_count(request_count) else 0,
        "binding_request_sha256": request_binding if _valid_sha(request_binding) else "0" * 64,
        "transaction_intent_sha256": request_transaction if _valid_sha(request_transaction) else "0" * 64,
        "target_path": target_path if target_safe else "",
        "execution_authorization_request_sha256": authorization_digest,
        "exact_transaction_lineage_match": ready,
        "target_metadata_safe": target_safe,
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
    parser.add_argument("--authorization-request", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        source = json.loads(args.source_receipt)
        request = json.loads(args.authorization_request)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": "INVALID_JSON", "detail": str(exc)}, sort_keys=True))
        return 2
    receipt = evaluate(source, request)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["decision"] == "EXECUTION_AUTHORIZATION_READY_ONLY" else 1


if __name__ == "__main__":
    sys.exit(main())
