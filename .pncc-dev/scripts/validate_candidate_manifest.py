#!/usr/bin/env python3
"""Fail-closed validator for PNCC Candidate Artifact Truth manifest v1.

This module uses Python stdlib only. It validates manifest structure plus
cross-field authority semantics that must not be inferred from hosted CI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

CONTRACT_ID = "PNCC_CANDIDATE_ARTIFACT_TRUTH_V1"
REPOSITORY = "kmephis-ai/VPS-Control-PNCC"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,127}$")

REQUIRED_ENGINEERING_CHECKS = {
    "repo-integrity",
    "powershell-static",
    "truth-contract",
    "adwf-binding",
    "pipeline-state",
    "quality-fast",
    "quality-deep",
}

ROOT_KEYS = {
    "schema_version",
    "contract_id",
    "candidate_id",
    "artifact_role",
    "source",
    "artifact",
    "build",
    "tool_versions",
    "engineering_checks",
    "provenance",
    "runtime",
}
SOURCE_KEYS = {"repository", "commit_sha", "ref", "identity_semantic", "path"}
ARTIFACT_KEYS = {"filename", "sha256", "size_bytes"}
BUILD_KEYS = {"workflow", "run_id", "run_attempt", "job_name", "created_at_utc", "builder"}
CHECK_KEYS = {"name", "conclusion", "subject_sha"}
PROVENANCE_KEYS = {"artifact_origin", "sanitation_state", "attestation_state", "runtime_authority"}
RUNTIME_KEYS = {"qualification_state", "evidence_ref", "promotion_eligible"}

ARTIFACT_ROLES = {"RUNTIME_CANDIDATE", "SYNTHETIC_TEST_FIXTURE"}
IDENTITY_SEMANTICS = {"EXACT_SOURCE_COMMIT", "SYNTHETIC_SOURCE", "SANITIZED_PUBLIC_FIXTURE"}
BUILDERS = {"GITHUB_HOSTED", "SYNTHETIC_TEST"}
ARTIFACT_ORIGINS = {"BUILD_OUTPUT", "SYNTHETIC_FIXTURE", "SANITIZED_PUBLIC_FIXTURE"}
SANITATION_STATES = {"EXACT_BUILD_OUTPUT", "SYNTHETIC", "SANITIZED_PUBLIC"}
ATTESTATION_STATES = {"NOT_ATTESTED", "HOSTED_PROVENANCE_RECORDED"}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_exact_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label}:OBJECT_REQUIRED")
        return False
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        errors.append(f"{label}:MISSING_KEYS:{','.join(missing)}")
    if unknown:
        errors.append(f"{label}:UNKNOWN_KEYS:{','.join(unknown)}")
    return not missing and not unknown


def _require_nonempty_string(value: Any, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}:NONEMPTY_STRING_REQUIRED")
        return False
    return True


def _require_enum(value: Any, allowed: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{label}:INVALID_VALUE")
        return False
    return True


def _validate_utc_timestamp(value: Any, label: str, errors: list[str]) -> None:
    if not _require_nonempty_string(value, label, errors):
        return
    if not value.endswith("Z"):
        errors.append(f"{label}:UTC_Z_REQUIRED")
        return
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        errors.append(f"{label}:INVALID_DATETIME")
        return
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        errors.append(f"{label}:UTC_REQUIRED")


def _validate_relative_path(value: Any, label: str, errors: list[str]) -> str:
    if not _require_nonempty_string(value, label, errors):
        return ""
    text = value.replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or text.startswith("/") or any(part in {"", ".", ".."} for part in path.parts):
        errors.append(f"{label}:SAFE_RELATIVE_PATH_REQUIRED")
        return text
    return text


def validate_manifest(manifest: Any) -> list[str]:
    errors: list[str] = []
    if not _require_exact_keys(manifest, ROOT_KEYS, "ROOT", errors):
        if not isinstance(manifest, dict):
            return errors

    if manifest.get("schema_version") != 1:
        errors.append("ROOT:SCHEMA_VERSION_INVALID")
    if manifest.get("contract_id") != CONTRACT_ID:
        errors.append("ROOT:CONTRACT_ID_INVALID")

    candidate_id = manifest.get("candidate_id")
    if not isinstance(candidate_id, str) or not CANDIDATE_ID.fullmatch(candidate_id):
        errors.append("ROOT:CANDIDATE_ID_INVALID")

    role = manifest.get("artifact_role")
    _require_enum(role, ARTIFACT_ROLES, "ROOT:ARTIFACT_ROLE", errors)

    source = manifest.get("source")
    if _require_exact_keys(source, SOURCE_KEYS, "SOURCE", errors):
        if source.get("repository") != REPOSITORY:
            errors.append("SOURCE:REPOSITORY_INVALID")
        commit_sha = source.get("commit_sha")
        if not isinstance(commit_sha, str) or not SHA40.fullmatch(commit_sha):
            errors.append("SOURCE:COMMIT_SHA_INVALID")
        _require_nonempty_string(source.get("ref"), "SOURCE:REF", errors)
        _require_enum(source.get("identity_semantic"), IDENTITY_SEMANTICS, "SOURCE:IDENTITY_SEMANTIC", errors)
        source_path = _validate_relative_path(source.get("path"), "SOURCE:PATH", errors)
    else:
        commit_sha = None
        source_path = ""

    artifact = manifest.get("artifact")
    if _require_exact_keys(artifact, ARTIFACT_KEYS, "ARTIFACT", errors):
        filename = artifact.get("filename")
        if not _require_nonempty_string(filename, "ARTIFACT:FILENAME", errors):
            filename = ""
        elif "/" in filename or "\\" in filename or filename in {".", ".."}:
            errors.append("ARTIFACT:FILENAME_BASENAME_REQUIRED")
        artifact_sha = artifact.get("sha256")
        if not isinstance(artifact_sha, str) or not SHA256.fullmatch(artifact_sha):
            errors.append("ARTIFACT:SHA256_INVALID")
        size_bytes = artifact.get("size_bytes")
        if not _is_int(size_bytes) or size_bytes <= 0:
            errors.append("ARTIFACT:SIZE_BYTES_POSITIVE_INTEGER_REQUIRED")

    build = manifest.get("build")
    if _require_exact_keys(build, BUILD_KEYS, "BUILD", errors):
        _require_nonempty_string(build.get("workflow"), "BUILD:WORKFLOW", errors)
        _require_nonempty_string(build.get("job_name"), "BUILD:JOB_NAME", errors)
        if not _is_int(build.get("run_id")) or build.get("run_id") <= 0:
            errors.append("BUILD:RUN_ID_POSITIVE_INTEGER_REQUIRED")
        if not _is_int(build.get("run_attempt")) or build.get("run_attempt") <= 0:
            errors.append("BUILD:RUN_ATTEMPT_POSITIVE_INTEGER_REQUIRED")
        _validate_utc_timestamp(build.get("created_at_utc"), "BUILD:CREATED_AT_UTC", errors)
        _require_enum(build.get("builder"), BUILDERS, "BUILD:BUILDER", errors)

    tool_versions = manifest.get("tool_versions")
    if not isinstance(tool_versions, dict) or not tool_versions:
        errors.append("TOOL_VERSIONS:NONEMPTY_OBJECT_REQUIRED")
    else:
        for key, value in sorted(tool_versions.items()):
            if not isinstance(key, str) or not key.strip():
                errors.append("TOOL_VERSIONS:KEY_INVALID")
            if not isinstance(value, str) or not value.strip():
                errors.append(f"TOOL_VERSIONS:{key}:VALUE_INVALID")

    checks = manifest.get("engineering_checks")
    seen_names: set[str] = set()
    present_required: set[str] = set()
    if not isinstance(checks, list):
        errors.append("ENGINEERING_CHECKS:ARRAY_REQUIRED")
    else:
        for index, check in enumerate(checks):
            label = f"ENGINEERING_CHECKS:{index}"
            if not _require_exact_keys(check, CHECK_KEYS, label, errors):
                continue
            name = check.get("name")
            if not _require_nonempty_string(name, f"{label}:NAME", errors):
                continue
            if name in seen_names:
                errors.append(f"ENGINEERING_CHECKS:DUPLICATE_NAME:{name}")
            seen_names.add(name)
            if name in REQUIRED_ENGINEERING_CHECKS:
                present_required.add(name)
            if check.get("conclusion") != "SUCCESS":
                errors.append(f"ENGINEERING_CHECKS:{name}:NON_SUCCESS")
            subject_sha = check.get("subject_sha")
            if not isinstance(subject_sha, str) or not SHA40.fullmatch(subject_sha):
                errors.append(f"ENGINEERING_CHECKS:{name}:SUBJECT_SHA_INVALID")
            elif isinstance(commit_sha, str) and subject_sha != commit_sha:
                errors.append(f"ENGINEERING_CHECKS:{name}:SUBJECT_SHA_MISMATCH")
        missing_checks = sorted(REQUIRED_ENGINEERING_CHECKS - present_required)
        if missing_checks:
            errors.append(f"ENGINEERING_CHECKS:MISSING_REQUIRED:{','.join(missing_checks)}")

    provenance = manifest.get("provenance")
    if _require_exact_keys(provenance, PROVENANCE_KEYS, "PROVENANCE", errors):
        _require_enum(provenance.get("artifact_origin"), ARTIFACT_ORIGINS, "PROVENANCE:ARTIFACT_ORIGIN", errors)
        _require_enum(provenance.get("sanitation_state"), SANITATION_STATES, "PROVENANCE:SANITATION_STATE", errors)
        _require_enum(provenance.get("attestation_state"), ATTESTATION_STATES, "PROVENANCE:ATTESTATION_STATE", errors)
        if provenance.get("runtime_authority") is not False:
            errors.append("PROVENANCE:RUNTIME_AUTHORITY_FORBIDDEN")

    runtime = manifest.get("runtime")
    if _require_exact_keys(runtime, RUNTIME_KEYS, "RUNTIME", errors):
        if runtime.get("qualification_state") != "NOT_VERIFIED":
            errors.append("RUNTIME:QUALIFICATION_MUST_BE_NOT_VERIFIED")
        if runtime.get("evidence_ref") is not None:
            errors.append("RUNTIME:EVIDENCE_REF_FORBIDDEN_WHILE_NOT_VERIFIED")
        if runtime.get("promotion_eligible") is not False:
            errors.append("RUNTIME:PROMOTION_ELIGIBLE_FORBIDDEN")

    if role == "SYNTHETIC_TEST_FIXTURE" and isinstance(source, dict) and isinstance(build, dict) and isinstance(provenance, dict):
        if source.get("identity_semantic") != "SYNTHETIC_SOURCE":
            errors.append("SEMANTICS:SYNTHETIC_SOURCE_IDENTITY_REQUIRED")
        if not source_path.startswith(".pncc-dev/examples/"):
            errors.append("SEMANTICS:SYNTHETIC_SOURCE_PATH_REQUIRED")
        if build.get("builder") != "SYNTHETIC_TEST":
            errors.append("SEMANTICS:SYNTHETIC_BUILDER_REQUIRED")
        if provenance.get("artifact_origin") != "SYNTHETIC_FIXTURE":
            errors.append("SEMANTICS:SYNTHETIC_ARTIFACT_ORIGIN_REQUIRED")
        if provenance.get("sanitation_state") != "SYNTHETIC":
            errors.append("SEMANTICS:SYNTHETIC_SANITATION_STATE_REQUIRED")
        if provenance.get("attestation_state") != "NOT_ATTESTED":
            errors.append("SEMANTICS:SYNTHETIC_ATTESTATION_FORBIDDEN")

    if role == "RUNTIME_CANDIDATE" and isinstance(source, dict) and isinstance(build, dict) and isinstance(provenance, dict):
        normalized_source_path = source_path.lower().rstrip("/")
        if source.get("identity_semantic") != "EXACT_SOURCE_COMMIT":
            errors.append("SEMANTICS:RUNTIME_CANDIDATE_EXACT_SOURCE_REQUIRED")
        if "legacy/v7-rc14.38-sanitized" in normalized_source_path:
            errors.append("SEMANTICS:SANITIZED_RC1438_RUNTIME_CANDIDATE_FORBIDDEN")
        if build.get("builder") != "GITHUB_HOSTED":
            errors.append("SEMANTICS:RUNTIME_CANDIDATE_HOSTED_BUILDER_REQUIRED")
        if provenance.get("artifact_origin") != "BUILD_OUTPUT":
            errors.append("SEMANTICS:RUNTIME_CANDIDATE_BUILD_OUTPUT_REQUIRED")
        if provenance.get("sanitation_state") != "EXACT_BUILD_OUTPUT":
            errors.append("SEMANTICS:RUNTIME_CANDIDATE_EXACT_BUILD_OUTPUT_REQUIRED")

    return errors


def load_manifest(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate PNCC Candidate Artifact Truth manifest v1")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
    except Exception as exc:  # fail closed on parse/read errors
        print(f"CANDIDATE_MANIFEST=FAIL PARSE_ERROR={exc}")
        return 1

    errors = validate_manifest(manifest)
    if errors:
        print("CANDIDATE_MANIFEST=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        return 1

    print(
        "CANDIDATE_MANIFEST=PASS "
        f"CANDIDATE_ID={manifest['candidate_id']} "
        f"ROLE={manifest['artifact_role']} "
        f"SOURCE_SHA={manifest['source']['commit_sha']} "
        f"ARTIFACT_SHA256={manifest['artifact']['sha256']} "
        "RUNTIME=NOT_VERIFIED PROMOTION_ELIGIBLE=false"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
