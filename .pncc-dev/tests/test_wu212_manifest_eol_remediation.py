import hashlib
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "c725ab82465a0a094fde00359c4a78fd18cd3f3c"
README = ROOT / "src/windows-v7/VPS-Control-v7-README.txt"
MANIFEST = ROOT / "src/windows-v7/VPS-Control-v7-SHA256.txt"
GITATTR = ROOT / ".gitattributes"
V631 = ROOT / "src/rollback-base/VPS-Control-v6.3.1.ps1"
EXPECTED_README = "530241a9ab4853f95a6a528cdac94bda615c4b505cb688e8b31d51dadcf7908a"
EXPECTED_V631 = "385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e"
EXPECTED_V631_BLOB = "fbcf80dac2d619c421b8a40b5612cd13d5da4a73"
RULE = "src/windows-v7/VPS-Control-v7-README.txt text eol=lf"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WU212Tests(unittest.TestCase):
    def test_exact_gitattributes_delta_only(self):
        base = subprocess.check_output(["git", "show", f"{BASE}:.gitattributes"], cwd=ROOT).decode("utf-8-sig")
        current = GITATTR.read_text(encoding="utf-8-sig")
        self.assertEqual(current, base + RULE + "\n")

    def test_readme_source_semantics_and_blob_unchanged(self):
        self.assertEqual(git("diff", "--name-only", BASE, "--", "src/windows-v7/VPS-Control-v7-README.txt"), "")
        self.assertEqual(git("diff", "--name-only", BASE, "--", "src/windows-v7/VPS-Control-v7-launch.ps1"), "")
        self.assertEqual(sha256(README), EXPECTED_README)

    def test_checkout_attribute_is_explicit_lf(self):
        attrs = git("check-attr", "text", "eol", "--", "src/windows-v7/VPS-Control-v7-README.txt")
        self.assertIn(": text: set", attrs)
        self.assertIn(": eol: lf", attrs)

    def test_all_manifest_covered_worktree_bytes_match_manifest(self):
        for raw in MANIFEST.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            expected, rel = line.split(None, 1)
            path = ROOT / "src/windows-v7" / pathlib.Path(rel.replace("\\", "/"))
            self.assertTrue(path.is_file(), rel)
            self.assertEqual(sha256(path), expected.lower(), rel)

    def test_v631_immutable_identity_untouched(self):
        self.assertEqual(len(V631.read_bytes()), 162507)
        self.assertEqual(sha256(V631), EXPECTED_V631)
        self.assertEqual(git("hash-object", "src/rollback-base/VPS-Control-v6.3.1.ps1"), EXPECTED_V631_BLOB)

    def test_contract_forbidden_authority(self):
        import json
        c = json.loads((ROOT / ".pncc-dev/contracts/wave6-wu212-manifest-eol-remediation.json").read_text(encoding="utf-8"))
        self.assertEqual(c["work_unit_id"], "PIPE-WU-212")
        self.assertEqual(c["authorized_base_main_sha"], BASE)
        for key in (
            "product_runtime_source_mutation",
            "v6_3_1_byte_or_semantic_mutation",
            "port_1080_lifecycle",
            "port_1080_or_1081_semantics_change",
            "launcher_code_14_or_17_weakening",
            "host_key_dpapi_or_pwfile_weakening",
            "self_hosted_runner",
            "ruleset_or_security_weakening",
            "force_or_bypass",
            "release",
            "tag",
            "stable_transition",
        ):
            self.assertFalse(c["authority"][key], key)


if __name__ == "__main__":
    unittest.main()
