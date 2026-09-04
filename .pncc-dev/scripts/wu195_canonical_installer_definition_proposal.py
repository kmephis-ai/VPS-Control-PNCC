#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WU188_PATH = ROOT / ".pncc-dev/scripts/wu188_installer_definition_static_validator.py"
EXPECTED_KEYS = {
    "schema_version", "work_unit_id", "repository", "source_main_sha",
    "source_candidate_version", "source_main_script_path", "source_main_script_git_blob",
    "target_path", "proposal_encoding", "newline_semantic", "proposal_sha256",
    "proposal_byte_count", "proposal_text", "wu188_static_admission_required",
    "materialization_authority", "compiler_execution_authorized", "build_authorized",
    "runtime_authority", "promotion_authority",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


def load_wu188():
    spec = importlib.util.spec_from_file_location("wu188_for_wu195", WU188_PATH)
    if not spec or not spec.loader:
        raise RuntimeError("WU188_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def evaluate(contract: dict, verify_git: bool = False) -> dict:
    reasons: list[str] = []
    if set(contract) != EXPECTED_KEYS:
        reasons.append("INVALID_CONTRACT_KEYS")
    if contract.get("schema_version") != 1 or contract.get("work_unit_id") != "PIPE-WU-195":
        reasons.append("INVALID_CONTRACT_IDENTITY")
    if contract.get("repository") != "kmephis-ai/VPS-Control-PNCC":
        reasons.append("INVALID_REPOSITORY")
    if contract.get("source_candidate_version") != "7.0.2":
        reasons.append("INVALID_SOURCE_VERSION")
    base = contract.get("source_main_sha", "")
    blob = contract.get("source_main_script_git_blob", "")
    if not isinstance(base, str) or not SHA40.fullmatch(base):
        reasons.append("INVALID_SOURCE_MAIN_SHA")
    if not isinstance(blob, str) or not SHA40.fullmatch(blob):
        reasons.append("INVALID_SOURCE_MAIN_SCRIPT_BLOB")
    if contract.get("source_main_script_path") != "src/windows-v7/VPS-Control-v7.ps1":
        reasons.append("INVALID_SOURCE_MAIN_SCRIPT_PATH")
    if contract.get("target_path") != "installer/windows/VPS-Control-PNCC.iss":
        reasons.append("INVALID_TARGET_PATH")
    if contract.get("proposal_encoding") != "UTF-8" or contract.get("newline_semantic") != "LF_EXACT":
        reasons.append("INVALID_BYTE_SEMANTICS")

    text = contract.get("proposal_text")
    if not isinstance(text, str):
        reasons.append("INVALID_PROPOSAL_TEXT")
        text = ""
    raw = text.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    if contract.get("proposal_sha256") != digest or not SHA64.fullmatch(str(contract.get("proposal_sha256", ""))):
        reasons.append("PROPOSAL_SHA256_MISMATCH")
    if contract.get("proposal_byte_count") != len(raw):
        reasons.append("PROPOSAL_BYTE_COUNT_MISMATCH")
    if "\r" in text:
        reasons.append("NON_LF_PROPOSAL_TEXT")

    wu188 = load_wu188()
    static = wu188.validate_text(text)
    if not contract.get("wu188_static_admission_required") or not static.admitted:
        reasons.extend(static.reasons or ("WU188_STATIC_ADMISSION_REQUIRED",))

    for key in (
        "materialization_authority", "compiler_execution_authorized", "build_authorized",
        "runtime_authority", "promotion_authority",
    ):
        if contract.get(key) is not False:
            reasons.append(f"AUTHORITY_ESCALATION_{key.upper()}")

    # Passive package definition only: no installer-triggered execution section.
    if re.search(r"(?im)^\s*\[(?:Run|UninstallRun|Code)\]\s*$", text):
        reasons.append("ACTIVE_INSTALLER_EXECUTION_SECTION")
    if "AppVersion=7.0.2" not in text:
        reasons.append("APP_VERSION_MISMATCH")
    if 'Source: "..\\..\\src\\windows-v7\\*"' not in text:
        reasons.append("SOURCE_TREE_NOT_EXACT")
    if "PrivilegesRequired=lowest" not in text:
        reasons.append("NON_LEAST_PRIVILEGE_INSTALL")

    if verify_git and not reasons:
        try:
            observed_blob = git("rev-parse", f"{base}:{contract['source_main_script_path']}")
            if observed_blob != blob:
                reasons.append("SOURCE_MAIN_SCRIPT_BLOB_MISMATCH")
            source = subprocess.check_output(
                ["git", "show", f"{base}:{contract['source_main_script_path']}"], cwd=ROOT
            )
            if b"VPS Control Center v7.0.2" not in source or b"$UiVersion = '7.0.2'" not in source:
                reasons.append("SOURCE_VERSION_SURFACE_MISMATCH")
        except subprocess.CalledProcessError:
            reasons.append("SOURCE_GIT_ANCHOR_UNRESOLVED")

    reasons = sorted(set(reasons))
    return {
        "decision": "CANONICAL_PROPOSAL_IDENTITY_READY" if not reasons else "BLOCKED",
        "reasons": reasons,
        "target_path": contract.get("target_path", ""),
        "proposal_sha256": digest,
        "proposal_byte_count": len(raw),
        "source_main_sha": base,
        "source_main_script_git_blob": blob,
        "wu188_static_admitted": static.admitted,
        "materialization_authority": False,
        "compiler_execution_authorized": False,
        "build_authorized": False,
        "runtime_authority": False,
        "promotion_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--verify-git", action="store_true")
    args = parser.parse_args()
    try:
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
        result = evaluate(contract, verify_git=args.verify_git)
    except Exception as exc:
        print(json.dumps({"decision": "BLOCKED", "reasons": [type(exc).__name__]}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] == "CANONICAL_PROPOSAL_IDENTITY_READY" else 2


if __name__ == "__main__":
    sys.exit(main())
