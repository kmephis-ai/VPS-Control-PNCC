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

LF_RULE_PATHS = (
    "src/windows-v7/VPS-Control-v7-README.txt",
    "src/windows-v7/VPS-Control-v7-browser-strict.ps1",
    "src/windows-v7/VPS-Control-v7-demo.cmd",
    "src/windows-v7/VPS-Control-v7-engine-upgrade.ps1",
    "src/windows-v7/VPS-Control-v7-evidence-worker.ps1",
    "src/windows-v7/VPS-Control-v7-keenetic.ps1",
    "src/windows-v7/VPS-Control-v7-launch.ps1",
    "src/windows-v7/VPS-Control-v7-tunnel-manager.ps1",
    "src/windows-v7/VPS-Control-v7-vm-gateway.ps1",
    "src/windows-v7/VPS-Control-v7-vps-manager.ps1",
    "src/windows-v7/VPS-Control-v7.cmd",
    "src/windows-v7/VPS-Control-v7.ps1",
    "src/windows-v7/VPS-Control-v7.vbs",
    "src/windows-v7/modules/V7-Consistency.ps1",
    "src/windows-v7/modules/V7-Core.ps1",
    "src/windows-v7/modules/V7-DeepTelemetry.ps1",
    "src/windows-v7/modules/V7-Demo.ps1",
    "src/windows-v7/modules/V7-Events.ps1",
    "src/windows-v7/modules/V7-KeeneticModel.ps1",
    "src/windows-v7/modules/V7-Maintenance.ps1",
    "src/windows-v7/modules/V7-Observability.ps1",
    "src/windows-v7/modules/V7-Readiness.ps1",
    "src/windows-v7/modules/V7-Runtime.ps1",
    "src/windows-v7/modules/V7-StatusCenter.ps1",
    "src/windows-v7/modules/V7-Storage.ps1",
    "src/windows-v7/modules/V7-Tunnels.ps1",
    "src/windows-v7/modules/V7-UiCommon.ps1",
)

RULES = tuple(f"{path} text eol=lf" for path in LF_RULE_PATHS)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_entries():
    rows = []
    for raw in MANIFEST.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        expected, rel = line.split(None, 1)
        rows.append((expected.lower(), rel))
    return rows


class WU212Tests(unittest.TestCase):
    def test_exact_gitattributes_delta_only(self):
        base = subprocess.check_output(["git", "show", f"{BASE}:.gitattributes"], cwd=ROOT).decode("utf-8-sig")
        current = GITATTR.read_text(encoding="utf-8-sig")
        self.assertEqual(current, base + "".join(rule + "\n" for rule in RULES))

    def test_manifest_covered_product_source_semantics_unchanged(self):
        names = [rel.replace("\\", "/") for _, rel in manifest_entries()]
        changed = git("diff", "--name-only", BASE, "--", *[f"src/windows-v7/{name}" for name in names])
        self.assertEqual(changed, "")
        self.assertEqual(sha256(README), EXPECTED_README)

    def test_all_explicit_lf_overrides_are_manifest_covered(self):
        covered = {"src/windows-v7/" + rel.replace("\\", "/") for _, rel in manifest_entries()}
        self.assertTrue(set(LF_RULE_PATHS).issubset(covered))

    def test_all_susceptible_manifest_paths_have_explicit_lf(self):
        susceptible = []
        for _, rel in manifest_entries():
            normalized = "src/windows-v7/" + rel.replace("\\", "/")
            if pathlib.PurePosixPath(normalized).suffix.lower() in {".txt", ".ps1", ".cmd", ".vbs"}:
                susceptible.append(normalized)
        self.assertEqual(set(susceptible), set(LF_RULE_PATHS))
        for path in susceptible:
            attrs = git("check-attr", "text", "eol", "--", path)
            self.assertIn(": text: set", attrs, path)
            self.assertIn(": eol: lf", attrs, path)

    def test_all_manifest_covered_worktree_bytes_match_manifest(self):
        for expected, rel in manifest_entries():
            path = ROOT / "src/windows-v7" / pathlib.Path(rel.replace("\\", "/"))
            self.assertTrue(path.is_file(), rel)
            self.assertEqual(sha256(path), expected, rel)

    def test_v631_immutable_identity_untouched(self):
        self.assertEqual(len(V631.read_bytes()), 162507)
        self.assertEqual(sha256(V631), EXPECTED_V631)
        self.assertEqual(git("hash-object", "src/rollback-base/VPS-Control-v6.3.1.ps1"), EXPECTED_V631_BLOB)

    def test_contract_forbidden_authority(self):
        import json
        c = json.loads((ROOT / ".pncc-dev/contracts/wave6-wu212-manifest-eol-remediation.json").read_text(encoding="utf-8"))
        self.assertEqual(c["work_unit_id"], "PIPE-WU-212")
        self.assertEqual(c["authorized_base_main_sha"], BASE)
        self.assertEqual(c["remediation"]["semantic_content_mutation"], False)
        self.assertEqual(c["remediation"]["canonical_manifest_mutation"], False)
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
