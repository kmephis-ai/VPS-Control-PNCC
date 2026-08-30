#!/usr/bin/env python3
"""Fail-closed WU-105 exception for legacy Writer Lease PR path guards.

Historical Writer Lease workflows treated any external-binding change as a protected
surface violation. PIPE-WU-105 is explicitly scoped to reconcile that proof-only
provenance. This checker permits only the exact WU-105 provenance transition while
preserving all Writer Lease/provider-state/runtime protections and all WU-103
materialization anchors byte-for-byte.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_BASE = "083d999647e1c6c43f5a088849b7ef60edaa9c66"
EXPECTED_BINDING_BLOB = "d522b5f9b9e2370a9f172c9c9406eae785ab6335"
EXPECTED_READINESS_BLOB = "68ce73e311e3d8a2798557244c6f8f9129c020fc"
EXPECTED_READINESS_CHECKER_BLOB = "7440c1c19baf099e29bbbfcca311162029f00017"
EXPECTED_TRANSITION_BLOB = "5cac3b434279b056914f99c082033656831da5bf"
EXPECTED_ANCHORS = {
    ".pncc-dev/scripts/plan_governed_work_unit_materialization.py": "c561b34dbf3fb7cfefd1a2a9780aba6e857ec78c",
    ".pncc-dev/contracts/governed-work-unit-materialization-policy.json": "8b6b6d9116b96a8f4746c22906a522589a9ae6e0",
    ".pncc-dev/contracts/reusable-canonical-work-unit-materialization-authorized.json": "39db0554b86932b1beb4bb7250d040c06f9371ea",
    ".pncc-dev/scripts/select_provider_work_unit.py": "8045a97d5344f058064690cb265b30f88973e2b8",
    "docs/governance/PROVIDER_TRUTH_WORK_UNIT_SELECTION.md": "c6b5c9e394415febd586273d3e64ef01c8628cf8",
    ".pncc-dev/schemas/work-unit.schema.json": "a6b23c5695262192175216e6293d832f8e835851",
}
ALWAYS_FORBIDDEN_PREFIXES = (
    ".pncc-state/",
    "src/windows-v7/",
    "tools/runtime-agent/",
)
ALWAYS_FORBIDDEN_EXACT = {
    ".pncc-dev/schemas/writer-lease.schema.json",
    ".pncc-dev/examples/writer-lease.valid.json",
}
BINDING = ".adwf-consumer/external-binding.json"
READINESS = ".adwf-consumer/wave5-readiness.json"
CHECKER = ".pncc-dev/scripts/check_wave5_adwf_readiness.py"
TRANSITION = ".pncc-dev/contracts/governed-frontier-transition-pipe-wu-105.json"


def fail(reason: str) -> None:
    print("WU105_PROVENANCE_COMPATIBILITY=BLOCKED")
    print("REASON=" + reason)
    raise SystemExit(2)


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        fail("GIT_COMMAND_FAILED:" + " ".join(args))
    return proc.stdout.strip()


def require_blob(path: str, expected: str) -> None:
    if not (ROOT / path).is_file():
        fail("MISSING_PATH:" + path)
    actual = git("hash-object", path)
    if actual != expected:
        fail(f"BLOB_DRIFT:{path}:{actual}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ns = ap.parse_args()

    changed = [line for line in git("diff", "--name-only", ns.base, ns.head).splitlines() if line]
    for path in changed:
        if path in ALWAYS_FORBIDDEN_EXACT or any(path.startswith(prefix) for prefix in ALWAYS_FORBIDDEN_PREFIXES):
            fail("PROTECTED_SURFACE_CHANGED:" + path)

    if BINDING in changed:
        if ns.base != EXPECTED_BASE:
            fail("EXTERNAL_BINDING_CHANGE_OUTSIDE_WU105_BASE")
        for required in (BINDING, READINESS, CHECKER, TRANSITION):
            if required not in changed:
                fail("WU105_REQUIRED_COMPANION_NOT_CHANGED:" + required)
        require_blob(BINDING, EXPECTED_BINDING_BLOB)
        require_blob(READINESS, EXPECTED_READINESS_BLOB)
        require_blob(CHECKER, EXPECTED_READINESS_CHECKER_BLOB)
        require_blob(TRANSITION, EXPECTED_TRANSITION_BLOB)
        for path, blob in EXPECTED_ANCHORS.items():
            require_blob(path, blob)
        proc = subprocess.run(
            ["python3", CHECKER],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(proc.stdout, end="")
        if proc.returncode != 0:
            fail("WU105_READINESS_CHECKER_FAILED")
    elif ns.base == EXPECTED_BASE and READINESS in changed:
        fail("WU105_READINESS_CHANGED_WITHOUT_BINDING")

    print("WU105_PROVENANCE_COMPATIBILITY=PASS")
    print("EXTERNAL_BINDING_EXCEPTION=" + ("EXACT_WU105_PROOF_ONLY" if BINDING in changed else "NOT_USED"))
    print("PROVIDER_STATE_MUTATION=false")
    print("PRODUCT_RUNTIME_MUTATION=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
