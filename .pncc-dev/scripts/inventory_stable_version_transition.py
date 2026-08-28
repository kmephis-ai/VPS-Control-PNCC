#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

OLD = "7.0.0-rc14.39"
NEW = "7.0.0"
SOURCE_ROOT = "src/windows-v7/"
CONTROL_PATHS = (
    ".pncc-dev/candidate-source.json",
    "build/windows-v7-candidate-recipe.json",
    ".github/workflows/candidate-builder.yml",
)


def git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    if p.returncode:
        raise RuntimeError(p.stderr.strip())
    return p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository-root", type=Path, default=Path("."))
    ap.add_argument("--output", type=Path, required=True)
    ns = ap.parse_args()
    root = ns.repository_root.resolve()
    tracked = [x for x in git(root, "ls-files").splitlines() if x]
    rows = []
    for rel in tracked:
        if not (rel.startswith(SOURCE_ROOT) or rel in CONTROL_PATHS):
            continue
        data = (root / rel).read_bytes()
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        count = text.count(OLD)
        if not count:
            continue
        lines = []
        for number, line in enumerate(text.splitlines(), 1):
            if OLD in line:
                lines.append({"line": number, "occurrences": line.count(OLD)})
        rows.append({
            "path": rel,
            "domain": "PRODUCT_SOURCE" if rel.startswith(SOURCE_ROOT) else "BUILD_CONTROL",
            "occurrences": count,
            "lines": lines,
        })
    rows.sort(key=lambda r: r["path"].encode("utf-8"))
    product = [r for r in rows if r["domain"] == "PRODUCT_SOURCE"]
    control = [r for r in rows if r["domain"] == "BUILD_CONTROL"]
    result = {
        "schema_version": 1,
        "contract_id": "PNCC_STABLE_VERSION_TRANSITION_INVENTORY_V1",
        "work_unit_id": "PIPE-WU-043A",
        "source_head_sha": git(root, "rev-parse", "HEAD").strip(),
        "from_version": OLD,
        "to_version": NEW,
        "product_source_files": len(product),
        "product_source_occurrences": sum(r["occurrences"] for r in product),
        "build_control_files": len(control),
        "build_control_occurrences": sum(r["occurrences"] for r in control),
        "files": rows,
        "runtime_authority_transfer": False,
        "product_mutation": False,
        "stable_release_authorized": False,
    }
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PNCC_STABLE_VERSION_INVENTORY=PASS PRODUCT_FILES={len(product)} PRODUCT_OCCURRENCES={result['product_source_occurrences']} CONTROL_FILES={len(control)} CONTROL_OCCURRENCES={result['build_control_occurrences']}")
    for row in rows:
        print(f"VERSION_OCCURRENCE PATH={row['path']} DOMAIN={row['domain']} COUNT={row['occurrences']} LINES={','.join(str(x['line']) for x in row['lines'])}")
    print("PRODUCT_MUTATION=false RUNTIME_AUTHORITY_TRANSFER=false STABLE_RELEASE_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
