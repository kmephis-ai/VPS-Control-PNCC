#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "kmephis-ai/VPS-Control-PNCC"
ISSUE = 410
WU = "PIPE-WU-180"
MARKER = "PNCC-EXACT-HEAD-CI-DISPATCH-REQUEST"
TARGET_BRANCH = "agent/PIPE-WU-175-v702-activation-wu172-fix"
WORKFLOWS = (
    "canonical-source-admission.yml",
    "candidate-builder.yml",
    "quality-fast.yml",
    "quality-deep.yml",
    "public-safety.yml",
    "wave5-exact-head-ci-inspection-classification.yml",
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class Blocked(RuntimeError):
    pass


def api(path: str, token: str, method: str = "GET", payload=None):
    url = "https://api.github.com" + path
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pncc-wu180-exact-head-dispatch-bridge",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise Blocked(f"GITHUB_HTTP_{exc.code}:{method}:{path}:{body[:300]}") from exc
    except (urllib.error.URLError, UnicodeError, json.JSONDecodeError) as exc:
        raise Blocked("GITHUB_IO_FAILED:" + type(exc).__name__) from exc


def parse_request(body: str) -> dict:
    lines = [line.strip() for line in (body or "").splitlines() if MARKER in line]
    if len(lines) != 1:
        raise Blocked("REQUEST_MARKER_COUNT")
    match = re.search(r"<!--\s*" + re.escape(MARKER) + r"\s+(\{.*\})\s*-->", lines[0])
    if not match:
        raise Blocked("REQUEST_MARKER_FORMAT")
    try:
        obj = json.loads(match.group(1))
    except Exception as exc:
        raise Blocked("REQUEST_JSON_INVALID") from exc
    allowed = {"schema_version", "action", "work_unit", "target_branch", "target_sha", "workflows"}
    if set(obj) != allowed:
        raise Blocked("REQUEST_SCHEMA_MISMATCH")
    if obj["schema_version"] != 1 or obj["action"] != "DISPATCH" or obj["work_unit"] != WU:
        raise Blocked("REQUEST_SCOPE_MISMATCH")
    if obj["target_branch"] != TARGET_BRANCH or obj["target_branch"] == "main":
        raise Blocked("TARGET_BRANCH_MISMATCH")
    if not isinstance(obj["target_sha"], str) or not SHA40.fullmatch(obj["target_sha"]):
        raise Blocked("TARGET_SHA_INVALID")
    if obj["workflows"] != list(WORKFLOWS):
        raise Blocked("WORKFLOW_ALLOWLIST_MISMATCH")
    return obj


def ref_path(branch: str) -> str:
    return f"/repos/{REPO}/git/ref/heads/{urllib.parse.quote(branch, safe='/')}"


def assert_exact_target(token: str, branch: str, sha: str) -> None:
    ref = api(ref_path(branch), token)
    observed = ((ref or {}).get("object") or {}).get("sha")
    if observed != sha:
        raise Blocked("TARGET_REF_MOVED")


def dispatch_one(token: str, workflow: str, branch: str, sha: str) -> None:
    if workflow not in WORKFLOWS:
        raise Blocked("WORKFLOW_NOT_ALLOWLISTED")
    assert_exact_target(token, branch, sha)
    encoded = urllib.parse.quote(workflow, safe="")
    api(
        f"/repos/{REPO}/actions/workflows/{encoded}/dispatches",
        token,
        "POST",
        {"ref": branch},
    )


def execute(request: dict, token: str) -> None:
    branch = request["target_branch"]
    sha = request["target_sha"]
    for workflow in WORKFLOWS:
        dispatch_one(token, workflow, branch, sha)
    assert_exact_target(token, branch, sha)
    print("EXACT_HEAD_DISPATCH=SUCCESS")
    print("TARGET_BRANCH=" + branch)
    print("TARGET_SHA=" + sha)
    print("WORKFLOW_COUNT=" + str(len(WORKFLOWS)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    if args.issue_number != ISSUE or args.repository != REPO:
        raise Blocked("INVOCATION_SCOPE")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise Blocked("TOKEN_MISSING")
    issue = api(f"/repos/{REPO}/issues/{ISSUE}", token)
    if not isinstance(issue, dict) or issue.get("state") != "open" or issue.get("pull_request") is not None:
        raise Blocked("CANONICAL_OPEN_ISSUE_REQUIRED")
    request = parse_request(issue.get("body") or "")
    execute(request, token)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Blocked as exc:
        print("EXACT_HEAD_DISPATCH=BLOCKED")
        print("ERROR=" + str(exc))
        raise SystemExit(2)
