#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[2]
WU188_PATH = ROOT / ".pncc-dev" / "scripts" / "wu188_installer_definition_static_validator.py"


def _load_wu188():
    spec = importlib.util.spec_from_file_location("pncc_wu188_static_validator", WU188_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("WU188 validator import specification unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


WU188 = _load_wu188()


def build_envelope(text: Any) -> dict[str, Any]:
    reasons: list[str]
    if not isinstance(text, str):
        raw = b""
        classification = "BLOCKED"
        reasons = ["INVALID_PROPOSAL_TEXT_TYPE"]
    else:
        raw = text.encode("utf-8", errors="strict")
        decision = WU188.validate_text(text)
        classification = decision.classification
        reasons = sorted(set(decision.reasons))

    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-189",
        "source_validator_work_unit": "PIPE-WU-188",
        "classification": classification,
        "reasons": reasons,
        "proposal_sha256": hashlib.sha256(raw).hexdigest(),
        "proposal_byte_count": len(raw),
        "exact_utf8_bytes": True,
        "newline_normalization": False,
        "installer_definition_identity_bound": False,
        "materialization_authorized": False,
        "build_authorized": False,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WU189 exact UTF-8 installer-definition proposal envelope")
    parser.add_argument("--text", required=True, help="Proposal text supplied directly; no filesystem input is accepted")
    args = parser.parse_args(list(argv) if argv is not None else None)
    envelope = build_envelope(args.text)
    print(json.dumps(envelope, sort_keys=True, ensure_ascii=False))
    return 0 if envelope["classification"] == "ADMITTED" else 2


if __name__ == "__main__":
    sys.exit(main())
