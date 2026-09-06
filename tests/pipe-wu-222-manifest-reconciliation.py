from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src/windows-v7/VPS-Control-v7-SHA256.txt"
BASE = MANIFEST.parent
LINE_RE = re.compile(r"^([0-9a-f]{64})\s+(.+)$")


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    raw = MANIFEST.read_bytes()
    if b"\r\n" in raw or b"\r" in raw:
        print("MANIFEST_CANONICAL_EOL_MISMATCH expected=LF", file=sys.stderr)
        eol_ok = False
    else:
        eol_ok = True

    mismatches: list[str] = []
    checked = 0
    seen: set[str] = set()
    text = raw.decode("utf-8-sig")
    for number, line in enumerate(text.split("\n"), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_RE.fullmatch(line)
        if not match:
            mismatches.append(f"INVALID_LINE line={number} text={line!r}")
            continue
        expected, rel = match.groups()
        rel_posix = rel.replace("\\", "/")
        if rel_posix in seen:
            mismatches.append(f"DUPLICATE_ENTRY path={rel_posix}")
            continue
        seen.add(rel_posix)
        target = BASE / pathlib.PurePosixPath(rel_posix)
        if not target.is_file():
            mismatches.append(f"MISSING_FILE path={rel_posix}")
            continue
        actual = sha256(target)
        checked += 1
        if actual != expected:
            mismatches.append(
                f"SHA256_MISMATCH path={rel_posix} actual={actual} expected={expected}"
            )

    attr = subprocess.run(
        ["git", "check-attr", "eol", "--", "src/windows-v7/VPS-Control-v7-SHA256.txt"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    attr_ok = attr.endswith(": lf")
    if not attr_ok:
        mismatches.append(f"GITATTR_EOL_NOT_LF actual={attr}")

    print(f"MANIFEST_ENTRIES_CHECKED={checked}")
    print(f"MANIFEST_MISMATCH_COUNT={len(mismatches)}")
    for item in mismatches:
        print(item)

    if checked < 1 or mismatches or not eol_ok:
        return 1
    print("PIPE_WU_222_MANIFEST_RECONCILIATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
