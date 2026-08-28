#!/usr/bin/env python3
"""Fail-closed PNCC Candidate Build Input readiness evaluator.

READY is engineering build-input truth only. It never grants runtime,
promotion, deployment, or Stable/DONE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


POLICY_KEYS = {
    "schema_version",
    "contract_id",
    "declaration_path",
    "allowed_source_root_prefixes",
    "allowed_build_recipe_prefixes",
    "allowed_provenance_prefixes",
    "forbidden_prefixes",
    "product_source_extensions",
    "runtime_authority",
    "hosted_ci_is_runtime_truth",
}

DECLARATION_KEYS = {
    "schema_version",
    "source_identity_semantic",
    "candidate_version",
    "source_roots",
    "build_recipe",
    "provenance_path",
    "runtime_authority",
    "promotion_authority",
}

RECIPE_KEYS = {
    "schema_version",
    "recipe_id",
    "candidate_version",
    "source_root",
    "source_bytes_semantic",
    "input_selection",
    "archive_format",
    "compression",
    "path_order",
    "archive_root",
    "fixed_timestamp_utc",
    "zip_create_system",
    "zip_external_attr",
    "manifest_path",
    "output_filename",
    "runtime_authority",
    "promotion_authority",
}

READY = "READY"
BLOCKED_MISSING_SOURCE_DECLARATION = "BLOCKED_MISSING_SOURCE_DECLARATION"
BLOCKED_FORBIDDEN_SOURCE_PREFIX = "BLOCKED_FORBIDDEN_SOURCE_PREFIX"
BLOCKED_MISSING_SOURCE_ROOT = "BLOCKED_MISSING_SOURCE_ROOT"
BLOCKED_EMPTY_SOURCE_ROOT = "BLOCKED_EMPTY_SOURCE_ROOT"
BLOCKED_UNTRACKED_SOURCE = "BLOCKED_UNTRACKED_SOURCE"
BLOCKED_MISSING_BUILD_RECIPE = "BLOCKED_MISSING_BUILD_RECIPE"
BLOCKED_UNTRACKED_BUILD_RECIPE = "BLOCKED_UNTRACKED_BUILD_RECIPE"
BLOCKED_DIRTY_BUILD_INPUT = "BLOCKED_DIRTY_BUILD_INPUT"
BLOCKED_INVALID_DECLARATION = "BLOCKED_INVALID_DECLARATION"
BLOCKED_INVALID_RECIPE = "BLOCKED_INVALID_RECIPE"
BLOCKED_VERSION_MISMATCH = "BLOCKED_VERSION_MISMATCH"
BLOCKED_PROVENANCE_MISMATCH = "BLOCKED_PROVENANCE_MISMATCH"
BLOCKED_MANIFEST_MISMATCH = "BLOCKED_MANIFEST_MISMATCH"
BLOCKED_INVALID_POLICY = "BLOCKED_INVALID_POLICY"
BLOCKED_GIT_STATE = "BLOCKED_GIT_STATE"

VERSION_RX = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-rc[0-9]+\.[0-9]+)?$")


def _result(state: str, reason: str, subject_sha: Optional[str] = None) -> Dict[str, Any]:
    return {
        "state": state,
        "can_build": state == READY,
        "runtime_authority": False,
        "promotion_authority": False,
        "subject_sha": subject_sha,
        "reason": reason,
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _exact_keys(value: Any, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value.keys()) == expected


def _string_list(value: Any, *, nonempty: bool = True) -> bool:
    if not isinstance(value, list):
        return False
    if nonempty and not value:
        return False
    return all(isinstance(item, str) and item.strip() for item in value)


def _normalize_relative_path(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute():
        return None
    parts = path.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None
    normalized = path.as_posix()
    if normalized.startswith("/") or normalized == ".":
        return None
    return normalized


def _normalize_prefixes(values: Any) -> Optional[List[str]]:
    if not _string_list(values):
        return None
    normalized: List[str] = []
    for value in values:
        path = _normalize_relative_path(value.rstrip("/"))
        if path is None:
            return None
        normalized.append(path.rstrip("/") + "/")
    if len(normalized) != len(set(normalized)):
        return None
    return normalized


def _under_prefix(path: str, prefixes: Iterable[str]) -> bool:
    normalized = path.rstrip("/") + "/"
    return any(normalized.startswith(prefix) for prefix in prefixes)


def _run_git(root: Path, args: Sequence[str], *, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _head_sha(root: Path) -> Optional[str]:
    completed = _run_git(root, ["rev-parse", "--verify", "HEAD"])
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip().lower()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        return None
    return value


def _tracked_paths(root: Path, path: str) -> Optional[List[str]]:
    completed = _run_git(root, ["ls-files", "-z", "--", path])
    if completed.returncode != 0:
        return None
    return [item for item in completed.stdout.split("\0") if item]


def _is_dirty(root: Path, paths: Sequence[str]) -> Optional[bool]:
    worktree = _run_git(root, ["diff", "--quiet", "--", *paths])
    if worktree.returncode not in (0, 1):
        return None
    index = _run_git(root, ["diff", "--cached", "--quiet", "--", *paths])
    if index.returncode not in (0, 1):
        return None
    return worktree.returncode == 1 or index.returncode == 1


def _git_blob(root: Path, path: str) -> Optional[bytes]:
    completed = _run_git(root, ["show", f"HEAD:{path}"], text=False)
    if completed.returncode != 0:
        return None
    return bytes(completed.stdout)


def _decode_blob(root: Path, path: str) -> Optional[str]:
    value = _git_blob(root, path)
    if value is None:
        return None
    try:
        return value.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _validate_policy(policy: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not _exact_keys(policy, POLICY_KEYS):
        return None, "policy fields do not match the closed v2 contract"
    if policy.get("schema_version") != 2:
        return None, "unsupported policy schema_version"
    if policy.get("contract_id") != "PNCC_CANDIDATE_BUILD_INPUT_READINESS_V2":
        return None, "unexpected policy contract_id"
    declaration_path = _normalize_relative_path(policy.get("declaration_path"))
    if declaration_path is None:
        return None, "invalid declaration_path"
    source_prefixes = _normalize_prefixes(policy.get("allowed_source_root_prefixes"))
    build_prefixes = _normalize_prefixes(policy.get("allowed_build_recipe_prefixes"))
    provenance_prefixes = _normalize_prefixes(policy.get("allowed_provenance_prefixes"))
    forbidden_prefixes = _normalize_prefixes(policy.get("forbidden_prefixes"))
    if (
        source_prefixes is None
        or build_prefixes is None
        or provenance_prefixes is None
        or forbidden_prefixes is None
    ):
        return None, "invalid or duplicate path prefixes"
    extensions = policy.get("product_source_extensions")
    if not _string_list(extensions) or len(extensions) != len(set(extensions)):
        return None, "invalid product_source_extensions"
    if not all(item.startswith(".") and item == item.lower() for item in extensions):
        return None, "product_source_extensions must be lowercase extensions"
    if policy.get("runtime_authority") is not False:
        return None, "runtime_authority must remain false"
    if policy.get("hosted_ci_is_runtime_truth") is not False:
        return None, "hosted_ci_is_runtime_truth must remain false"
    normalized = dict(policy)
    normalized["declaration_path"] = declaration_path
    normalized["allowed_source_root_prefixes"] = source_prefixes
    normalized["allowed_build_recipe_prefixes"] = build_prefixes
    normalized["allowed_provenance_prefixes"] = provenance_prefixes
    normalized["forbidden_prefixes"] = forbidden_prefixes
    return normalized, None


def _validate_recipe(recipe: Any, *, candidate_version: str, source_root: str) -> Optional[str]:
    if not _exact_keys(recipe, RECIPE_KEYS):
        return "recipe fields do not match the closed deterministic ZIP v1 contract"
    expected_scalars = {
        "schema_version": 1,
        "recipe_id": "PNCC_WINDOWS_V7_DETERMINISTIC_ZIP_V1",
        "candidate_version": candidate_version,
        "source_root": source_root,
        "source_bytes_semantic": "GIT_BLOB_BYTES",
        "input_selection": "ALL_TRACKED_FILES_RECURSIVE",
        "archive_format": "ZIP",
        "compression": "STORE",
        "path_order": "ORDINAL_UTF8",
        "archive_root": "PACKAGE_ROOT",
        "fixed_timestamp_utc": "1980-01-01T00:00:00Z",
        "zip_create_system": "MSDOS",
        "zip_external_attr": "DOS_ARCHIVE",
        "manifest_path": f"{source_root}/VPS-Control-v7-SHA256.txt",
        "output_filename": f"VPS-Control-v{candidate_version}.zip",
        "runtime_authority": False,
        "promotion_authority": False,
    }
    for key, expected in expected_scalars.items():
        if recipe.get(key) != expected:
            return f"recipe {key} mismatch"
    return None


def _validate_version_surface(root: Path, source_root: str, candidate_version: str) -> Optional[str]:
    main_path = f"{source_root}/VPS-Control-v7.ps1"
    launch_path = f"{source_root}/VPS-Control-v7-launch.ps1"
    tunnel_path = f"{source_root}/VPS-Control-v7-TUNNEL-CONTRACT.json"
    main = _decode_blob(root, main_path)
    launch = _decode_blob(root, launch_path)
    if main is None or launch is None:
        return "cannot decode authoritative PowerShell version surface"
    if f"$UiVersion = '{candidate_version}'" not in main:
        return "VPS-Control-v7.ps1 UiVersion mismatch"
    if f"VPS Control Center v{candidate_version}" not in main[:2048]:
        return "VPS-Control-v7.ps1 header mismatch"
    if f"$LauncherVersion = '{candidate_version}'" not in launch:
        return "VPS-Control-v7-launch.ps1 LauncherVersion mismatch"
    tunnel_blob = _decode_blob(root, tunnel_path)
    if tunnel_blob is None:
        return "cannot decode tunnel contract"
    try:
        tunnel = json.loads(tunnel_blob)
    except Exception as exc:
        return f"cannot parse tunnel contract: {exc}"
    if tunnel.get("ContractVersion") != candidate_version:
        return "tunnel ContractVersion mismatch"
    for rel in ("VPS-Control-v7-README.txt", "VPS-Control-v7-ARCHITECTURE.md", "VPS-Control-v7-CAPABILITY-TRUTH.md"):
        text = _decode_blob(root, f"{source_root}/{rel}")
        if text is None:
            return f"cannot decode {rel}"
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if candidate_version not in first:
            return f"{rel} current-version heading mismatch"
    previous_version = "7.0.0-rc14.38"
    executable_ext = {".ps1", ".psm1", ".psd1", ".cmd", ".vbs", ".json"}
    tracked = _tracked_paths(root, source_root)
    if tracked is None:
        return "cannot enumerate source for residual-version scan"
    for path in tracked:
        if Path(path).suffix.lower() not in executable_ext:
            continue
        text = _decode_blob(root, path)
        if text is not None and previous_version in text:
            return f"residual previous current-version literal in executable/config source: {path}"
    return None


def _validate_provenance_and_manifest(root: Path, *, source_root: str, candidate_version: str, provenance_path: str, manifest_path: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    prov_blob = _git_blob(root, provenance_path)
    if prov_blob is None:
        return "provenance is not available from exact HEAD", None, None
    try:
        prov = json.loads(prov_blob.decode("utf-8-sig"))
    except Exception as exc:
        return f"cannot parse provenance: {exc}", None, None
    if prov.get("hash_semantics") != "CANONICAL_GIT_BLOB_BYTES":
        return "provenance hash_semantics mismatch", None, None
    if prov.get("source_root") != source_root:
        return "provenance source_root mismatch", None, None
    baseline = prov.get("baseline")
    if not isinstance(baseline, dict):
        return "provenance baseline missing", None, None
    if baseline.get("embedded_version") != candidate_version:
        return "provenance embedded_version mismatch", None, None
    if baseline.get("requires_version_bump_before_build") is not False:
        return "provenance still requires a version bump", None, None
    if baseline.get("activated_candidate_version") != candidate_version:
        return "provenance activated_candidate_version mismatch", None, None
    if baseline.get("previous_runtime_version") != "7.0.0-rc14.38":
        return "provenance previous_runtime_version mismatch", None, None
    safety = prov.get("safety")
    if not isinstance(safety, dict):
        return "provenance safety block missing", None, None
    for key in ("runtime_authority", "promotion_authority", "stable_done"):
        if safety.get(key) is not False:
            return f"provenance safety authority weakened: {key}", None, None
    if safety.get("build_input_ready") is not True:
        return "provenance build_input_ready is not true", None, None
    if safety.get("artifact_exists") is not False:
        return "provenance incorrectly claims artifact_exists", None, None
    inventory = prov.get("inventory")
    if not isinstance(inventory, list) or not inventory:
        return "provenance inventory missing", None, None
    inventory_paths: List[str] = []
    for rec in inventory:
        if not isinstance(rec, dict) or set(rec.keys()) != {"bytes", "path", "sha256"}:
            return "malformed provenance inventory row", None, None
        rel = _normalize_relative_path(rec.get("path"))
        if rel is None or rel != rec.get("path"):
            return "unsafe provenance inventory path", None, None
        blob = _git_blob(root, f"{source_root}/{rel}")
        if blob is None:
            return f"provenance path missing from HEAD: {rel}", None, None
        if rec.get("bytes") != len(blob) or rec.get("sha256") != hashlib.sha256(blob).hexdigest():
            return f"provenance Git-blob mismatch: {rel}", None, None
        inventory_paths.append(rel)
    if len(inventory_paths) != len(set(inventory_paths)):
        return "duplicate provenance inventory path", None, None
    tracked = _tracked_paths(root, source_root)
    if tracked is None:
        return "cannot enumerate tracked canonical source", None, None
    expected_inventory = sorted(PurePosixPath(path).relative_to(PurePosixPath(source_root)).as_posix() for path in tracked)
    if sorted(inventory_paths) != expected_inventory:
        return "provenance inventory does not exactly cover canonical tracked source", None, None
    manifest_blob = _git_blob(root, manifest_path)
    if manifest_blob is None:
        return "package manifest missing from HEAD", None, None
    try:
        manifest_lines = manifest_blob.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        return "package manifest is not UTF-8", None, None
    first = next((line.strip() for line in manifest_lines if line.strip()), "")
    if candidate_version not in first:
        return "package manifest current-version heading mismatch", None, None
    rows = [line for line in manifest_lines if line and not line.startswith("#")]
    manifest_map: Dict[str, str] = {}
    for row in rows:
        match = re.match(r"^([0-9a-f]{64})  (.+)$", row)
        if not match:
            return "malformed package manifest row", None, None
        rel = match.group(2).replace("\\", "/")
        if _normalize_relative_path(rel) != rel:
            return "unsafe package manifest path", None, None
        if rel in manifest_map:
            return "duplicate package manifest path", None, None
        manifest_map[rel] = match.group(1)
    manifest_rel = PurePosixPath(manifest_path).relative_to(PurePosixPath(source_root)).as_posix()
    expected_manifest = sorted(path for path in expected_inventory if path != manifest_rel)
    if sorted(manifest_map) != expected_manifest:
        return "package manifest does not exactly cover canonical source excluding itself", None, None
    for rel, expected_sha in manifest_map.items():
        blob = _git_blob(root, f"{source_root}/{rel}")
        if blob is None or hashlib.sha256(blob).hexdigest() != expected_sha:
            return f"package manifest Git-blob mismatch: {rel}", None, None
    return None, len(inventory_paths), len(manifest_map)


def evaluate(repository_root: Path, policy_path: Path) -> Dict[str, Any]:
    root = repository_root.resolve()
    try:
        policy_raw = _load_json(policy_path)
    except Exception as exc:
        return _result(BLOCKED_INVALID_POLICY, f"cannot read policy: {exc}")
    policy, policy_error = _validate_policy(policy_raw)
    if policy is None:
        return _result(BLOCKED_INVALID_POLICY, policy_error or "invalid policy")
    subject_sha = _head_sha(root)
    if subject_sha is None:
        return _result(BLOCKED_GIT_STATE, "repository has no exact 40-hex HEAD commit")
    declaration_rel = policy["declaration_path"]
    declaration_path = root.joinpath(*PurePosixPath(declaration_rel).parts)
    if not declaration_path.is_file():
        return _result(BLOCKED_MISSING_SOURCE_DECLARATION, f"governed source declaration is absent: {declaration_rel}", subject_sha)
    try:
        declaration = _load_json(declaration_path)
    except Exception as exc:
        return _result(BLOCKED_INVALID_DECLARATION, f"cannot parse declaration: {exc}", subject_sha)
    if not _exact_keys(declaration, DECLARATION_KEYS):
        return _result(BLOCKED_INVALID_DECLARATION, "declaration fields do not match the closed v2 contract", subject_sha)
    if declaration.get("schema_version") != 2:
        return _result(BLOCKED_INVALID_DECLARATION, "unsupported declaration schema_version", subject_sha)
    if declaration.get("source_identity_semantic") != "EXACT_SOURCE_COMMIT":
        return _result(BLOCKED_INVALID_DECLARATION, "source_identity_semantic must be EXACT_SOURCE_COMMIT", subject_sha)
    candidate_version = declaration.get("candidate_version")
    if not isinstance(candidate_version, str) or not VERSION_RX.fullmatch(candidate_version):
        return _result(BLOCKED_INVALID_DECLARATION, "invalid candidate_version", subject_sha)
    if declaration.get("runtime_authority") is not False or declaration.get("promotion_authority") is not False:
        return _result(BLOCKED_INVALID_DECLARATION, "declaration cannot grant runtime/promotion authority", subject_sha)
    if not _string_list(declaration.get("source_roots")):
        return _result(BLOCKED_INVALID_DECLARATION, "source_roots must be a non-empty string list", subject_sha)
    if len(declaration["source_roots"]) != len(set(declaration["source_roots"])):
        return _result(BLOCKED_INVALID_DECLARATION, "source_roots must be unique", subject_sha)
    if len(declaration["source_roots"]) != 1:
        return _result(BLOCKED_INVALID_DECLARATION, "deterministic ZIP v1 requires exactly one source_root", subject_sha)
    source_roots: List[str] = []
    for raw in declaration["source_roots"]:
        normalized = _normalize_relative_path(raw)
        if normalized is None:
            return _result(BLOCKED_INVALID_DECLARATION, f"unsafe source root: {raw!r}", subject_sha)
        normalized_dir = normalized.rstrip("/") + "/"
        if _under_prefix(normalized_dir, policy["forbidden_prefixes"]):
            return _result(BLOCKED_FORBIDDEN_SOURCE_PREFIX, f"forbidden source root: {normalized_dir}", subject_sha)
        if not _under_prefix(normalized_dir, policy["allowed_source_root_prefixes"]):
            return _result(BLOCKED_INVALID_DECLARATION, f"source root is outside governed prefixes: {normalized_dir}", subject_sha)
        source_roots.append(normalized_dir.rstrip("/"))
    source_root = source_roots[0]
    build_recipe = _normalize_relative_path(declaration.get("build_recipe"))
    if build_recipe is None:
        return _result(BLOCKED_INVALID_DECLARATION, "unsafe build_recipe path", subject_sha)
    if _under_prefix(build_recipe, policy["forbidden_prefixes"]):
        return _result(BLOCKED_FORBIDDEN_SOURCE_PREFIX, f"forbidden build recipe: {build_recipe}", subject_sha)
    if not _under_prefix(build_recipe, policy["allowed_build_recipe_prefixes"]):
        return _result(BLOCKED_INVALID_DECLARATION, f"build recipe is outside governed prefixes: {build_recipe}", subject_sha)
    provenance_path = _normalize_relative_path(declaration.get("provenance_path"))
    if provenance_path is None:
        return _result(BLOCKED_INVALID_DECLARATION, "unsafe provenance_path", subject_sha)
    if _under_prefix(provenance_path, policy["forbidden_prefixes"]):
        return _result(BLOCKED_FORBIDDEN_SOURCE_PREFIX, f"forbidden provenance path: {provenance_path}", subject_sha)
    if not _under_prefix(provenance_path, policy["allowed_provenance_prefixes"]):
        return _result(BLOCKED_INVALID_DECLARATION, "provenance_path is outside governed prefixes", subject_sha)
    source_path = root.joinpath(*PurePosixPath(source_root).parts)
    if not source_path.exists() or not source_path.is_dir():
        return _result(BLOCKED_MISSING_SOURCE_ROOT, f"missing source root: {source_root}", subject_sha)
    physical_files = sorted(path for path in source_path.rglob("*") if path.is_file())
    if not physical_files:
        return _result(BLOCKED_EMPTY_SOURCE_ROOT, f"source root contains no files: {source_root}", subject_sha)
    tracked_source = _tracked_paths(root, source_root)
    if tracked_source is None:
        return _result(BLOCKED_GIT_STATE, f"cannot query tracked source paths: {source_root}", subject_sha)
    tracked_source_set = set(tracked_source)
    relative_files = [path.relative_to(root).as_posix() for path in physical_files]
    untracked = [path for path in relative_files if path not in tracked_source_set]
    if untracked:
        return _result(BLOCKED_UNTRACKED_SOURCE, f"untracked source file: {untracked[0]}", subject_sha)
    product_files = [path for path in physical_files if path.suffix.lower() in set(policy["product_source_extensions"])]
    if not product_files:
        return _result(BLOCKED_EMPTY_SOURCE_ROOT, f"source root has no PNCC product-source files: {source_root}", subject_sha)
    build_path = root.joinpath(*PurePosixPath(build_recipe).parts)
    if not build_path.exists() or not build_path.is_file():
        return _result(BLOCKED_MISSING_BUILD_RECIPE, f"missing build recipe: {build_recipe}", subject_sha)
    tracked_build = _tracked_paths(root, build_recipe)
    if tracked_build is None:
        return _result(BLOCKED_GIT_STATE, f"cannot query tracked build recipe: {build_recipe}", subject_sha)
    if build_recipe not in set(tracked_build):
        return _result(BLOCKED_UNTRACKED_BUILD_RECIPE, f"build recipe is not Git-tracked: {build_recipe}", subject_sha)
    provenance_fs = root.joinpath(*PurePosixPath(provenance_path).parts)
    if not provenance_fs.exists() or not provenance_fs.is_file():
        return _result(BLOCKED_PROVENANCE_MISMATCH, f"missing provenance: {provenance_path}", subject_sha)
    tracked_prov = _tracked_paths(root, provenance_path)
    if tracked_prov is None or provenance_path not in set(tracked_prov):
        return _result(BLOCKED_PROVENANCE_MISMATCH, "provenance is not Git-tracked", subject_sha)
    guarded = [source_root, build_recipe, provenance_path, declaration_rel]
    dirty = _is_dirty(root, guarded)
    if dirty is None:
        return _result(BLOCKED_GIT_STATE, "cannot evaluate build-input worktree/index state", subject_sha)
    if dirty:
        return _result(BLOCKED_DIRTY_BUILD_INPUT, "declared build inputs differ from exact HEAD", subject_sha)
    try:
        recipe = _load_json(build_path)
    except Exception as exc:
        return _result(BLOCKED_INVALID_RECIPE, f"cannot parse build recipe: {exc}", subject_sha)
    recipe_error = _validate_recipe(recipe, candidate_version=candidate_version, source_root=source_root)
    if recipe_error:
        return _result(BLOCKED_INVALID_RECIPE, recipe_error, subject_sha)
    version_error = _validate_version_surface(root, source_root, candidate_version)
    if version_error:
        return _result(BLOCKED_VERSION_MISMATCH, version_error, subject_sha)
    manifest_path = recipe["manifest_path"]
    provenance_error, inventory_count, manifest_count = _validate_provenance_and_manifest(root, source_root=source_root, candidate_version=candidate_version, provenance_path=provenance_path, manifest_path=manifest_path)
    if provenance_error:
        state = BLOCKED_MANIFEST_MISMATCH if "manifest" in provenance_error.lower() else BLOCKED_PROVENANCE_MISMATCH
        return _result(state, provenance_error, subject_sha)
    return _result(READY, f"governed deterministic build inputs are ready: version={candidate_version} source_root={source_root} product_files={len(product_files)} inventory={inventory_count} manifest={manifest_count} artifact_exists=false", subject_sha)


def _print_result(result: Dict[str, Any]) -> None:
    subject = result.get("subject_sha") or "NONE"
    print("CANDIDATE_BUILD_INPUT_STATE={state} CAN_BUILD={can_build} RUNTIME_AUTHORITY=false PROMOTION_AUTHORITY=false SUBJECT_SHA={subject} REASON={reason}".format(state=result["state"], can_build=str(bool(result["can_build"])).lower(), subject=subject, reason=json.dumps(result["reason"], ensure_ascii=True)))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--policy", default=".pncc-dev/contracts/candidate-build-input-policy.json")
    parser.add_argument("--expect-state")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    root = Path(args.repository_root)
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    result = evaluate(root, policy_path)
    _print_result(result)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.expect_state and result["state"] != args.expect_state:
        print(f"EXPECTED_STATE_MISMATCH expected={args.expect_state} actual={result['state']}", file=sys.stderr)
        return 2
    if args.require_ready and result["state"] != READY:
        print(f"CANDIDATE_BUILD_BLOCKED state={result['state']}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
