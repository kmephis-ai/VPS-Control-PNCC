#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any, Iterable

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_KEYS = {
    "schema_version",
    "work_unit_id",
    "source_envelope_work_unit",
    "decision",
    "reasons",
    "proposal_sha256",
    "proposal_byte_count",
    "binding_request_sha256",
    "exact_identity_match",
    "verified",
    "durable_identity_bound",
    "proposal_materialized",
    "compiler_execution_authorized",
    "build_authorized",
}
INTENT_KEYS = {
    "schema_version",
    "work_unit_id",
    "source_binding_request_work_unit",
    "proposal_sha256",
    "proposal_byte_count",
    "binding_request_sha256",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _valid_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def evaluate(source_receipt: Any, transaction_intent: Any) -> dict[str, Any]:
    reasons: list[str] = []

    if not isinstance(source_receipt, dict):
        reasons.append("INVALID_SOURCE_RECEIPT_TYPE")
        source_receipt = {}
    if set(source_receipt) != SOURCE_KEYS:
        reasons.append("INVALID_SOURCE_RECEIPT_KEYS")
    if source_receipt.get("schema_version") != 1:
        reasons.append("INVALID_SOURCE_RECEIPT_SCHEMA_VERSION")
    if source_receipt.get("work_unit_id") != "PIPE-WU-190":
        reasons.append("INVALID_SOURCE_RECEIPT_WORK_UNIT")
    if source_receipt.get("source_envelope_work_unit") != "PIPE-WU-189":
        reasons.append("INVALID_SOURCE_RECEIPT_ENVELOPE_SOURCE")
    if source_receipt.get("decision") != "READY_ONLY":
        reasons.append("SOURCE_RECEIPT_NOT_READY_ONLY")
    if source_receipt.get("reasons") != []:
        reasons.append("SOURCE_RECEIPT_REASONS_NOT_EMPTY")
    if source_receipt.get("exact_identity_match") is not True:
        reasons.append("SOURCE_RECEIPT_IDENTITY_NOT_EXACT")
    for key in (
        "verified",
        "durable_identity_bound",
        "proposal_materialized",
        "compiler_execution_authorized",
        "build_authorized",
    ):
        if source_receipt.get(key) is not False:
            reasons.append("SOURCE_RECEIPT_AUTHORITY_ESCALATION")
            break

    source_sha = source_receipt.get("proposal_sha256")
    source_count = source_receipt.get("proposal_byte_count")
    source_binding = source_receipt.get("binding_request_sha256")
    if not _valid_sha(source_sha):
        reasons.append("INVALID_SOURCE_PROPOSAL_SHA256")
    if not _valid_count(source_count):
        reasons.append("INVALID_SOURCE_PROPOSAL_BYTE_COUNT")
    if not _valid_sha(source_binding):
        reasons.append("INVALID_SOURCE_BINDING_REQUEST_SHA256")

    if not isinstance(transaction_intent, dict):
        reasons.append("INVALID_TRANSACTION_INTENT_TYPE")
        transaction_intent = {}
    if set(transaction_intent) != INTENT_KEYS:
        reasons.append("INVALID_TRANSACTION_INTENT_KEYS")
    if transaction_intent.get("schema_version") != 1:
        reasons.append("INVALID_TRANSACTION_INTENT_SCHEMA_VERSION")
    if transaction_intent.get("work_unit_id") != "PIPE-WU-191":
        reasons.append("INVALID_TRANSACTION_INTENT_WORK_UNIT")
    if transaction_intent.get("source_binding_request_work_unit") != "PIPE-WU-190":
        reasons.append("INVALID_TRANSACTION_INTENT_SOURCE")

    intent_sha = transaction_intent.get("proposal_sha256")
    intent_count = transaction_intent.get("proposal_byte_count")
    intent_binding = transaction_intent.get("binding_request_sha256")
    if not _valid_sha(intent_sha):
        reasons.append("INVALID_TRANSACTION_INTENT_PROPOSAL_SHA256")
    if not _valid_count(intent_count):
        reasons.append("INVALID_TRANSACTION_INTENT_PROPOSAL_BYTE_COUNT")
    if not _valid_sha(intent_binding):
        reasons.append("INVALID_TRANSACTION_INTENT_BINDING_REQUEST_SHA256")
    if _valid_sha(intent_sha) and _valid_sha(source_sha) and intent_sha != source_sha:
        reasons.append("PROPOSAL_SHA256_MISMATCH")
    if _valid_count(intent_count) and _valid_count(source_count) and intent_count != source_count:
        reasons.append("PROPOSAL_BYTE_COUNT_MISMATCH")
    if _valid_sha(intent_binding) and _valid_sha(source_binding) and intent_binding != source_binding:
        reasons.append("BINDING_REQUEST_SHA256_MISMATCH")

    intent_digest = hashlib.sha256(_canonical_bytes(transaction_intent)).hexdigest()
    reasons = sorted(set(reasons))
    ready = not reasons

    safe_sha = intent_sha if _valid_sha(intent_sha) else "0" * 64
    safe_count = intent_count if _valid_count(intent_count) else 0
    safe_binding = intent_binding if _valid_sha(intent_binding) else "0" * 64
    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-191",
        "source_binding_request_work_unit": "PIPE-WU-190",
        "decision": "TRANSACTION_READY_ONLY" if ready else "BLOCKED",
        "reasons": reasons,
        "proposal_sha256": safe_sha,
        "proposal_byte_count": safe_count,
        "binding_request_sha256": safe_binding,
        "transaction_intent_sha256": intent_digest,
        "exact_request_lineage_match": ready,
        "verified": False,
        "durable_identity_bound": False,
        "proposal_materialized": False,
        "binding_receipt_persisted": False,
        "compiler_execution_authorized": False,
        "build_authorized": False,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-receipt", required=True)
    parser.add_argument("--transaction-intent", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        source = json.loads(args.source_receipt)
        intent = json.loads(args.transaction_intent)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": "INVALID_JSON", "detail": str(exc)}, sort_keys=True))
        return 2
    receipt = evaluate(source, intent)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["decision"] == "TRANSACTION_READY_ONLY" else 1


if __name__ == "__main__":
    sys.exit(main())
