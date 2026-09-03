#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def evaluate(plan: dict) -> dict:
    required = {
        "repository", "base_sha", "branch", "path", "content_b64_sha",
        "decoded_bytes_sha", "expected_git_blob_sha", "force_ref_update",
        "immutable_readback", "owner_authorization"
    }
    if set(plan) != required:
        return {"decision": "BLOCKED", "reason": "PLAN_SCHEMA_MISMATCH"}
    if plan["repository"] != "kmephis-ai/VPS-Control-PNCC":
        return {"decision": "BLOCKED", "reason": "REPOSITORY_MISMATCH"}
    if not SHA40.fullmatch(str(plan["base_sha"])):
        return {"decision": "BLOCKED", "reason": "BASE_SHA_INVALID"}
    branch = str(plan["branch"])
    if branch == "main" or not branch.startswith("agent/"):
        return {"decision": "BLOCKED", "reason": "BOUNDED_BRANCH_REQUIRED"}
    path = str(plan["path"])
    if not path or path.startswith("/") or ".." in Path(path).parts:
        return {"decision": "BLOCKED", "reason": "PATH_INVALID"}
    if plan["force_ref_update"] is not False:
        return {"decision": "BLOCKED", "reason": "FORCE_REF_FORBIDDEN"}
    if plan["immutable_readback"] is not True:
        return {"decision": "BLOCKED", "reason": "IMMUTABLE_READBACK_REQUIRED"}
    if plan["owner_authorization"] is not True:
        return {"decision": "BLOCKED", "reason": "OWNER_AUTHORIZATION_REQUIRED"}
    for key in ("content_b64_sha", "decoded_bytes_sha", "expected_git_blob_sha"):
        if not SHA40.fullmatch(str(plan[key])):
            return {"decision": "BLOCKED", "reason": key.upper() + "_INVALID"}
    if plan["decoded_bytes_sha"] != plan["expected_git_blob_sha"]:
        return {"decision": "BLOCKED", "reason": "EXACT_BYTE_GIT_BLOB_IDENTITY_MISMATCH"}
    return {"decision": "READY_FOR_SEPARATE_OWNER_AUTHORIZED_EXECUTION", "reason": "READINESS_CONTRACT_SATISFIED"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    a = p.parse_args()
    result = evaluate(json.loads(Path(a.input).read_text(encoding="utf-8")))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"].startswith("READY_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
