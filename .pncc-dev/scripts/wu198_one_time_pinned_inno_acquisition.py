#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / ".pncc-dev/contracts/wave6-wu198-one-time-pinned-inno-acquisition.json"
EXECUTE_RE = re.compile(r"<!--\s*PNCC-WU198-ACQUISITION-EXECUTE\s+schema=1\s+expected_main=([0-9a-f]{40})\s*-->")


def load_contract() -> dict:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    target = contract.get("target") or {}
    boundary = contract.get("execution_boundary") or {}
    authority = contract.get("authority") or {}
    expected_target = {
        "repository": "jrsoftware/issrc",
        "tag": "is-7_1_0",
        "release_id": 369110765,
        "asset_id": 511336600,
        "asset_name": "innosetup-7.1.0-x64.exe",
        "source_url": "https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe",
        "size_bytes": 14304168,
        "sha256": "0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f",
    }
    if contract.get("schema_version") != 1 or contract.get("work_unit_id") != "PIPE-WU-198":
        raise RuntimeError("CONTRACT_IDENTITY_INVALID")
    if target != expected_target:
        raise RuntimeError("TARGET_DRIFT")
    if boundary != {
        "runner_class": "GITHUB_HOSTED",
        "runner_label": "ubuntu-24.04",
        "one_time_only": True,
        "destination_class": "RUNNER_TEMP_EPHEMERAL_ONLY",
        "cache_allowed": False,
        "artifact_upload_allowed": False,
        "persistent_storage_allowed": False,
        "install_allowed": False,
        "execute_allowed": False,
        "build_allowed": False,
        "release_allowed": False,
    }:
        raise RuntimeError("EXECUTION_BOUNDARY_DRIFT")
    allowed_true = {"network_acquisition"}
    if {k for k, v in authority.items() if v is True} != allowed_true:
        raise RuntimeError("AUTHORITY_EXPANSION")
    return contract


def validate_execution_marker(issue_body: str, main_sha: str) -> None:
    matches = EXECUTE_RE.findall(issue_body or "")
    if len(matches) != 1:
        raise RuntimeError("EXECUTION_MARKER_INVALID")
    if matches[0] != main_sha:
        raise RuntimeError("EXPECTED_MAIN_MISMATCH")


def stream_to_file_and_hash(response, destination: pathlib.Path) -> tuple[int, str]:
    total = 0
    digest = hashlib.sha256()
    with destination.open("xb") as fh:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
            fh.write(chunk)
    return total, digest.hexdigest()


def verify_observation(observed_size: int, observed_sha256: str, target: dict) -> None:
    if observed_size != target["size_bytes"]:
        raise RuntimeError("SIZE_MISMATCH")
    if observed_sha256.lower() != target["sha256"]:
        raise RuntimeError("SHA256_MISMATCH")


def acquire_once(contract: dict, runner_temp: pathlib.Path, main_sha: str) -> dict:
    target = contract["target"]
    runner_temp = runner_temp.resolve()
    runner_temp.mkdir(parents=True, exist_ok=True)
    destination = runner_temp / target["asset_name"]
    if destination.exists():
        raise RuntimeError("DESTINATION_PREEXISTS")

    observed_size = None
    observed_sha = None
    final_url = None
    try:
        request = urllib.request.Request(
            target["source_url"],
            headers={"User-Agent": "pncc-wu198-one-time-acquisition"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            final_url = response.geturl()
            observed_size, observed_sha = stream_to_file_and_hash(response, destination)
        verify_observation(observed_size, observed_sha, target)
    finally:
        if destination.exists():
            destination.unlink()

    if destination.exists():
        raise RuntimeError("ASSET_NOT_DELETED")

    return {
        "schema_version": 1,
        "role": "INSTALLER_COMPILER_ACQUISITION_PROVENANCE_RECEIPT",
        "work_unit_id": "PIPE-WU-198",
        "source_repository": target["repository"],
        "tag": target["tag"],
        "release_id": target["release_id"],
        "asset_id": target["asset_id"],
        "asset_name": target["asset_name"],
        "source_url": target["source_url"],
        "resolved_url": final_url,
        "expected_size_bytes": target["size_bytes"],
        "observed_size_bytes": observed_size,
        "expected_sha256": target["sha256"],
        "observed_sha256": observed_sha,
        "identity_verified": True,
        "runner_class": "GITHUB_HOSTED",
        "workspace_class": "RUNNER_TEMP_EPHEMERAL_ONLY",
        "installed": False,
        "executed": False,
        "built": False,
        "artifact_uploaded": False,
        "cache_written": False,
        "asset_persisted_after_job": False,
        "main_sha": main_sha,
        "acquired_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    try:
        contract = load_contract()
        issue_body = os.environ.get("PNCC_ISSUE_BODY", "")
        main_sha = os.environ.get("PNCC_MAIN_SHA", "")
        runner_temp = os.environ.get("RUNNER_TEMP", "")
        if not re.fullmatch(r"[0-9a-f]{40}", main_sha):
            raise RuntimeError("MAIN_SHA_INVALID")
        if not runner_temp:
            raise RuntimeError("RUNNER_TEMP_MISSING")
        if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
            raise RuntimeError("GITHUB_HOSTED_RUNNER_REQUIRED")
        validate_execution_marker(issue_body, main_sha)
        receipt = acquire_once(contract, pathlib.Path(runner_temp), main_sha)
        print("PNCC_WU198_PROVENANCE_RECEIPT=" + json.dumps(receipt, separators=(",", ":"), sort_keys=True))
        return 0
    except Exception as exc:
        print("PNCC_WU198_ACQUISITION=BLOCKED")
        print("ERROR=" + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
