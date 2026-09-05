#!/usr/bin/env python3
import hashlib, json, pathlib, subprocess, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "7ec91428e04b54bfa74d22bee0a02b045e211fa9"
DIST = ROOT / "src/rollback-base/VPS-Control-v6.3.1.ps1"
ISS = ROOT / "installer/windows/VPS-Control-PNCC.iss"
GA = ROOT / ".gitattributes"
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-wu209-v631-distribution-closure.json"
EXPECTED_SHA = "385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e"
EXPECTED_BYTES = 162507
EXPECTED_BLOB = "fbcf80dac2d619c421b8a40b5612cd13d5da4a73"
V631_LINE = 'Source: "..\\..\\src\\rollback-base\\VPS-Control-v6.3.1.ps1"; DestDir: "{app}"; DestName: "VPS-Control-v6.3.1.ps1"; Flags: ignoreversion notimestamp'

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

class WU209Tests(unittest.TestCase):
    def test_exact_immutable_bytes_and_blob(self):
        b = DIST.read_bytes()
        self.assertEqual(len(b), EXPECTED_BYTES)
        self.assertEqual(hashlib.sha256(b).hexdigest(), EXPECTED_SHA)
        self.assertEqual(git("hash-object", "src/rollback-base/VPS-Control-v6.3.1.ps1"), EXPECTED_BLOB)

    def test_no_git_text_normalization_for_immutable_path(self):
        text = GA.read_text(encoding="utf-8")
        self.assertIn("src/rollback-base/VPS-Control-v6.3.1.ps1 -text", text)
        attr = git("check-attr", "text", "--", "src/rollback-base/VPS-Control-v6.3.1.ps1")
        self.assertTrue(attr.endswith("text: unset"), attr)

    def test_installer_change_is_exactly_one_additive_files_entry(self):
        base = subprocess.check_output(
            ["git","show",f"{BASE}:installer/windows/VPS-Control-PNCC.iss"],
            cwd=ROOT, text=True
        )
        cur = ISS.read_text(encoding="utf-8")
        self.assertEqual(cur.count(V631_LINE), 1)
        self.assertEqual(cur.replace(V631_LINE + "\n", ""), base)

    def test_launcher_fail_closed_contract_is_untouched(self):
        current_blob = git("rev-parse", "HEAD:src/windows-v7/VPS-Control-v7-launch.ps1")
        base_blob = git("rev-parse", f"{BASE}:src/windows-v7/VPS-Control-v7-launch.ps1")
        self.assertEqual(current_blob, base_blob)

    def test_contract_bounds(self):
        c = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(c["work_unit_id"], "PIPE-WU-209")
        self.assertEqual(c["immutable_v6_3_1"]["sha256"], EXPECTED_SHA)
        self.assertEqual(c["immutable_v6_3_1"]["git_blob_sha1"], EXPECTED_BLOB)
        for k in [
            "compiler_execution","artifact_build_or_upload","release","tag",
            "stable_transition","self_hosted_runner","port_1080_lifecycle",
            "port_1081_lifecycle","v6_3_1_byte_or_semantic_mutation",
            "launcher_code_17_weakening","ruleset_or_security_weakening","force_or_bypass"
        ]:
            self.assertFalse(c["authority"][k], k)

if __name__ == "__main__":
    unittest.main(verbosity=2)