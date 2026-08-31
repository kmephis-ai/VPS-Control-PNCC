import copy
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_autonomous_continuation_human_by_exception_durable_multi_session_steady_state_wu132.py"
spec = importlib.util.spec_from_file_location("wu132_validator", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def canonical():
    import json
    return json.loads(module.EVIDENCE.read_text(encoding="utf-8"))


def test_canonical_passes():
    assert module.validate(canonical()) == []


def test_duplicate_fingerprint_fails():
    data = canonical()
    data["sessions"][1]["completed_transaction_fingerprint_sha256"] = data["sessions"][0]["completed_transaction_fingerprint_sha256"]
    errors = module.validate(data)
    assert any("fingerprint" in e for e in errors)


def test_stale_decision_reuse_fails():
    data = canonical()
    data["sessions"][1]["persisted_decisions_discarded"] = False
    errors = module.validate(data)
    assert any("persisted decisions" in e for e in errors)


def test_replay_acceptance_fails():
    data = canonical()
    data["sessions"][0]["replay_outcome"] = "ACCEPTED"
    errors = module.validate(data)
    assert any("replay" in e for e in errors)


def test_wrong_generation_fails():
    data = canonical()
    data["sessions"][0]["registry_generation_after"] = 42
    errors = module.validate(data)
    assert any("generation" in e for e in errors)


def test_wrong_branch_readback_fails():
    data = canonical()
    data["sessions"][1]["branch_readback_sha"] = "0" * 40
    errors = module.validate(data)
    assert any("branch readback" in e for e in errors)
