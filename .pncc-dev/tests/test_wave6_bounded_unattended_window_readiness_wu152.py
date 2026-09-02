import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "wave6-bounded-unattended-development-window-readiness-wu152.json"
SCRIPT = ROOT / "scripts" / "evaluate_wave6_bounded_unattended_window_readiness_wu152.py"

spec = importlib.util.spec_from_file_location("wu152", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_canonical_contract_passes_without_activation():
    result = mod.evaluate(load_contract())
    assert result["state"] == "PASS"
    assert result["ready_for_owner_activation_decision"] is True
    assert result["unattended_mutation_activated"] is False
    assert result["authority_granted"] is False


def test_rejects_unbounded_work_unit_budget():
    c = load_contract()
    c["recommended_initial_envelope"]["max_work_units"] = 4
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_rejects_unbounded_time_budget():
    c = load_contract()
    c["recommended_initial_envelope"]["max_wall_clock_minutes"] = 91
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_rejects_parallel_mutating_writers():
    c = load_contract()
    c["recommended_initial_envelope"]["max_parallel_mutating_writers"] = 2
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_rejects_authority_carry_across_work_units():
    c = load_contract()
    c["recommended_initial_envelope"]["carry_authority_across_work_units"] = True
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_rejects_cross_domain_lease_reuse():
    c = load_contract()
    c["recommended_initial_envelope"]["reuse_writer_lease_across_conflict_domains"] = True
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_rejects_any_new_authority():
    for key in mod.FALSE_AUTHORITY_KEYS:
        c = load_contract()
        c["authority"][key] = True
        result = mod.evaluate(c)
        assert result["state"] == "FAIL_CLOSED", key


def test_rejects_missing_waiting_runtime_stop():
    c = load_contract()
    c["mandatory_stop_conditions"].remove("WAITING_RUNTIME")
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_rejects_missing_unknown_truth_stop():
    c = load_contract()
    c["mandatory_stop_conditions"].remove("UNKNOWN_OR_STALE_PROVIDER_TRUTH")
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_rejects_activation_performed_in_readiness_wu():
    c = load_contract()
    c["activation_decision"]["performed"] = True
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_owner_decision_remains_mandatory():
    c = load_contract()
    c["activation_decision"]["separate_owner_decision_required"] = False
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"


def test_durable_resume_requires_fresh_provider_reconciliation():
    c = load_contract()
    c["durable_stop_semantics"]["resume_requires_fresh_provider_reconciliation"] = False
    assert mod.evaluate(c)["state"] == "FAIL_CLOSED"
