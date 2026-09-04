#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any, Iterable

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUEST_KEYS = {
    "schema_version",
    "work_unit_id",
    "source_envelope_work_unit",
    "proposal_sha256",
    "proposal_byte_count",
}
ENVELOPE_KEYS = {
    "schema_version",
    "work_unit_id",
    "source_validator_work_unit",
    "classification",
    "reasons",
    "proposal_sha256",
    "proposal_byte_count",
    "exact_utf8_bytes",
    "newline_normalization",
    "installer_definition_identity_bound",
    "materialization_authorized",
    "build_authorized",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _valid_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def evaluate(envelope: Any, request: Any) -> dict[str, Any]:
    reasons: list[str] = []

    if not isinstance(envelope, dict):
        reasons.append("INVALID_ENVELOPE_TYPE")
        envelope = {}
    if set(envelope) != ENVELOPE_KEYS:
        reasons.append("INVALID_ENVELOPE_KEYS")
    if envelope.get("schema_version") != 1:
        reasons.append("INVALID_ENVELOPE_SCHEMA_VERSION")
    if envelope.get("work_unit_id") != "PIPE-WU-189":
        reasons.append("INVALID_ENVELOPE_WORK_UNIT")
    if envelope.get("source_validator_work_unit") != "PIPE-WU-188":
        reasons.append("INVALID_ENVELOPE_VALIDATOR_SOURCE")
    if envelope.get("classification") != "ADMITTED":
        reasons.append("ENVELOPE_NOT_ADMITTED")
    if envelope.get("exact_utf8_bytes") is not True:
        reasons.append("ENVELOPE_NOT_EXACT_UTF8")
    if envelope.get("newline_normalization") is not False:
        reasons.append("ENVELOPE_NEWLINE_NORMALIZATION_INVALID")
    for key in ("installer_definition_identity_bound", "materialization_authorized", "build_authorized"):
        if envelope.get(key) is not False:
            reasons.append("ENVELOPE_AUTHORITY_ESCALATION")
            break

    envelope_sha = envelope.get("proposal_sha256")
    envelope_count = envelope.get("proposal_byte_count")
    if not isinstance(envelope_sha, str) or SHA256_RE.fullmatch(envelope_sha) is None:
        reasons.append("INVALID_ENVELOPE_PROPOSAL_SHA256")
    if not _valid_count(envelope_count):
        reasons.append("INVALID_ENVELOPE_PROPOSAL_BYTE_COUNT")

    if not isinstance(request, dict):
        reasons.append("INVALID_REQUEST_TYPE")
        request = {}
    if set(request) != REQUEST_KEYS:
        reasons.append("INVALID_REQUEST_KEYS")
    if request.get("schema_version") != 1:
        reasons.append("INVALID_REQUEST_SCHEMA_VERSION")
    if request.get("work_unit_id") != "PIPE-WU-190":
        reasons.append("INVALID_REQUEST_WORK_UNIT")
    if request.get("source_envelope_work_unit") != "PIPE-WU-189":
        reasons.append("INVALID_REQUEST_ENVELOPE_SOURCE")

    request_sha = request.get("proposal_sha256")
    request_count = request.get("proposal_byte_count")
    if not isinstance(request_sha, str) or SHA256_RE.fullmatch(request_sha) is None:
        reasons.append("INVALID_REQUEST_PROPOSAL_SHA256")
    if not _valid_count(request_count):
        reasons.append("INVALID_REQUEST_PROPOSAL_BYTE_COUNT")
    if isinstance(request_sha, str) and isinstance(envelope_sha, str) and request_sha != envelope_sha:
        reasons.append("PROPOSAL_SHA256_MISMATCH")
    if _valid_count(request_count) and _valid_count(envelope_count) and request_count != envelope_count:
        reasons.append("PROPOSAL_BYTE_COUNT_MISMATCH")

    request_digest = hashlib.sha256(_canonical_bytes(request)).hexdigest()
    reasons = sorted(set(reasons))
    ready = not reasons

    safe_sha = request_sha if isinstance(request_sha, str) and SHA256_RE.fullmatch(request_sha) else "0" * 64
    safe_count = request_count if _valid_count(request_count) else 0
    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-190",
        "source_envelope_work_unit": "PIPE-WU-189",
        "decision": "READY_ONLY" if ready else "BLOCKED",
        "reasons": reasons,
        "proposal_sha256": safe_sha,
        "proposal_byte_count": safe_count,
        "binding_request_sha256": request_digest,
        "exact_identity_match": ready,
        "verified": False,
        "durable_identity_bound": False,
        "proposal_materialized": False,
        "compiler_execution_authorized": False,
        "build_authorized": False,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WU190 installer-definition identity binding request readiness evaluator")
    parser.add_argument("--envelope-json", required=True, help="WU189 proposal envelope JSON supplied directly")
    parser.add_argument("--request-json", required=True, help="WU190 binding request JSON supplied directly")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        envelope = json.loads(args.envelope_json)
        request = json.loads(args.request_json)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": "INVALID_JSON", "detail": str(exc)}, sort_keys=True))
        return 2
    receipt = evaluate(envelope, request)
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=False))
    return 0 if receipt["decision"] == "READY_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
