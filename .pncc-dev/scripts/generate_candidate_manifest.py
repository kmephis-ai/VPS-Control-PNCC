#!/usr/bin/env python3
"""Generate PNCC Candidate Artifact Truth manifest for protected-main build."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ManifestError(RuntimeError):
    pass


CANDIDATE_VERSION_RX = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-rc[0-9]+\.[0-9]+)?$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def candidate_id_for(version: str, source_sha: str) -> str:
    if version == "7.0.0":
        return f"PNCC-V7.0.0-{source_sha[:12].upper()}"
    if version == "7.0.0-rc14.39":
        return f"PNCC-RC14.39-{source_sha[:12].upper()}"
    raise ManifestError(f"unsupported governed candidate version: {version}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate governed PNCC candidate manifest")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--build-evidence", type=Path, required=True)
    parser.add_argument("--engineering-checks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args(argv)
    try:
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        ref = os.environ.get("GITHUB_REF", "")
        event_name = os.environ.get("GITHUB_EVENT_NAME", "")
        workflow = os.environ.get("GITHUB_WORKFLOW", "")
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
        job = os.environ.get("GITHUB_JOB", "")
        if repository != "kmephis-ai/VPS-Control-PNCC":
            raise ManifestError(f"unexpected repository: {repository}")
        if ref != "refs/heads/main" or event_name != "push":
            raise ManifestError(f"governed candidate manifest requires protected-main push: ref={ref} event={event_name}")
        if workflow != "candidate-builder" or job != "candidate-builder-main":
            raise ManifestError(f"unexpected workflow/job: {workflow}/{job}")
        if len(args.source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in args.source_sha):
            raise ManifestError("invalid source SHA")
        evidence = load_json(args.build_evidence)
        checks = load_json(args.engineering_checks)
        if not isinstance(evidence, dict):
            raise ManifestError("build evidence object required")
        if not isinstance(checks, list):
            raise ManifestError("engineering checks array required")
        if evidence.get("source_commit_sha") != args.source_sha:
            raise ManifestError("build evidence source SHA mismatch")
        if evidence.get("source_root") != "src/windows-v7":
            raise ManifestError("unexpected source root")
        repro = evidence.get("reproducibility")
        if not isinstance(repro, dict) or repro.get("byte_identical") is not True or repro.get("independent_builds") != 2:
            raise ManifestError("two-build reproducibility proof required")
        artifact_record = evidence.get("artifact")
        if not isinstance(artifact_record, dict):
            raise ManifestError("artifact evidence missing")
        if args.artifact.name != artifact_record.get("filename"):
            raise ManifestError("artifact filename mismatch")
        artifact_bytes = args.artifact.read_bytes()
        sha = hashlib.sha256(artifact_bytes).hexdigest()
        if sha != artifact_record.get("sha256") or len(artifact_bytes) != artifact_record.get("size_bytes"):
            raise ManifestError("artifact bytes/evidence mismatch")
        candidate_version = evidence.get("candidate_version")
        if not isinstance(candidate_version, str) or not CANDIDATE_VERSION_RX.fullmatch(candidate_version):
            raise ManifestError(f"invalid candidate version: {candidate_version}")
        expected_filename = f"VPS-Control-v{candidate_version}.zip"
        if args.artifact.name != expected_filename:
            raise ManifestError(f"candidate version/artifact filename mismatch: expected {expected_filename}")
        candidate_id = candidate_id_for(candidate_version, args.source_sha)
        manifest = {
            "schema_version": 1,
            "contract_id": "PNCC_CANDIDATE_ARTIFACT_TRUTH_V1",
            "candidate_id": candidate_id,
            "artifact_role": "RUNTIME_CANDIDATE",
            "source": {
                "repository": repository, "commit_sha": args.source_sha, "ref": ref,
                "identity_semantic": "EXACT_SOURCE_COMMIT", "path": "src/windows-v7",
            },
            "artifact": {"filename": args.artifact.name, "sha256": sha, "size_bytes": len(artifact_bytes)},
            "build": {
                "workflow": workflow, "run_id": int(run_id), "run_attempt": int(run_attempt),
                "job_name": job,
                "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "builder": "GITHUB_HOSTED",
            },
            "tool_versions": {
                "python": sys.version.split()[0], "zipfile": "stdlib",
                "builder_contract": "PNCC_DETERMINISTIC_CANDIDATE_BUILD_V1",
                "candidate_version": candidate_version,
            },
            "engineering_checks": checks,
            "provenance": {
                "artifact_origin": "BUILD_OUTPUT", "sanitation_state": "EXACT_BUILD_OUTPUT",
                "attestation_state": "HOSTED_PROVENANCE_RECORDED", "runtime_authority": False,
            },
            "runtime": {"qualification_state": "NOT_VERIFIED", "evidence_ref": None, "promotion_eligible": False},
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
        print(
            "CANDIDATE_MANIFEST_GENERATED=PASS "
            f"CANDIDATE_ID={manifest['candidate_id']} VERSION={candidate_version} ARTIFACT_SHA256={sha} "
            "RUNTIME=NOT_VERIFIED PROMOTION_ELIGIBLE=false"
        )
        return 0
    except Exception as exc:
        print(f"CANDIDATE_MANIFEST_GENERATED=FAIL ERROR={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
