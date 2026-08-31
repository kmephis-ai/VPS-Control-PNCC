import copy
import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_autonomous_continuation_human_by_exception_durable_multi_session_steady_state_wu132.py"
spec = importlib.util.spec_from_file_location("wu132_validator", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def canonical():
    return json.loads(module.EVIDENCE.read_text(encoding="utf-8"))


class DurableMultiSessionSteadyStateWu132Tests(unittest.TestCase):
    def test_canonical_passes(self):
        self.assertEqual(module.validate(canonical()), [])

    def test_duplicate_fingerprint_fails(self):
        data = canonical()
        data["sessions"][1]["completed_transaction_fingerprint_sha256"] = data["sessions"][0]["completed_transaction_fingerprint_sha256"]
        errors = module.validate(data)
        self.assertTrue(any("fingerprint" in error for error in errors))

    def test_stale_decision_reuse_fails(self):
        data = canonical()
        data["sessions"][1]["persisted_decisions_discarded"] = False
        errors = module.validate(data)
        self.assertTrue(any("persisted decisions" in error for error in errors))

    def test_replay_acceptance_fails(self):
        data = canonical()
        data["sessions"][0]["replay_outcome"] = "ACCEPTED"
        errors = module.validate(data)
        self.assertTrue(any("replay" in error for error in errors))

    def test_wrong_generation_fails(self):
        data = canonical()
        data["sessions"][0]["registry_generation_after"] = 42
        errors = module.validate(data)
        self.assertTrue(any("generation" in error for error in errors))

    def test_wrong_branch_readback_fails(self):
        data = canonical()
        data["sessions"][1]["branch_readback_sha"] = "0" * 40
        errors = module.validate(data)
        self.assertTrue(any("branch readback" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
