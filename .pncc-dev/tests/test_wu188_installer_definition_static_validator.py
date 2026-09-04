import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev" / "scripts" / "wu188_installer_definition_static_validator.py"
spec = importlib.util.spec_from_file_location("wu188", SCRIPT)
wu188 = importlib.util.module_from_spec(spec)
sys.modules["wu188"] = wu188
spec.loader.exec_module(wu188)

GOOD = f"""
; PNCC future installer-definition proposal text only
; Windows 10 target intent
; PowerShell 5.1 compatibility required
; 127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY
; 127.0.0.1:1081 = PRIMARY_AUTO
; V6.3.1 immutable SHA-256 {wu188.V631_SHA256}
; PuTTY transport uses -pwfile only
; host-key verification is fail-closed and must remain enabled
"""

class WU188ValidatorTests(unittest.TestCase):
    def assert_blocked(self, text, reason):
        d = wu188.validate_text(text)
        self.assertEqual("BLOCKED", d.classification)
        self.assertIn(reason, d.reasons)

    def test_synthetic_safe_text_admitted(self):
        d = wu188.validate_text(GOOD)
        self.assertEqual("ADMITTED", d.classification)
        self.assertEqual((), d.reasons)

    def test_empty_blocks(self):
        self.assert_blocked("", "EMPTY_PROPOSAL_TEXT")

    def test_missing_required_marker_blocks(self):
        self.assert_blocked(GOOD.replace("Windows 10 target intent", "Windows target intent"), "MISSING_WINDOWS10_INTENT")

    def test_plaintext_putty_pw_blocks(self):
        self.assert_blocked(GOOD + "\nplink.exe -pw hunter2 host", "PLAINTEXT_PUTTY_PASSWORD")

    def test_embedded_password_blocks(self):
        self.assert_blocked(GOOD + "\nPassword=secret123", "EMBEDDED_PASSWORD")

    def test_hostkey_bypass_blocks(self):
        self.assert_blocked(GOOD + "\nDisable host key verification", "HOSTKEY_BYPASS")

    def test_auto_1080_blocks(self):
        self.assert_blocked(GOOD + "\nrestart tunnel on 1080 automatically", "AUTO_1080_LIFECYCLE")

    def test_v631_mutation_blocks(self):
        self.assert_blocked(GOOD + "\nreplace V6.3.1 during setup", "V631_MUTATION")

    def test_network_download_blocks(self):
        self.assert_blocked(GOOD + "\ncurl https://example.invalid/tool.exe", "INSTALLER_NETWORK_EXEC")

    def test_compiler_exec_blocks(self):
        self.assert_blocked(GOOD + "\nrun ISCC.exe during setup", "COMPILER_EXEC")

    def test_security_weakening_blocks(self):
        self.assert_blocked(GOOD + "\ndisable security verification", "SECURITY_WEAKENING")

    def test_1080_role_contradiction_blocks(self):
        self.assert_blocked(GOOD + "\n1080 = PRIMARY_AUTO", "PORT_ROLE_CONTRADICTION_1080")

    def test_1081_role_contradiction_blocks(self):
        self.assert_blocked(GOOD + "\n1081 = MANUAL_ONLY", "PORT_ROLE_CONTRADICTION_1081")

    def test_output_is_deterministic(self):
        a = wu188.validate_text(GOOD + "\nPassword=secret123\nDisable host key verification")
        b = wu188.validate_text(GOOD + "\nDisable host key verification\nPassword=secret123")
        self.assertEqual(sorted(a.reasons), list(a.reasons))
        self.assertEqual(a.reasons, b.reasons)

if __name__ == "__main__":
    unittest.main()
