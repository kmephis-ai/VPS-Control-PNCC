#!/usr/bin/env python3
"""Fail-closed PNCC Candidate Build Input readiness evaluator.

This module classifies whether the current Git checkout contains governed,
non-legacy candidate build inputs. Classification is engineering truth only;
it never grants runtime authority or promotion authority.
"""

from __future__ import annotations

import argparse
import json
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
    "forbidden_prefixes",
    "product_source_extensions",
    "runtime_authority",
    "hosted_ci_is_runtime_truth",
}

DECLARATION_KEYS = {
    "schema_version",
    "source_identity_semantic",
    "source_roots",
    "build_recipe",
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
BLOCKED_INVALID_POLICY = "BLOCKED_INVALID_POLICY"
BLOCKED_GIT_STATE = "BLOCKED_GIT_STATE"


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


def _run_git(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
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


def _validate_policy(policy: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not _exact_keys(policy, POLICY_KEYS):
        return None, "policy fields do not match the closed v1 contract"
    if policy.get("schema_version") != 1:
        return None, "unsupported policy schema_version"
    if policy.get("contract_id") != "PNCC_CANDIDATE_BUILD_INPUT_READINESS_V1":
        return None, "unexpected policy contract_id"
    declaration_path = _normalize_relative_path(policy.get("declaration_path"))
    if declaration_path is None:
        return None, "invalid declaration_path"
    source_prefixes = _normalize_prefixes(policy.get("allowed_source_root_prefixes"))
    build_prefixes = _normalize_prefixes(policy.get("allowed_build_recipe_prefixes"))
    forbidden_prefixes = _normalize_prefixes(policy.get("forbidden_prefixes"))
    if source_prefixes is None or build_prefixes is None or forbidden_prefixes is None:
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
    normalized["forbidden_prefixes"] = forbidden_prefixes
    return normalized, None


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
        return _result(
            BLOCKED_MISSING_SOURCE_DECLARATION,
            f"governed source declaration is absent: {declaration_rel}",
            subject_sha,
        )

    try:
        declaration = _load_json(declaration_path)
    except Exception as exc:
        return _result(BLOCKED_INVALID_DECLARATION, f"cannot parse declaration: {exc}", subject_sha)

    if not _exact_keys(declaration, DECLARATION_KEYS):
        return _result(BLOCKED_INVALID_DECLARATION, "declaration fields do not match the closed v1 contract", subject_sha)
    if declaration.get("schema_version") != 1:
        return _result(BLOCKED_INVALID_DECLARATION, "unsupported declaration schema_version", subject_sha)
    if declaration.get("source_identity_semantic") != "EXACT_SOURCE_COMMIT":
        return _result(BLOCKED_INVALID_DECLARATION, "source_identity_semantic must be EXACT_SOURCE_COMMIT", subject_sha)
    if not _string_list(declaration.get("source_roots")):
        return _result(BLOCKED_INVALID_DECLARATION, "source_roots must be a non-empty string list", subject_sha)
    if len(declaration["source_roots"]) != len(set(declaration["source_roots"])):
        return _result(BLOCKED_INVALID_DECLARATION, "source_roots must be unique", subject_sha)

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

    build_recipe = _normalize_relative_path(declaration.get("build_recipe"))
    if build_recipe is None:
        return _result(BLOCKED_INVALID_DECLARATION, "unsafe build_recipe path", subject_sha)
    if _under_prefix(build_recipe, policy["forbidden_prefixes"]):
        return _result(BLOCKED_FORBIDDEN_SOURCE_PREFIX, f"forbidden build recipe: {build_recipe}", subject_sha)
    if not _under_prefix(build_recipe, policy["allowed_build_recipe_prefixes"]):
        return _result(BLOCKED_INVALID_DECLARATION, f"build recipe is outside governed prefixes: {build_recipe}", subject_sha)

    aggregate_product_files = 0
    all_guarded_paths: List[str] = []
    for source_root in source_roots:
        source_path = root.joinpath(*PurePosixPath(source_root).parts)
        if not source_path.exists() or not source_path.is_dir():
            return _result(BLOCKED_MISSING_SOURCE_ROOT, f"missing source root: {source_root}", subject_sha)
        physical_files = sorted(path for path in source_path.rglob("*") if path.is_file())
        if not physical_files:
            return _result(BLOCKED_EMPTY_SOURCE_ROOT, f"source root contains no files: {source_root}", subject_sha)
        tracked = _tracked_paths(root, source_root)
        if tracked is None:
            return _result(BLOCKED_GIT_STATE, f"cannot query tracked source paths: {source_root}", subject_sha)
        tracked_set = set(tracked)
        relative_files = [path.relative_to(root).as_posix() for path in physical_files]
        untracked = [path for path in relative_files if path not in tracked_set]
        if untracked:
            return _result(BLOCKED_UNTRACKED_SOURCE, f"untracked source file: {untracked[0]}", subject_sha)
        product_files = [path for path in physical_files if path.suffix.lower() in set(policy["product_source_extensions"])]
        if not product_files:
            return _result(BLOCKED_EMPTY_SOURCE_ROOT, f"source root has no PNCC product-source files: {source_root}", subject_sha)
        aggregate_product_files += len(product_files)
        all_guarded_paths.append(source_root)

    if aggregate_product_files <= 0:
        return _result(BLOCKED_EMPTY_SOURCE_ROOT, "no governed PNCC product-source files found", subject_sha)

    build_path = root.joinpath(*PurePosixPath(build_recipe).parts)
    if not build_path.exists() or not build_path.is_file():
        return _result(BLOCKED_MISSING_BUILD_RECIPE, f"missing build recipe: {build_recipe}", subject_sha)
    tracked_build = _tracked_paths(root, build_recipe)
    if tracked_build is None:
        return _result(BLOCKED_GIT_STATE, f"cannot query tracked build recipe: {build_recipe}", subject_sha)
    if build_recipe not in set(tracked_build):
        return _result(BLOCKED_UNTRACKED_BUILD_RECIPE, f"build recipe is not Git-tracked: {build_recipe}", subject_sha)

    all_guarded_paths.append(build_recipe)
    dirty = _is_dirty(root, all_guarded_paths)
    if dirty is None:
        return _result(BLOCKED_GIT_STATE, "cannot evaluate build-input worktree/index state", subject_sha)
    if dirty:
        return _result(BLOCKED_DIRTY_BUILD_INPUT, "declared build inputs differ from exact HEAD", subject_sha)

    return _result(
        READY,
        f"governed exact-source inputs are ready: roots={len(source_roots)} product_files={aggregate_product_files}",
        subject_sha,
    )


def _print_result(result: Dict[str, Any]) -> None:
    subject = result.get("subject_sha") or "NONE"
    print(
        "CANDIDATE_BUILD_INPUT_STATE={state} CAN_BUILD={can_build} "
        "RUNTIME_AUTHORITY=false PROMOTION_AUTHORITY=false SUBJECT_SHA={subject} REASON={reason}".format(
            state=result["state"],
            can_build=str(bool(result["can_build"])).lower(),
            subject=subject,
            reason=json.dumps(result["reason"], ensure_ascii=True),
        )
    )


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
