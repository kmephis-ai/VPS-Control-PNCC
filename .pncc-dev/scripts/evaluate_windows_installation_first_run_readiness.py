#!/usr/bin/env python3
import json
import pathlib
import re
import sys

EXPECTED_BASE = "3159da904a3f0741804cd3f67332e6e40c434604"
EXPECTED_V631 = "385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e"
EXPECTED_TECH = "Inno Setup 7"
EXPECTED_RESULTS = ["READY", "ATTENTION_REQUIRED", "BLOCKED"]
EXPECTED_POWERSHELL = ["Windows PowerShell 5.1", "PowerShell 7"]


def fail(code, detail=""):
    print(f"WU181_READINESS=BLOCKED code={code} detail={detail}")
    return 1


def evaluate(path):
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        return fail("CONTRACT_READ_ERROR", str(exc))

    checks = [
        (data.get("schema_version") == 1, "SCHEMA"),
        (data.get("role") == "WINDOWS_INSTALLATION_FIRST_RUN_READINESS", "ROLE"),
        (data.get("work_unit") == "PIPE-WU-181", "WORK_UNIT"),
        (data.get("base_sha") == EXPECTED_BASE, "BASE_SHA"),
        (data.get("status") == "READY_FOR_SEPARATE_IMPLEMENTATION_WU", "STATUS"),
    ]
    for ok, code in checks:
        if not ok:
            return fail(code)

    tech = data.get("technology_selection", {})
    if tech.get("installer_family") != EXPECTED_TECH:
        return fail("INSTALLER_FAMILY")
    if tech.get("compiler_version_pinned") is not False:
        return fail("COMPILER_PIN_FORBIDDEN")
    if tech.get("delivery_shape") != "single-exe":
        return fail("DELIVERY_SHAPE")
    if re.search(r"\b7\.\d+(?:\.\d+)?\b", tech.get("installer_family", "")):
        return fail("INSTALLER_VERSION_PINNED")

    platform = data.get("supported_platform", {})
    if platform.get("os") != "Windows 10" or platform.get("powershell") != EXPECTED_POWERSHELL:
        return fail("PLATFORM_COMPATIBILITY")

    prereq = data.get("prerequisites", {})
    required = set(prereq.get("required_discovery", []))
    must = {
        "PowerShell compatibility",
        "Proxifier discovery/readiness",
        "PuTTY discovery/readiness",
        "credential storage readiness",
        "host-key trust readiness",
        "PRIMARY_AUTO 127.0.0.1:1081 readiness",
        "RESERVE_MANUAL 127.0.0.1:1080 visibility/readiness",
    }
    if not must.issubset(required):
        return fail("PREREQUISITE_INVENTORY")
    if prereq.get("automatic_install_of_proxifier") is not False or prereq.get("automatic_install_of_putty") is not False:
        return fail("THIRD_PARTY_AUTO_INSTALL_AUTHORITY")

    lifecycle = data.get("lifecycle_contract", {})
    for key in ("fresh_install", "upgrade", "migration", "repair", "uninstall", "rollback"):
        if not lifecycle.get(key):
            return fail("LIFECYCLE_CONTRACT", key)

    first = data.get("first_run_contract", {})
    if first.get("result_states") != EXPECTED_RESULTS:
        return fail("FIRST_RUN_STATES")
    if first.get("must_explain") != ["what happened", "why", "what the user can do next"]:
        return fail("EXPLAINABILITY")
    if first.get("must_not_claim_runtime_truth_without_physical_evidence") is not True:
        return fail("RUNTIME_TRUTH_BOUNDARY")
    if first.get("must_not_weaken_security") is not True:
        return fail("SECURITY_BOUNDARY")

    sec = data.get("security_invariants", {})
    expected_security = {
        "primary_auto": "127.0.0.1:1081",
        "reserve_manual": "127.0.0.1:1080",
        "reserve_manual_lifecycle_automation_forbidden": True,
        "v631_sha256": EXPECTED_V631,
        "v631_mutation_forbidden": True,
        "dpapi_plaintext_export_forbidden": True,
        "putty_password_transport": "-pwfile",
        "plaintext_putty_pw_forbidden": True,
        "host_key_verification": "fail-closed",
    }
    for key, value in expected_security.items():
        if sec.get(key) != value:
            return fail("SECURITY_INVARIANT", key)

    authority = data.get("authority", {})
    required_false = {
        "installer_implementation", "binary_build", "runtime_execution", "runtime_mutation",
        "release", "tag", "promotion", "stable", "ruleset_or_security_weakening", "self_hosted_runner"
    }
    if any(authority.get(key) is not False for key in required_false):
        return fail("AUTHORITY_ESCALATION")

    print("WU181_READINESS=READY_FOR_SEPARATE_IMPLEMENTATION_WU")
    return 0


if __name__ == "__main__":
    contract = sys.argv[1] if len(sys.argv) > 1 else ".pncc-dev/contracts/windows-installation-first-run-readiness.json"
    raise SystemExit(evaluate(contract))
