from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/wu195_canonical_installer_definition_proposal.py"
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-wu195-canonical-installer-definition-proposal.json"
spec = importlib.util.spec_from_file_location("wu195", SCRIPT)
assert spec and spec.loader
WU195 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = WU195
spec.loader.exec_module(WU195)


def contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class WU195Tests(unittest.TestCase):
    def test_canonical_contract_is_ready(self):
        result = WU195.evaluate(contract())
        self.assertEqual("CANONICAL_PROPOSAL_IDENTITY_READY", result["decision"])
        self.assertEqual([], result["reasons"])
        self.assertEqual("125e333203237ed2bb4730f7ad13607baf560421650cb58a554ce589591f8c33", result["proposal_sha256"])
        self.assertEqual(1120, result["proposal_byte_count"])
        self.assertTrue(result["wu188_static_admitted"])

    def test_unknown_contract_key_fails_closed(self):
        value = contract(); value["unexpected"] = True
        self.assertIn("INVALID_CONTRACT_KEYS", WU195.evaluate(value)["reasons"])

    def test_byte_change_fails_digest_and_count(self):
        value = contract(); value["proposal_text"] += "; drift\n"
        result = WU195.evaluate(value)
        self.assertIn("PROPOSAL_SHA256_MISMATCH", result["reasons"])
        self.assertIn("PROPOSAL_BYTE_COUNT_MISMATCH", result["reasons"])

    def test_target_path_is_exact(self):
        value = contract(); value["target_path"] = "installer/windows/VPS-Control-v7.iss"
        self.assertIn("INVALID_TARGET_PATH", WU195.evaluate(value)["reasons"])

    def test_active_execution_sections_fail(self):
        value = contract(); value["proposal_text"] += "\n[Run]\nFilename: \"cmd.exe\"\n"
        # Re-anchor digest/count so this test proves the semantic block independently.
        import hashlib
        raw = value["proposal_text"].encode("utf-8")
        value["proposal_sha256"] = hashlib.sha256(raw).hexdigest()
        value["proposal_byte_count"] = len(raw)
        self.assertIn("ACTIVE_INSTALLER_EXECUTION_SECTION", WU195.evaluate(value)["reasons"])

    def test_authority_escalation_fails(self):
        for key in ("materialization_authority", "compiler_execution_authorized", "build_authorized", "runtime_authority", "promotion_authority"):
            with self.subTest(key=key):
                value = contract(); value[key] = True
                self.assertIn(f"AUTHORITY_ESCALATION_{key.upper()}", WU195.evaluate(value)["reasons"])

    def test_wu188_safety_remains_mandatory(self):
        value = contract(); value["proposal_text"] = value["proposal_text"].replace("Windows 10 target intent", "Windows target intent")
        import hashlib
        raw = value["proposal_text"].encode("utf-8")
        value["proposal_sha256"] = hashlib.sha256(raw).hexdigest(); value["proposal_byte_count"] = len(raw)
        self.assertIn("MISSING_WINDOWS10_INTENT", WU195.evaluate(value)["reasons"])


if __name__ == "__main__":
    unittest.main()
