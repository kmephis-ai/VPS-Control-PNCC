#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib.util
import time
import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / ".pncc-dev/scripts/writer_lease_cas_executor_wu149.py"
REF_CONVERGENCE_DELAYS_SECONDS = (0.0, 0.2, 0.5, 1.0, 2.0, 4.0)


def load_core() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pncc_wu149_cas_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("CORE_IMPORT_FAILED")
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    return core


def install_immutable_registry_reads(core: ModuleType) -> ModuleType:
    original_gh: Callable[..., Any] = core.gh
    ref_path = f"/git/ref/heads/{core.STATE_BRANCH}"
    mutable_path = f"/contents/{core.REGISTRY_PATH}?ref={urllib.parse.quote(core.STATE_BRANCH, safe='')}"
    state: dict[str, Any] = {
        "blob": None,
        "blob_bytes": None,
        "tree": None,
        "commit": None,
        "commit_request": None,
        "prewrite_head": None,
        "patch_ack": False,
        "patched": False,
    }

    def fail(code: str) -> None:
        raise core.ExecutorError(code)

    def exact_sha(value: Any) -> str:
        text = str(value or "")
        if not core.SHA40.fullmatch(text):
            fail("POSTWRITE_GITDATA_IDENTITY_MISSING")
        return text

    def ref_sha(result: Any) -> str:
        if not isinstance(result, dict):
            fail("POSTWRITE_REF_RESPONSE_INVALID")
        obj = result.get("object")
        if not isinstance(obj, dict):
            fail("POSTWRITE_REF_RESPONSE_INVALID")
        return exact_sha(obj.get("sha"))

    def prove_ref_convergence(token: str) -> Any:
        expected_commit = exact_sha(state["commit"])
        prewrite_head = exact_sha(state["prewrite_head"])
        last_result: Any = None
        for index, delay in enumerate(REF_CONVERGENCE_DELAYS_SECONDS):
            if delay:
                time.sleep(delay)
            last_result = original_gh("GET", ref_path, token)
            observed = ref_sha(last_result)
            if observed == expected_commit:
                return last_result
            if observed != prewrite_head:
                fail("POSTWRITE_STATE_REF_DIVERGED")
            if index == len(REF_CONVERGENCE_DELAYS_SECONDS) - 1:
                break
        fail("POSTWRITE_STATE_REF_CONVERGENCE_TIMEOUT")

    def prove_registry_blob_from_git_data(token: str) -> dict[str, str]:
        expected_blob = exact_sha(state["blob"])
        expected_tree = exact_sha(state["tree"])
        expected_commit = exact_sha(state["commit"])
        prewrite_head = exact_sha(state["prewrite_head"])
        expected_bytes = state["blob_bytes"]
        request = state["commit_request"]
        if state["patch_ack"] is not True or not isinstance(expected_bytes, bytes) or not isinstance(request, dict):
            fail("POSTWRITE_GITDATA_IDENTITY_MISSING")

        commit_obj = original_gh("GET", f"/git/commits/{expected_commit}", token)
        if not isinstance(commit_obj, dict):
            fail("POSTWRITE_COMMIT_INVALID")
        if ((commit_obj.get("tree") or {}).get("sha")) != expected_tree:
            fail("POSTWRITE_COMMIT_TREE_MISMATCH")
        parents = commit_obj.get("parents")
        if not isinstance(parents, list) or [p.get("sha") for p in parents if isinstance(p, dict)] != [prewrite_head]:
            fail("POSTWRITE_COMMIT_PARENT_MISMATCH")
        if request.get("tree") != expected_tree or request.get("parents") != [prewrite_head]:
            fail("POSTWRITE_COMMIT_REQUEST_MISMATCH")
        if commit_obj.get("message") != request.get("message"):
            fail("POSTWRITE_COMMIT_MESSAGE_MISMATCH")

        parts = [part for part in core.REGISTRY_PATH.split("/") if part]
        if not parts:
            fail("POSTWRITE_REGISTRY_PATH_INVALID")
        current_tree = expected_tree
        for index, part in enumerate(parts):
            tree_obj = original_gh("GET", f"/git/trees/{current_tree}", token)
            entries = tree_obj.get("tree") if isinstance(tree_obj, dict) else None
            if not isinstance(entries, list):
                fail("POSTWRITE_TREE_ENTRIES_INVALID")
            matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("path") == part]
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

        blob_obj = original_gh("GET", f"/git/blobs/{expected_blob}", token)
        if not isinstance(blob_obj, dict) or blob_obj.get("encoding") != "base64":
            fail("POSTWRITE_REGISTRY_BLOB_ENCODING_INVALID")
        try:
            observed_bytes = base64.b64decode(str(blob_obj.get("content", "")), validate=False)
        except Exception as exc:
            raise core.ExecutorError("POSTWRITE_REGISTRY_BLOB_DECODE_FAILED") from exc
        if observed_bytes != expected_bytes or core.git_blob_sha(observed_bytes) != expected_blob:
            fail("POSTWRITE_REGISTRY_BYTES_MISMATCH")
        return {"sha": expected_blob}

    def pinned_gh(method: str, path: str, token: str, body: Any = None) -> Any:
        if method == "GET" and path == ref_path:
            if state["patched"]:
                return prove_ref_convergence(token)
            result = original_gh(method, path, token, body)
            state["prewrite_head"] = ref_sha(result)
            return result

        if method == "GET" and path == mutable_path:
            if state["patched"]:
                return prove_registry_blob_from_git_data(token)
            observed_head = ref_sha(original_gh("GET", ref_path, token))
            state["prewrite_head"] = observed_head
            immutable_path = (
                f"/contents/{core.REGISTRY_PATH}?ref="
                f"{urllib.parse.quote(observed_head, safe='')}"
            )
            return original_gh(method, immutable_path, token, body)

        if method == "PATCH" and path == f"/git/refs/heads/{core.STATE_BRANCH}":
            if not isinstance(body, dict) or body.get("force") is not False:
                fail("POSTWRITE_FORCE_OR_BODY_INVALID")
            if body.get("sha") != state["commit"]:
                fail("POSTWRITE_PATCH_COMMIT_MISMATCH")
            exact_sha(state["prewrite_head"])
            result = original_gh(method, path, token, body)
            if ref_sha(result) != state["commit"]:
                fail("POSTWRITE_PATCH_ACK_MISMATCH")
            state["patch_ack"] = True
            state["patched"] = True
            return result

        result = original_gh(method, path, token, body)

        if method == "POST" and path == "/git/blobs":
            if not isinstance(body, dict) or body.get("encoding") != "utf-8" or not isinstance(body.get("content"), str):
                fail("CREATED_BLOB_REQUEST_INVALID")
            state["blob"] = (result or {}).get("sha")
            state["blob_bytes"] = body["content"].encode("utf-8")
        elif method == "POST" and path == "/git/trees":
            state["tree"] = (result or {}).get("sha")
        elif method == "POST" and path == "/git/commits":
            state["commit"] = (result or {}).get("sha")
            state["commit_request"] = dict(body or {})

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
