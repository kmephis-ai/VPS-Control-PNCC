#!/usr/bin/env python3
"""Materialize a provider-bound PNCC runtime qualification request."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


class RequestError(RuntimeError):
    pass


SHA40_RX = re.compile(r"^[0-9a-f]{40}$")
SHA256_RX = re.compile(r"^[0-9a-f]{64}$")
STABLE_CANDIDATE_RX = re.compile(r"^PNCC-V(?P<version>7\.0\.[0-9]+)-(?P<suffix>[0-9A-F]{12})$")

REQUIRED_SCOPES = [
    "WINDOWS_BASELINE",
    "PROCESS_OWNERSHIP_BASELINE",
    "WATCHDOG_LIFECYCLE",
    "PROXIFIER_DESCENDANT_CLEANUP",
    "PRIMARY_AUTO_1081",
    "RESERVE_MANUAL_1080",
    "CREDENTIAL_HOSTKEY",
    "NETWORK_QUALIFICATION",
    "ROLLBACK_IDENTITY",
]

EXPECTED_INVARIANTS = {
    "primary_auto_port": 1081,
    "reserve_manual_port": 1080,
    "reserve_manual_lifecycle": "MANUAL_ONLY",
    "v6_3_1_sha256": "385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e",
    "putty_password_argument": "-pwfile",
    "plaintext_pw_allowed": False,
    "hostkey_verification_disable_allowed": False,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def positive_int(raw: str, field: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise RequestError(f"{field} must be an integer") from exc
    if value <= 0:
        raise RequestError(f"{field} must be positive")
    return value


def build_request(
    manifest: dict[str, Any],
    provider_artifact_id: int,
    provider_artifact_digest: str,
    provider_build_run_id: int,
    origin_work_unit_id: str,
) -> dict[str, Any]:
    if manifest.get("contract_id") != "PNCC_CANDIDATE_ARTIFACT_TRUTH_V1":
        raise RequestError("unexpected candidate manifest contract")
    candidate_id = manifest.get("candidate_id")
    match = STABLE_CANDIDATE_RX.fullmatch(candidate_id or "")
    if not match:
        raise RequestError(f"Stable 7.0.x candidate required: {candidate_id}")

    source = manifest.get("source")
    artifact = manifest.get("artifact")
    runtime = manifest.get("runtime")
    build = manifest.get("build")
    if not isinstance(source, dict) or not isinstance(artifact, dict) or not isinstance(runtime, dict) or not isinstance(build, dict):
        raise RequestError("candidate manifest missing source/artifact/runtime/build objects")

    source_sha = source.get("commit_sha")
    if not isinstance(source_sha, str) or not SHA40_RX.fullmatch(source_sha):
        raise RequestError("invalid source commit SHA")
    if match.group("suffix") != source_sha[:12].upper():
        raise RequestError("candidate id/source SHA mismatch")
    if source.get("repository") != "kmephis-ai/VPS-Control-PNCC" or source.get("ref") != "refs/heads/main":
        raise RequestError("request requires protected-main candidate provenance")

    version = match.group("version")
    filename = artifact.get("filename")
    artifact_sha256 = artifact.get("sha256")
    artifact_size = artifact.get("size_bytes")
    expected_filename = f"VPS-Control-v{version}.zip"
    if filename != expected_filename:
        raise RequestError(f"unexpected Stable artifact filename: {filename}; expected {expected_filename}")
    if not isinstance(artifact_sha256, str) or not SHA256_RX.fullmatch(artifact_sha256):
        raise RequestError("invalid artifact SHA-256")
    if not isinstance(artifact_size, int) or isinstance(artifact_size, bool) or artifact_size <= 0:
        raise RequestError("invalid artifact size")
    if runtime.get("qualification_state") != "NOT_VERIFIED" or runtime.get("promotion_eligible") is not False:
        raise RequestError("candidate must be unqualified and non-promotable")
    if manifest.get("provenance", {}).get("runtime_authority") is not False:
        raise RequestError("candidate manifest must not carry runtime authority")

    manifest_run_id = build.get("run_id")
    if manifest_run_id != provider_build_run_id:
        raise RequestError(
            f"provider build run mismatch: manifest={manifest_run_id} provider={provider_build_run_id}"
        )
    if not SHA256_RX.fullmatch(provider_artifact_digest):
        raise RequestError("provider artifact digest must be lowercase 64-hex SHA-256")
    if not re.fullmatch(r"^PIPE-WU-[0-9]+$", origin_work_unit_id):
        raise RequestError("invalid origin work unit id")

    suffix = match.group("suffix")
    return {
        "schema_version": 1,
        "contract_id": "PNCC_RUNTIME_QUALIFICATION_REQUEST_V1",
        "request_id": f"PNCC-RQ-V{version}-{suffix}",
        "origin_work_unit_id": origin_work_unit_id,
        "candidate": {
            "candidate_id": candidate_id,
            "source_sha": source_sha,
            "artifact_filename": filename,
            "artifact_sha256": artifact_sha256,
            "artifact_size_bytes": artifact_size,
            "provider_artifact_id": provider_artifact_id,
            "provider_artifact_digest": provider_artifact_digest,
            "provider_build_run_id": provider_build_run_id,
        },
        "required_scopes": list(REQUIRED_SCOPES),
        "expected_invariants": dict(EXPECTED_INVARIANTS),
        "state": "RUNTIME_PENDING",
        "runtime_authority": False,
        "promotion_eligible": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate provider-bound PNCC runtime qualification request")
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--provider-artifact-id", required=True)
    parser.add_argument("--provider-artifact-digest", required=True)
    parser.add_argument("--provider-build-run-id", required=True)
    parser.add_argument("--origin-work-unit-id", default="PIPE-WU-045")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = load_json(args.candidate_manifest)
        if not isinstance(manifest, dict):
            raise RequestError("candidate manifest object required")
        request = build_request(
            manifest=manifest,
            provider_artifact_id=positive_int(args.provider_artifact_id, "provider artifact id"),
            provider_artifact_digest=args.provider_artifact_digest,
            provider_build_run_id=positive_int(args.provider_build_run_id, "provider build run id"),
            origin_work_unit_id=args.origin_work_unit_id,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
        print(
            "RUNTIME_QUALIFICATION_REQUEST=PASS "
            f"REQUEST_ID={request['request_id']} CANDIDATE_ID={request['candidate']['candidate_id']} "
            f"ARTIFACT_ID={request['candidate']['provider_artifact_id']} "
            "STATE=RUNTIME_PENDING RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
        )
        return 0
    except Exception as exc:
        print(f"RUNTIME_QUALIFICATION_REQUEST=FAIL ERROR={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
