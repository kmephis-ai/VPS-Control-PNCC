#!/usr/bin/env python3
"""Deterministic PNCC candidate ZIP builder.

Consumes only governed candidate-source declaration, deterministic recipe, and
exact Git blob bytes from the current clean HEAD. Python stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

DECLARATION_PATH = ".pncc-dev/candidate-source.json"
EXPECTED_DECLARATION_KEYS = {
    "schema_version", "source_identity_semantic", "candidate_version", "source_roots",
    "build_recipe", "provenance_path", "runtime_authority", "promotion_authority",
}
EXPECTED_RECIPE_KEYS = {
    "schema_version", "recipe_id", "candidate_version", "source_root", "source_bytes_semantic",
    "input_selection", "archive_format", "compression", "path_order", "archive_root",
    "fixed_timestamp_utc", "zip_create_system", "zip_external_attr", "manifest_path",
    "output_filename", "runtime_authority", "promotion_authority",
}
FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)
DOS_ARCHIVE_ATTRIBUTE = 0x20


class BuildError(RuntimeError):
    pass


def run_git(root: Path, *args: str, text: bool = False):
    completed = subprocess.run(
        ["git", "-C", str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=text, check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr if text else completed.stderr.decode("utf-8", "replace")
        raise BuildError(f"git {' '.join(args)} failed rc={completed.returncode}: {stderr.strip()}")
    return completed.stdout


def git_text(root: Path, *args: str) -> str:
    return str(run_git(root, *args, text=True)).strip()


def git_blob(root: Path, repo_path: str) -> bytes:
    return bytes(run_git(root, "show", f"HEAD:{repo_path}"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json_blob(root: Path, repo_path: str) -> tuple[dict[str, Any], bytes]:
    raw = git_blob(root, repo_path)
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise BuildError(f"{repo_path}: JSON object required")
    return value, raw


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        raise BuildError(f"{label}: schema mismatch missing={missing} unknown={unknown}")


def validate_governed_inputs(root: Path) -> tuple[str, dict[str, Any], bytes, dict[str, Any], bytes]:
    head = git_text(root, "rev-parse", "HEAD")
    if len(head) != 40:
        raise BuildError("HEAD SHA is not 40 hex characters")
    status = git_text(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise BuildError("repository must be clean before build")

    declaration, declaration_raw = load_json_blob(root, DECLARATION_PATH)
    require_exact_keys(declaration, EXPECTED_DECLARATION_KEYS, "candidate-source")
    if declaration.get("schema_version") != 2:
        raise BuildError("candidate-source schema_version must be 2")
    if declaration.get("source_identity_semantic") != "EXACT_SOURCE_COMMIT":
        raise BuildError("candidate source must use EXACT_SOURCE_COMMIT")
    if declaration.get("runtime_authority") is not False or declaration.get("promotion_authority") is not False:
        raise BuildError("candidate-source cannot grant runtime/promotion authority")

    roots = declaration.get("source_roots")
    if not isinstance(roots, list) or len(roots) != 1 or not isinstance(roots[0], str):
        raise BuildError("exactly one source root is required")
    recipe_path = declaration.get("build_recipe")
    if not isinstance(recipe_path, str) or not recipe_path.startswith("build/"):
        raise BuildError("governed build recipe path required")
    recipe, recipe_raw = load_json_blob(root, recipe_path)
    require_exact_keys(recipe, EXPECTED_RECIPE_KEYS, "candidate recipe")

    if recipe.get("schema_version") != 1:
        raise BuildError("recipe schema_version must be 1")
    if recipe.get("candidate_version") != declaration.get("candidate_version"):
        raise BuildError("recipe/declaration candidate_version mismatch")
    if recipe.get("source_root") != roots[0]:
        raise BuildError("recipe/declaration source_root mismatch")

    expected = {
        "source_bytes_semantic": "GIT_BLOB_BYTES",
        "input_selection": "ALL_TRACKED_FILES_RECURSIVE",
        "archive_format": "ZIP", "compression": "STORE", "path_order": "ORDINAL_UTF8",
        "archive_root": "PACKAGE_ROOT", "fixed_timestamp_utc": "1980-01-01T00:00:00Z",
        "zip_create_system": "MSDOS", "zip_external_attr": "DOS_ARCHIVE",
    }
    for key, expected_value in expected.items():
        if recipe.get(key) != expected_value:
            raise BuildError(f"unsupported deterministic recipe field {key}={recipe.get(key)!r}")
    if recipe.get("runtime_authority") is not False or recipe.get("promotion_authority") is not False:
        raise BuildError("recipe cannot grant runtime/promotion authority")

    output_filename = recipe.get("output_filename")
    if not isinstance(output_filename, str) or Path(output_filename).name != output_filename or not output_filename.endswith(".zip"):
        raise BuildError("recipe output_filename must be a ZIP basename")
    expected_filename = f"VPS-Control-v{declaration['candidate_version']}.zip"
    if output_filename != expected_filename:
        raise BuildError(f"artifact filename/version mismatch: expected {expected_filename}")
    return head, declaration, declaration_raw, recipe, recipe_raw


def tracked_source_paths(root: Path, source_root: str) -> list[str]:
    lines = git_text(root, "ls-files", "--", source_root).splitlines()
    prefix = source_root.rstrip("/") + "/"
    paths = [line for line in lines if line.startswith(prefix)]
    if not paths:
        raise BuildError("canonical source root has no tracked files")
    if len(paths) != len(set(paths)):
        raise BuildError("duplicate tracked source path")
    return sorted(paths, key=lambda value: value.encode("utf-8"))


def verify_zip(path: Path, expected_names: list[str]) -> None:
    with zipfile.ZipFile(path, "r") as zf:
        infos = zf.infolist()
        names = [info.filename for info in infos]
        if names != expected_names:
            raise BuildError("ZIP entry order/name mismatch")
        if zf.comment != b"":
            raise BuildError("ZIP comment must be empty")
        for info in infos:
            if info.is_dir():
                raise BuildError(f"directory entry forbidden: {info.filename}")
            if info.compress_type != zipfile.ZIP_STORED:
                raise BuildError(f"compression forbidden: {info.filename}")
            if info.date_time != FIXED_ZIP_DATETIME:
                raise BuildError(f"timestamp mismatch: {info.filename} {info.date_time}")
            if info.create_system != 0:
                raise BuildError(f"create_system must be MS-DOS: {info.filename}")
            if (info.external_attr & 0xFF) != DOS_ARCHIVE_ATTRIBUTE:
                raise BuildError(f"DOS archive attribute mismatch: {info.filename}")
            if info.extra != b"":
                raise BuildError(f"ZIP extra metadata forbidden: {info.filename}")
            if info.comment != b"":
                raise BuildError(f"ZIP entry comment forbidden: {info.filename}")


def build(root: Path, output_dir: Path) -> dict[str, Any]:
    head, declaration, declaration_raw, recipe, recipe_raw = validate_governed_inputs(root)
    source_root = str(recipe["source_root"]).rstrip("/")
    tracked = tracked_source_paths(root, source_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / str(recipe["output_filename"])
    single_evidence_path = output_dir / "build-evidence.single.json"
    entries: list[dict[str, Any]] = []
    expected_names: list[str] = []

    with zipfile.ZipFile(artifact_path, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True, strict_timestamps=True) as zf:
        zf.comment = b""
        for repo_path in tracked:
            relative = PurePosixPath(repo_path).relative_to(PurePosixPath(source_root)).as_posix()
            raw = git_blob(root, repo_path)
            info = zipfile.ZipInfo(filename=relative, date_time=FIXED_ZIP_DATETIME)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            info.external_attr = DOS_ARCHIVE_ATTRIBUTE
            info.internal_attr = 0
            info.extra = b""
            info.comment = b""
            zf.writestr(info, raw)
            expected_names.append(relative)
            entries.append({"path": relative, "bytes": len(raw), "sha256": sha256_bytes(raw)})

    verify_zip(artifact_path, expected_names)
    artifact_bytes = artifact_path.read_bytes()
    evidence = {
        "schema_version": 1,
        "evidence_id": "PNCC_DETERMINISTIC_CANDIDATE_BUILD_V1",
        "source_commit_sha": head,
        "candidate_version": declaration["candidate_version"],
        "source_root": source_root,
        "source_file_count": len(entries),
        "candidate_source_declaration": {"path": DECLARATION_PATH, "sha256": sha256_bytes(declaration_raw)},
        "recipe": {"path": declaration["build_recipe"], "recipe_id": recipe["recipe_id"], "sha256": sha256_bytes(recipe_raw)},
        "artifact": {"filename": artifact_path.name, "sha256": sha256_bytes(artifact_bytes), "size_bytes": len(artifact_bytes)},
        "entries": entries,
        "deterministic_zip_semantics": {
            "archive_format": "ZIP", "compression": "STORE", "path_order": "ORDINAL_UTF8",
            "fixed_timestamp_utc": "1980-01-01T00:00:00Z", "zip_create_system": "MSDOS",
            "zip_external_attr": "DOS_ARCHIVE", "source_bytes_semantic": "GIT_BLOB_BYTES",
        },
        "runtime_authority": False,
        "promotion_authority": False,
    }
    single_evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
    print(
        "CANDIDATE_BUILD=PASS "
        f"SOURCE_SHA={head} FILES={len(entries)} ARTIFACT={artifact_path.name} "
        f"SHA256={evidence['artifact']['sha256']} SIZE={evidence['artifact']['size_bytes']} "
        "RUNTIME_AUTHORITY=false PROMOTION_AUTHORITY=false"
    )
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic PNCC candidate ZIP from exact Git blobs")
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        build(args.repository_root.resolve(), args.output_dir.resolve())
    except Exception as exc:
        print(f"CANDIDATE_BUILD=FAIL ERROR={exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
