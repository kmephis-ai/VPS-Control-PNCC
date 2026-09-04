import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/evaluate_windows_installation_first_run_readiness.py"
CONTRACT = ROOT / ".pncc-dev/contracts/windows-installation-first-run-readiness.json"
spec = importlib.util.spec_from_file_location("wu181", SCRIPT)
wu181 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wu181)


class Wu181ReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def evaluate(self, data):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "contract.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return wu181.evaluate(path)

    def test_canonical_contract_passes(self):
        self.assertEqual(self.evaluate(self.base), 0)

    def test_rejects_installer_implementation_authority(self):
        data = copy.deepcopy(self.base)
        data["authority"]["installer_implementation"] = True
        self.assertNotEqual(self.evaluate(data), 0)

    def test_rejects_runtime_authority(self):
        data = copy.deepcopy(self.base)
        data["authority"]["runtime_mutation"] = True
        self.assertNotEqual(self.evaluate(data), 0)

    def test_rejects_1080_automation(self):
        data = copy.deepcopy(self.base)
        data["security_invariants"]["reserve_manual_lifecycle_automation_forbidden"] = False
        self.assertNotEqual(self.evaluate(data), 0)

    def test_rejects_plaintext_putty_transport(self):
        data = copy.deepcopy(self.base)
        data["security_invariants"]["putty_password_transport"] = "-pw"
        self.assertNotEqual(self.evaluate(data), 0)

    def test_rejects_hostkey_weakening(self):
        data = copy.deepcopy(self.base)
        data["security_invariants"]["host_key_verification"] = "disabled"
        self.assertNotEqual(self.evaluate(data), 0)

    def test_rejects_missing_ps51(self):
        data = copy.deepcopy(self.base)
        data["supported_platform"]["powershell"] = ["PowerShell 7"]
        self.assertNotEqual(self.evaluate(data), 0)

    def test_rejects_compiler_pin_authority(self):
        data = copy.deepcopy(self.base)
        data["technology_selection"]["compiler_version_pinned"] = True
        self.assertNotEqual(self.evaluate(data), 0)

    def test_rejects_third_party_auto_install(self):
        data = copy.deepcopy(self.base)
        data["prerequisites"]["automatic_install_of_proxifier"] = True
        self.assertNotEqual(self.evaluate(data), 0)

    def test_rejects_runtime_truth_claim(self):
        data = copy.deepcopy(self.base)
        data["first_run_contract"]["must_not_claim_runtime_truth_without_physical_evidence"] = False
        self.assertNotEqual(self.evaluate(data), 0)


if __name__ == "__main__":
    unittest.main()
