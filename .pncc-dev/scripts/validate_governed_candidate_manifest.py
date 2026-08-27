#!/usr/bin/env python3
"""Strict validator for the first governed PNCC RC14.39 candidate artifact."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

BASE_VALIDATOR_PATH = Path(__file__).with_name("validate_candidate_manifest.py")
SPEC = importlib.util.spec_from_file_location("pncc_candidate_manifest_base", BASE_VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load base Candidate Artifact Truth validator")
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)

REQUIRED_GOVERNED_CHECKS = {
    "repo-integrity", "powershell-static", "truth-contract", "adwf-binding", "pipeline-state",
    "quality-fast", "quality-deep", "candidate-artifact-truth",
    "candidate-build-input-readiness", "canonical-source-admission",
}
EXPECTED_ARTIFACT_FILENAME = "VPS-Control-v7.0.0-rc14.39.zip"
EXPECTED_CANDIDATE_PREFIX = "PNCC-RC14.39-"


def validate_governed_manifest(manifest: Any) -> list[str]:
    errors = list(BASE.validate_manifest(manifest))
    if not isinstance(manifest, dict):
        return errors
    if manifest.get("artifact_role") != "RUNTIME_CANDIDATE":
        errors.append("GOVERNED:ARTIFACT_ROLE_RUNTIME_CANDIDATE_REQUIRED")
    candidate_id = manifest.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id.startswith(EXPECTED_CANDIDATE_PREFIX):
        errors.append("GOVERNED:CANDIDATE_ID_RC14_39_REQUIRED")
    source = manifest.get("source")
    if isinstance(source, dict):
        if source.get("repository") != "kmephis-ai/VPS-Control-PNCC": errors.append("GOVERNED:REPOSITORY_INVALID")
        if source.get("ref") != "refs/heads/main": errors.append("GOVERNED:PROTECTED_MAIN_REF_REQUIRED")
        if source.get("identity_semantic") != "EXACT_SOURCE_COMMIT": errors.append("GOVERNED:EXACT_SOURCE_COMMIT_REQUIRED")
        if source.get("path") != "src/windows-v7": errors.append("GOVERNED:CANONICAL_WINDOWS_V7_SOURCE_REQUIRED")
    artifact = manifest.get("artifact")
    if isinstance(artifact, dict) and artifact.get("filename") != EXPECTED_ARTIFACT_FILENAME:
        errors.append("GOVERNED:RC14_39_ARTIFACT_FILENAME_REQUIRED")
    build = manifest.get("build")
    if isinstance(build, dict):
        if build.get("workflow") != "candidate-builder": errors.append("GOVERNED:CANDIDATE_BUILDER_WORKFLOW_REQUIRED")
        if build.get("job_name") != "candidate-builder-main": errors.append("GOVERNED:CANDIDATE_BUILDER_MAIN_JOB_REQUIRED")
        if build.get("builder") != "GITHUB_HOSTED": errors.append("GOVERNED:GITHUB_HOSTED_BUILDER_REQUIRED")
    checks = manifest.get("engineering_checks")
    names: set[str] = set()
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict) and isinstance(check.get("name"), str): names.add(check["name"])
    missing = sorted(REQUIRED_GOVERNED_CHECKS - names)
    if missing: errors.append("GOVERNED:MISSING_ENGINEERING_CHECKS:" + ",".join(missing))
    provenance = manifest.get("provenance")
    if isinstance(provenance, dict):
        if provenance.get("artifact_origin") != "BUILD_OUTPUT": errors.append("GOVERNED:BUILD_OUTPUT_ORIGIN_REQUIRED")
        if provenance.get("sanitation_state") != "EXACT_BUILD_OUTPUT": errors.append("GOVERNED:EXACT_BUILD_OUTPUT_REQUIRED")
        if provenance.get("attestation_state") != "HOSTED_PROVENANCE_RECORDED": errors.append("GOVERNED:HOSTED_PROVENANCE_REQUIRED")
        if provenance.get("runtime_authority") is not False: errors.append("GOVERNED:RUNTIME_AUTHORITY_FORBIDDEN")
    runtime = manifest.get("runtime")
    if isinstance(runtime, dict):
        if runtime.get("qualification_state") != "NOT_VERIFIED": errors.append("GOVERNED:RUNTIME_MUST_BE_NOT_VERIFIED")
        if runtime.get("promotion_eligible") is not False: errors.append("GOVERNED:PROMOTION_ELIGIBLE_FORBIDDEN")
        if runtime.get("evidence_ref") is not None: errors.append("GOVERNED:RUNTIME_EVIDENCE_FORBIDDEN")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate governed PNCC RC14.39 candidate manifest")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"GOVERNED_CANDIDATE_MANIFEST=FAIL PARSE_ERROR={exc}")
        return 1
    errors = validate_governed_manifest(manifest)
    if errors:
        print("GOVERNED_CANDIDATE_MANIFEST=FAIL")
        for error in errors: print(f"ERROR={error}")
        return 1
    print(
        "GOVERNED_CANDIDATE_MANIFEST=PASS "
        f"CANDIDATE_ID={manifest['candidate_id']} SOURCE_SHA={manifest['source']['commit_sha']} "
        f"ARTIFACT_SHA256={manifest['artifact']['sha256']} ENGINEERING_CHECKS={len(REQUIRED_GOVERNED_CHECKS)} "
        "RUNTIME=NOT_VERIFIED PROMOTION_ELIGIBLE=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
