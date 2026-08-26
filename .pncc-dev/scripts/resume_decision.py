#!/usr/bin/env python3
"""Executable fail-closed resume decision for PNCC durable development state."""
from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pncc_state", ROOT / ".pncc-dev/scripts/validate_state.py")
state = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(state)


def decide_for_holder(work_unit: dict, checkpoint: dict, lease: dict, provider_truth: dict, *, holder: str, now_iso: str) -> dict:
    try:
        state.validate_writer_lease(lease)
    except state.ContractError as exc:
        return {"status": "BLOCK", "reasons": [str(exc)], "next_natural_boundary": None}
    if lease["holder"] != holder:
        return {"status": "BLOCK", "reasons": ["LEASE_HOLDER_MISMATCH"], "next_natural_boundary": None}
    return state.decide_resume(work_unit, checkpoint, lease, provider_truth, now_iso)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-unit", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--lease", required=True)
    parser.add_argument("--provider-truth", required=True)
    parser.add_argument("--holder", required=True)
    parser.add_argument("--now", required=True)
    args = parser.parse_args()
    try:
        result = decide_for_holder(
            state.load_json(Path(args.work_unit)),
            state.load_json(Path(args.checkpoint)),
            state.load_json(Path(args.lease)),
            state.load_json(Path(args.provider_truth)),
            holder=args.holder,
            now_iso=args.now,
        )
    except state.ContractError as exc:
        result = {"status": "BLOCK", "reasons": [str(exc)], "next_natural_boundary": None}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in {"RESUME_ALLOWED", "WAITING_PROVIDER_CHECKS", "WAITING_RUNTIME"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
