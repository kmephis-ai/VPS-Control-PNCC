#!/usr/bin/env python3
"""Collect same-SHA GitHub engineering checks for governed candidate manifest."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REQUIRED_CHECKS = (
    "repo-integrity", "powershell-static", "truth-contract", "adwf-binding", "pipeline-state",
    "quality-fast", "quality-deep", "candidate-artifact-truth",
    "candidate-build-input-readiness", "canonical-source-admission",
)


class CheckError(RuntimeError):
    pass


def fetch_check_runs(repository: str, sha: str, token: str) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{repository}/commits/{sha}/check-runs?per_page=100"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "pncc-candidate-builder",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise CheckError(f"GitHub check-runs HTTP {exc.code}: {body[:500]}") from exc
    runs = payload.get("check_runs")
    if not isinstance(runs, list):
        raise CheckError("GitHub check-runs response missing array")
    return [item for item in runs if isinstance(item, dict)]


def select_latest_by_name(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = run.get("name")
        run_id = run.get("id")
        if not isinstance(name, str) or not isinstance(run_id, int):
            continue
        current = selected.get(name)
        if current is None or int(current.get("id", -1)) < run_id:
            selected[name] = run
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect exact-SHA successful PNCC engineering checks")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=5)
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ENGINEERING_CHECKS=FAIL ERROR=GITHUB_TOKEN missing", file=sys.stderr)
        return 1
    if len(args.sha) != 40 or any(ch not in "0123456789abcdef" for ch in args.sha):
        print("ENGINEERING_CHECKS=FAIL ERROR=invalid lowercase SHA40", file=sys.stderr)
        return 1
    deadline = time.monotonic() + max(1, args.timeout_seconds)
    try:
        while True:
            latest = select_latest_by_name(fetch_check_runs(args.repository, args.sha, token))
            states: list[str] = []
            ready = True
            failed = []
            for name in REQUIRED_CHECKS:
                run = latest.get(name)
                if run is None:
                    ready = False
                    states.append(f"{name}=MISSING")
                    continue
                status = run.get("status")
                conclusion = run.get("conclusion")
                states.append(f"{name}={status}/{conclusion}")
                if status != "completed":
                    ready = False
                elif conclusion != "success":
                    failed.append(f"{name}:{conclusion}")
            if failed:
                raise CheckError("required engineering check failed: " + ",".join(failed))
            if ready:
                output = [{"name": name, "conclusion": "SUCCESS", "subject_sha": args.sha} for name in REQUIRED_CHECKS]
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
                print(f"ENGINEERING_CHECKS=PASS SUBJECT_SHA={args.sha} REQUIRED={len(REQUIRED_CHECKS)}")
                return 0
            if time.monotonic() >= deadline:
                raise CheckError("timeout waiting for checks: " + " ".join(states))
            print("ENGINEERING_CHECKS=WAIT " + " ".join(states), flush=True)
            time.sleep(max(1, args.poll_seconds))
    except Exception as exc:
        print(f"ENGINEERING_CHECKS=FAIL ERROR={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
