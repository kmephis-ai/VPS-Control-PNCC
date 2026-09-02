import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/validate_wave6_wu156_bounded_unattended_activation.py"
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-wu156-bounded-unattended-activation.json"
RECEIPT = ROOT / ".pncc-dev/attestations/wave6-wu156-bounded-unattended-owner-receipt.json"
READINESS = ROOT / ".pncc-dev/contracts/wave6-unattended-activation-owner-authorization-readiness-wu153.json"
EXPECTED_MAIN = "c94bea2e2a22f802c232d208bf43474a309a143f"

spec = importlib.util.spec_from_file_location("wu156_validator", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def baseline():
    return load(RECEIPT), load(CONTRACT), load(READINESS)


def errors(receipt=None, contract=None, readiness=None, main=EXPECTED_MAIN, now=None):
    r0, c0, a0 = baseline()
    return module.validate(receipt or r0, contract or c0, readiness or a0, main, now)


def test_valid_authorization_shape():
    assert errors(now=datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)) == []


def test_exact_pins_and_budget():
    receipt, contract, readiness = baseline()
    assert contract["authority_grant_sha"] == "ab80e34923fae92124ee1fb1b43e33b63499239d"
    assert contract["owner_receipt_sha"] == "a26d2c28cb01022e7e625ff358fa0e94ffa177b9"
    assert contract["max_work_units"] == 3
    assert contract["work_units_consumed_by_activation"] == 1
    assert contract["work_units_remaining_after_activation"] == 2
    assert contract["max_wall_clock_minutes"] == 90
    assert contract["max_parallel_mutating_writers"] == 1


def test_wrong_main_fails_closed():
    assert "AUTHORIZED_MAIN" in errors(main="0" * 40)


def test_wildcard_domain_fails_closed():
    receipt, contract, readiness = baseline()
    receipt = copy.deepcopy(receipt)
    contract = copy.deepcopy(contract)
    receipt["permitted_conflict_domains"][1] = "wave6-*"
    contract["permitted_conflict_domains"][1] = "wave6-*"
    found = module.validate(receipt, contract, readiness, EXPECTED_MAIN)
    assert "EXACT_DOMAINS" in found
    assert "NON_WILDCARD_DOMAINS" in found


def test_budget_expansion_fails_closed():
    for key, value, expected in (
        ("max_work_units", 4, "MAX_WORK_UNITS"),
        ("max_wall_clock_minutes", 91, "MAX_WALL_CLOCK"),
        ("max_parallel_mutating_writers", 2, "MAX_MUTATING_WRITERS"),
    ):
        receipt, contract, readiness = baseline()
        receipt = copy.deepcopy(receipt)
        contract = copy.deepcopy(contract)
        receipt[key] = value
        contract[key] = value
        assert expected in module.validate(receipt, contract, readiness, EXPECTED_MAIN)


def test_single_use_and_replay_are_mandatory():
    for key, expected in (("single_use", "SINGLE_USE"), ("replay_forbidden", "REPLAY_FORBIDDEN")):
        receipt, contract, readiness = baseline()
        receipt = copy.deepcopy(receipt)
        contract = copy.deepcopy(contract)
        receipt[key] = False
        contract[key] = False
        assert expected in module.validate(receipt, contract, readiness, EXPECTED_MAIN)


def test_forbidden_authority_cannot_be_enabled():
    for key in module.FORBIDDEN_TRUE_KEYS:
        receipt, contract, readiness = baseline()
        contract = copy.deepcopy(contract)
        contract["authority"][key] = True
        assert ("FORBIDDEN_AUTHORITY_" + key.upper()) in module.validate(receipt, contract, readiness, EXPECTED_MAIN)


def test_authority_carry_and_lease_reuse_forbidden():
    for key, expected in (
        ("carry_authority_across_work_units", "NO_AUTHORITY_CARRY"),
        ("reuse_writer_lease_across_conflict_domains", "NO_LEASE_REUSE"),
    ):
        receipt, contract, readiness = baseline()
        contract = copy.deepcopy(contract)
        contract["admission"][key] = True
        assert expected in module.validate(receipt, contract, readiness, EXPECTED_MAIN)


def test_time_window_fail_closed():
    receipt, contract, readiness = baseline()
    assert "AUTHORIZATION_EXPIRED_OR_NOT_YET_VALID" in module.validate(
        receipt, contract, readiness, EXPECTED_MAIN, datetime(2026, 9, 2, 21, 6, 4, tzinfo=timezone.utc)
    )
    contract = copy.deepcopy(contract)
    receipt = copy.deepcopy(receipt)
    contract["expires_at"] = "2026-09-02T21:06:05Z"
    receipt["expires_at"] = contract["expires_at"]
    assert "TIME_ENVELOPE" in module.validate(receipt, contract, readiness, EXPECTED_MAIN)


def test_receipt_contract_mismatch_fails_closed():
    receipt, contract, readiness = baseline()
    receipt = copy.deepcopy(receipt)
    receipt["authorization_id"] = "different"
    assert "RECEIPT_CONTRACT_MISMATCH_AUTHORIZATION_ID" in module.validate(receipt, contract, readiness, EXPECTED_MAIN)


def test_all_stop_conditions_preserved():
    receipt, contract, readiness = baseline()
    contract = copy.deepcopy(contract)
    contract["mandatory_stop_conditions"].remove("WAITING_RUNTIME")
    assert "MANDATORY_STOPS" in module.validate(receipt, contract, readiness, EXPECTED_MAIN)
