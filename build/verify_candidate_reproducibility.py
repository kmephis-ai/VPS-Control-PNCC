#!/usr/bin/env python3
"""Verify two independent PNCC candidate builds are byte-identical."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


class ReproError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ReproError(f"{path}: JSON object required")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify deterministic candidate reproducibility")
    parser.add_argument("--first-dir", type=Path, required=True)
    parser.add_argument("--second-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        first_evidence = load_json(args.first_dir / "build-evidence.single.json")
        second_evidence = load_json(args.second_dir / "build-evidence.single.json")
        stable_keys = (
            "source_commit_sha", "candidate_version", "source_root", "source_file_count",
            "candidate_source_declaration", "recipe", "entries", "deterministic_zip_semantics",
            "runtime_authority", "promotion_authority",
        )
        for key in stable_keys:
            if first_evidence.get(key) != second_evidence.get(key):
                raise ReproError(f"build evidence mismatch at {key}")
        filename = first_evidence.get("artifact", {}).get("filename")
        if not isinstance(filename, str) or not filename:
            raise ReproError("artifact filename missing")
        if second_evidence.get("artifact", {}).get("filename") != filename:
            raise ReproError("artifact filename mismatch")
        first = args.first_dir / filename
        second = args.second_dir / filename
        first_bytes = first.read_bytes()
        second_bytes = second.read_bytes()
        if first_bytes != second_bytes:
            raise ReproError("candidate ZIP bytes differ across independent builds")
        first_sha = sha256(first)
        second_sha = sha256(second)
        if first_sha != second_sha:
            raise ReproError("candidate SHA-256 mismatch")
        if len(first_bytes) != len(second_bytes):
            raise ReproError("candidate size mismatch")
        artifact = first_evidence.get("artifact", {})
        if artifact.get("sha256") != first_sha or artifact.get("size_bytes") != len(first_bytes):
            raise ReproError("first build evidence artifact identity mismatch")
        if second_evidence.get("artifact", {}).get("sha256") != second_sha:
            raise ReproError("second build evidence artifact identity mismatch")
        combined = dict(first_evidence)
        combined["reproducibility"] = {
            "independent_builds": 2, "byte_identical": True,
            "first_sha256": first_sha, "second_sha256": second_sha,
            "first_size_bytes": len(first_bytes), "second_size_bytes": len(second_bytes),
        }
        combined.pop("evidence_id", None)
        combined["evidence_id"] = "PNCC_DETERMINISTIC_CANDIDATE_BUILD_REPRODUCIBILITY_V1"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
        print(f"CANDIDATE_REPRODUCIBILITY=PASS SHA256={first_sha} SIZE={len(first_bytes)} INDEPENDENT_BUILDS=2")
        return 0
    except Exception as exc:
        print(f"CANDIDATE_REPRODUCIBILITY=FAIL ERROR={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
