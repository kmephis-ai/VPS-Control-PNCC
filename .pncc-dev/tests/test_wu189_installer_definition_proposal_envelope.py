import hashlib
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev" / "scripts" / "wu189_installer_definition_proposal_envelope.py"
spec = importlib.util.spec_from_file_location("wu189", SCRIPT)
wu189 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wu189
spec.loader.exec_module(wu189)

GOOD = f"""; PNCC future installer-definition proposal text only
; Windows 10 target intent
; PowerShell 5.1 compatibility required
; 127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY
; 127.0.0.1:1081 = PRIMARY_AUTO
; V6.3.1 immutable SHA-256 {wu189.WU188.V631_SHA256}
; PuTTY transport uses -pwfile only
; host-key verification is fail-closed and must remain enabled
"""


class WU189EnvelopeTests(unittest.TestCase):
    def test_safe_text_admitted_without_authority(self):
        e = wu189.build_envelope(GOOD)
        self.assertEqual("ADMITTED", e["classification"])
        self.assertEqual([], e["reasons"])
        self.assertFalse(e["installer_definition_identity_bound"])
        self.assertFalse(e["materialization_authorized"])
        self.assertFalse(e["build_authorized"])

    def test_same_text_same_envelope(self):
        self.assertEqual(wu189.build_envelope(GOOD), wu189.build_envelope(GOOD))

    def test_exact_utf8_digest_and_byte_count(self):
        raw = GOOD.encode("utf-8")
        e = wu189.build_envelope(GOOD)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), e["proposal_sha256"])
        self.assertEqual(len(raw), e["proposal_byte_count"])
        self.assertTrue(e["exact_utf8_bytes"])
        self.assertFalse(e["newline_normalization"])

    def test_one_byte_change_changes_digest(self):
        a = wu189.build_envelope(GOOD)
        b = wu189.build_envelope(GOOD + "x")
        self.assertNotEqual(a["proposal_sha256"], b["proposal_sha256"])

    def test_lf_vs_crlf_remain_distinct(self):
        lf = GOOD
        crlf = GOOD.replace("\n", "\r\n")
        a = wu189.build_envelope(lf)
        b = wu189.build_envelope(crlf)
        self.assertNotEqual(a["proposal_sha256"], b["proposal_sha256"])
        self.assertNotEqual(a["proposal_byte_count"], b["proposal_byte_count"])

    def test_unicode_byte_identity(self):
        text = GOOD + "; Примечание: проверка UTF-8\n"
        raw = text.encode("utf-8")
        e = wu189.build_envelope(text)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), e["proposal_sha256"])
        self.assertEqual(len(raw), e["proposal_byte_count"])

    def test_non_string_blocks_fail_closed(self):
        e = wu189.build_envelope({"text": GOOD})
        self.assertEqual("BLOCKED", e["classification"])
        self.assertEqual(["INVALID_PROPOSAL_TEXT_TYPE"], e["reasons"])
        self.assertEqual(hashlib.sha256(b"").hexdigest(), e["proposal_sha256"])
        self.assertEqual(0, e["proposal_byte_count"])

    def test_empty_propagates_wu188_block(self):
        e = wu189.build_envelope("")
        self.assertEqual("BLOCKED", e["classification"])
        self.assertIn("EMPTY_PROPOSAL_TEXT", e["reasons"])

    def test_plaintext_putty_password_propagates_block(self):
        e = wu189.build_envelope(GOOD + "\nplink.exe -pw hunter2 host")
        self.assertEqual("BLOCKED", e["classification"])
        self.assertIn("PLAINTEXT_PUTTY_PASSWORD", e["reasons"])

    def test_embedded_password_propagates_block(self):
        e = wu189.build_envelope(GOOD + "\nPassword=secret123")
        self.assertEqual("BLOCKED", e["classification"])
        self.assertIn("EMBEDDED_PASSWORD", e["reasons"])

    def test_hostkey_bypass_propagates_block(self):
        e = wu189.build_envelope(GOOD + "\nDisable host key verification")
        self.assertEqual("BLOCKED", e["classification"])
        self.assertIn("HOSTKEY_BYPASS", e["reasons"])

    def test_auto_1080_propagates_block(self):
        e = wu189.build_envelope(GOOD + "\nrestart tunnel on 1080 automatically")
        self.assertEqual("BLOCKED", e["classification"])
        self.assertIn("AUTO_1080_LIFECYCLE", e["reasons"])

    def test_v631_mutation_propagates_block(self):
        e = wu189.build_envelope(GOOD + "\nreplace V6.3.1 during setup")
        self.assertEqual("BLOCKED", e["classification"])
        self.assertIn("V631_MUTATION", e["reasons"])

    def test_network_execution_propagates_block(self):
        e = wu189.build_envelope(GOOD + "\ncurl https://example.invalid/tool.exe")
        self.assertEqual("BLOCKED", e["classification"])
        self.assertIn("INSTALLER_NETWORK_EXEC", e["reasons"])

    def test_compiler_execution_propagates_block(self):
        e = wu189.build_envelope(GOOD + "\nrun ISCC.exe during setup")
        self.assertEqual("BLOCKED", e["classification"])
        self.assertIn("COMPILER_EXEC", e["reasons"])

    def test_reasons_are_sorted_deterministically(self):
        e = wu189.build_envelope(GOOD + "\nPassword=secret123\nDisable host key verification")
        self.assertEqual(sorted(e["reasons"]), e["reasons"])


if __name__ == "__main__":
    unittest.main()
