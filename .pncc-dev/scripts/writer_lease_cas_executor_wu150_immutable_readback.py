#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / ".pncc-dev/scripts/writer_lease_cas_executor_wu149.py"


def load_core() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pncc_wu149_cas_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("CORE_IMPORT_FAILED")
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    return core


def install_immutable_registry_reads(core: ModuleType) -> ModuleType:
    original_gh: Callable[..., Any] = core.gh
    mutable_path = f"/contents/{core.REGISTRY_PATH}?ref={urllib.parse.quote(core.STATE_BRANCH, safe='')}"
    state: dict[str, Any] = {
        "blob": None,
        "tree": None,
        "commit": None,
        "patched": False,
    }

    def fail(code: str) -> None:
        raise core.ExecutorError(code)

    def prove_registry_blob_from_git_data(token: str) -> dict[str, str]:
        expected_blob = state["blob"]
        expected_tree = state["tree"]
        expected_commit = state["commit"]
        if not all(isinstance(x, str) and core.SHA40.fullmatch(x) for x in (expected_blob, expected_tree, expected_commit)):
            fail("POSTWRITE_GITDATA_IDENTITY_MISSING")

        observed_head = original_gh(
            "GET", f"/git/ref/heads/{core.STATE_BRANCH}", token
        )["object"]["sha"]
        if observed_head != expected_commit:
            fail("POSTWRITE_STATE_REF_MISMATCH")

        commit_obj = original_gh("GET", f"/git/commits/{expected_commit}", token)
        if ((commit_obj.get("tree") or {}).get("sha")) != expected_tree:
            fail("POSTWRITE_COMMIT_TREE_MISMATCH")

        parts = [part for part in core.REGISTRY_PATH.split("/") if part]
        if not parts:
            fail("POSTWRITE_REGISTRY_PATH_INVALID")
        current_tree = expected_tree
        for index, part in enumerate(parts):
            tree_obj = original_gh("GET", f"/git/trees/{current_tree}", token)
            entries = tree_obj.get("tree")
            if not isinstance(entries, list):
                fail("POSTWRITE_TREE_ENTRIES_INVALID")
            matches = [entry for entry in entries if entry.get("path") == part]
            if len(matches) != 1:
                fail("POSTWRITE_TREE_PATH_NOT_UNIQUE")
            entry = matches[0]
            is_last = index == len(parts) - 1
            if not is_last:
                if entry.get("type") != "tree" or not core.SHA40.fullmatch(str(entry.get("sha", ""))):
                    fail("POSTWRITE_TREE_PATH_TYPE_INVALID")
                current_tree = entry["sha"]
            else:
                if entry.get("type") != "blob":
                    fail("POSTWRITE_REGISTRY_ENTRY_TYPE_INVALID")
                if entry.get("sha") != expected_blob:
                    fail("POSTWRITE_REGISTRY_BLOB_MISMATCH")

        return {"sha": expected_blob}

    def pinned_gh(method: str, path: str, token: str, body: Any = None) -> Any:
        if method == "GET" and path == mutable_path:
            if state["patched"]:
                return prove_registry_blob_from_git_data(token)
            observed_head = original_gh(
                "GET", f"/git/ref/heads/{core.STATE_BRANCH}", token
            )["object"]["sha"]
            immutable_path = (
                f"/contents/{core.REGISTRY_PATH}?ref="
                f"{urllib.parse.quote(observed_head, safe='')}"
            )
            return original_gh(method, immutable_path, token, body)

        result = original_gh(method, path, token, body)

        if method == "POST" and path == "/git/blobs":
            state["blob"] = (result or {}).get("sha")
        elif method == "POST" and path == "/git/trees":
            state["tree"] = (result or {}).get("sha")
        elif method == "POST" and path == "/git/commits":
            state["commit"] = (result or {}).get("sha")
        elif method == "PATCH" and path == f"/git/refs/heads/{core.STATE_BRANCH}":
            if not isinstance(body, dict) or body.get("force") is not False:
                fail("POSTWRITE_FORCE_OR_BODY_INVALID")
            if body.get("sha") != state["commit"]:
                fail("POSTWRITE_PATCH_COMMIT_MISMATCH")
            state["patched"] = True

        return result

    core.gh = pinned_gh
    return core


def main() -> int:
    core = install_immutable_registry_reads(load_core())
    try:
        return core.main()
    except core.ExecutorError as exc:
        print("WRITER_LEASE_CAS_EXECUTOR=BLOCKED")
        print("ERROR=" + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
