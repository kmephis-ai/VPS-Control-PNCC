import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / ".pncc-dev" / "scripts" / "evaluate_candidate_build_input.py"
SPEC = importlib.util.spec_from_file_location("candidate_build_input", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

VERSION = "7.0.0-rc14.39"
SOURCE_ROOT = "src/windows-v7"
RECIPE_PATH = "build/windows-v7-candidate-recipe.json"
PROVENANCE_PATH = ".pncc-dev/provenance/canonical-source-post-rc14.38.json"
MANIFEST_PATH = f"{SOURCE_ROOT}/VPS-Control-v7-SHA256.txt"

POLICY = {
    "schema_version": 2,
    "contract_id": "PNCC_CANDIDATE_BUILD_INPUT_READINESS_V2",
    "declaration_path": ".pncc-dev/candidate-source.json",
    "allowed_source_root_prefixes": ["src/"],
    "allowed_build_recipe_prefixes": ["build/"],
    "allowed_provenance_prefixes": [".pncc-dev/provenance/"],
    "forbidden_prefixes": ["legacy/", ".pncc-dev/examples/", "docs/", ".github/"],
    "product_source_extensions": [".ps1", ".psm1", ".psd1", ".cmd", ".vbs"],
    "runtime_authority": False,
    "hosted_ci_is_runtime_truth": False,
}

DECLARATION = {
    "schema_version": 2,
    "source_identity_semantic": "EXACT_SOURCE_COMMIT",
    "candidate_version": VERSION,
    "source_roots": [SOURCE_ROOT],
    "build_recipe": RECIPE_PATH,
    "provenance_path": PROVENANCE_PATH,
    "runtime_authority": False,
    "promotion_authority": False,
}

RECIPE = {
    "schema_version": 1,
    "recipe_id": "PNCC_WINDOWS_V7_DETERMINISTIC_ZIP_V1",
    "candidate_version": VERSION,
    "source_root": SOURCE_ROOT,
    "source_bytes_semantic": "GIT_BLOB_BYTES",
    "input_selection": "ALL_TRACKED_FILES_RECURSIVE",
    "archive_format": "ZIP",
    "compression": "STORE",
    "path_order": "ORDINAL_UTF8",
    "archive_root": "PACKAGE_ROOT",
    "fixed_timestamp_utc": "1980-01-01T00:00:00Z",
    "zip_create_system": "MSDOS",
    "zip_external_attr": "DOS_ARCHIVE",
    "manifest_path": MANIFEST_PATH,
    "output_filename": f"VPS-Control-v{VERSION}.zip",
    "runtime_authority": False,
    "promotion_authority": False,
}


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_source(root: Path, *, version: str = VERSION, previous_literal: bool = False) -> None:
    src = root / SOURCE_ROOT
    (src / "modules").mkdir(parents=True, exist_ok=True)
    (src / "VPS-Control-v7.ps1").write_text(f"# VPS Control Center v{version}\n$UiVersion = '{version}'\n", encoding="utf-8")
    (src / "VPS-Control-v7-launch.ps1").write_text(f"$LauncherVersion = '{version}'\n", encoding="utf-8")
    (src / "VPS-Control-v7-README.txt").write_text(f"VPS CONTROL CENTER v{version} — TEST\nHistorical RC14.38 may be described here.\n", encoding="utf-8")
    (src / "VPS-Control-v7-ARCHITECTURE.md").write_text(f"# VPS Control Center v{version} — Test\nHistorical RC14.38 section.\n", encoding="utf-8")
    (src / "VPS-Control-v7-CAPABILITY-TRUTH.md").write_text(f"# VPS Control Center v{version} — Capability Truth\nHistorical RC14.38 section.\n", encoding="utf-8")
    write_json(src / "VPS-Control-v7-TUNNEL-CONTRACT.json", {"ContractVersion": version, "Tunnels": [], "CredentialTransport": {"PuttyArgument": "-pwfile", "PlaintextPwArgumentAllowed": False}})
    body = "Write-Output 'module'\n"
    if previous_literal:
        body += "$x='7.0.0-rc14.38'\n"
    (src / "modules" / "V7-Core.ps1").write_text(body, encoding="utf-8")


def build_manifest(root: Path, *, version: str = VERSION) -> None:
    src = root / SOURCE_ROOT
    rows = []
    for path in sorted(p for p in src.rglob("*") if p.is_file() and p.name != "VPS-Control-v7-SHA256.txt"):
        rel = path.relative_to(src).as_posix().replace("/", "\\")
        rows.append(f"{sha(path)}  {rel}")
    (src / "VPS-Control-v7-SHA256.txt").write_text(f"# VPS Control Center v{version} deterministic candidate source manifest\n" + "\n".join(rows) + "\n", encoding="utf-8")


def build_provenance(root: Path, *, version: str = VERSION) -> None:
    src = root / SOURCE_ROOT
    inv = []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        inv.append({"bytes": len(path.read_bytes()), "path": path.relative_to(src).as_posix(), "sha256": sha(path)})
    write_json(root / PROVENANCE_PATH, {
        "schema_version": 3,
        "provenance_id": "PNCC_CANONICAL_SOURCE_RC14_39_BUILD_INPUT_ACTIVATION_V1",
        "hash_semantics": "CANONICAL_GIT_BLOB_BYTES",
        "source_root": SOURCE_ROOT,
        "source_identity_semantic": "UNBUILT_RC14_39_CANDIDATE_SOURCE_BASELINE",
        "baseline": {"previous_runtime_version": "7.0.0-rc14.38", "embedded_version": version, "activated_candidate_version": version, "requires_version_bump_before_build": False},
        "inventory": inv,
        "safety": {"build_input_ready": True, "artifact_exists": False, "runtime_authority": False, "promotion_authority": False, "stable_done": False},
    })


def initialize_repository(root: Path, *, declaration=None, recipe=None, version: str = VERSION, previous_literal: bool = False, make_recipe: bool = True, make_provenance: bool = True) -> None:
    run_git(root, "init")
    run_git(root, "config", "user.name", "PNCC Test")
    run_git(root, "config", "user.email", "pncc-test@example.invalid")
    write_json(root / ".pncc-dev" / "contracts" / "candidate-build-input-policy.json", POLICY)
    if declaration is not None:
        write_json(root / ".pncc-dev" / "candidate-source.json", declaration)
    make_source(root, version=version, previous_literal=previous_literal)
    build_manifest(root, version=version)
    if make_recipe:
        write_json(root / RECIPE_PATH, recipe if recipe is not None else RECIPE)
    if make_provenance:
        build_provenance(root, version=version)
    run_git(root, "add", "-A")
    completed = run_git(root, "commit", "-m", "test fixture")
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)


class CandidateBuildInputReadinessTests(unittest.TestCase):
    def evaluate_temp(self, root: Path):
        return MODULE.evaluate(root, root / ".pncc-dev" / "contracts" / "candidate-build-input-policy.json")

    def test_current_repository_is_ready(self):
        result = MODULE.evaluate(REPO_ROOT, REPO_ROOT / ".pncc-dev" / "contracts" / "candidate-build-input-policy.json")
        self.assertEqual(MODULE.READY, result["state"])
        self.assertTrue(result["can_build"])
        self.assertFalse(result["runtime_authority"])
        self.assertFalse(result["promotion_authority"])

    def test_require_ready_cli_passes_for_current_repository(self):
        completed = subprocess.run([sys.executable, str(MODULE_PATH), "--repository-root", str(REPO_ROOT), "--require-ready"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(0, completed.returncode)
        self.assertIn("CANDIDATE_BUILD_INPUT_STATE=READY", completed.stdout)
        self.assertIn("CAN_BUILD=true", completed.stdout)

    def test_valid_contract_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION)
            self.assertEqual(MODULE.READY, self.evaluate_temp(root)["state"])

    def test_missing_declaration_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=None)
            self.assertEqual(MODULE.BLOCKED_MISSING_SOURCE_DECLARATION, self.evaluate_temp(root)["state"])

    def test_legacy_source_root_is_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); d = dict(DECLARATION); d["source_roots"] = ["legacy/v7"]; initialize_repository(root, declaration=d)
            self.assertEqual(MODULE.BLOCKED_FORBIDDEN_SOURCE_PREFIX, self.evaluate_temp(root)["state"])

    def test_recipe_path_traversal_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); d = dict(DECLARATION); d["build_recipe"] = "build/../legacy.json"; initialize_repository(root, declaration=d)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, self.evaluate_temp(root)["state"])

    def test_provenance_outside_governed_prefix_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); d = dict(DECLARATION); d["provenance_path"] = "build/provenance.json"; initialize_repository(root, declaration=d)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, self.evaluate_temp(root)["state"])

    def test_declaration_cannot_grant_runtime_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); d = dict(DECLARATION); d["runtime_authority"] = True; initialize_repository(root, declaration=d)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, self.evaluate_temp(root)["state"])

    def test_missing_recipe_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION, make_recipe=False)
            self.assertEqual(MODULE.BLOCKED_MISSING_BUILD_RECIPE, self.evaluate_temp(root)["state"])

    def test_recipe_unknown_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); r = dict(RECIPE); r["unexpected"] = True; initialize_repository(root, declaration=DECLARATION, recipe=r)
            self.assertEqual(MODULE.BLOCKED_INVALID_RECIPE, self.evaluate_temp(root)["state"])

    def test_recipe_compression_must_be_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); r = dict(RECIPE); r["compression"] = "DEFLATE"; initialize_repository(root, declaration=DECLARATION, recipe=r)
            self.assertEqual(MODULE.BLOCKED_INVALID_RECIPE, self.evaluate_temp(root)["state"])

    def test_recipe_candidate_version_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); r = dict(RECIPE); r["candidate_version"] = "7.0.0-rc14.40"; initialize_repository(root, declaration=DECLARATION, recipe=r)
            self.assertEqual(MODULE.BLOCKED_INVALID_RECIPE, self.evaluate_temp(root)["state"])

    def test_recipe_cannot_grant_promotion_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); r = dict(RECIPE); r["promotion_authority"] = True; initialize_repository(root, declaration=DECLARATION, recipe=r)
            self.assertEqual(MODULE.BLOCKED_INVALID_RECIPE, self.evaluate_temp(root)["state"])

    def test_source_version_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION, version="7.0.0-rc14.40")
            self.assertEqual(MODULE.BLOCKED_VERSION_MISMATCH, self.evaluate_temp(root)["state"])

    def test_previous_version_literal_in_executable_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION, previous_literal=True)
            self.assertEqual(MODULE.BLOCKED_VERSION_MISMATCH, self.evaluate_temp(root)["state"])

    def test_missing_provenance_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION, make_provenance=False)
            self.assertEqual(MODULE.BLOCKED_PROVENANCE_MISMATCH, self.evaluate_temp(root)["state"])

    def test_provenance_embedded_version_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION); p = json.loads((root / PROVENANCE_PATH).read_text()); p["baseline"]["embedded_version"] = "7.0.0-rc14.40"; write_json(root / PROVENANCE_PATH, p); run_git(root, "add", PROVENANCE_PATH); run_git(root, "commit", "-m", "bad provenance version")
            self.assertEqual(MODULE.BLOCKED_PROVENANCE_MISMATCH, self.evaluate_temp(root)["state"])

    def test_provenance_cannot_claim_artifact_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION); p = json.loads((root / PROVENANCE_PATH).read_text()); p["safety"]["artifact_exists"] = True; write_json(root / PROVENANCE_PATH, p); run_git(root, "add", PROVENANCE_PATH); run_git(root, "commit", "-m", "bad provenance authority")
            self.assertEqual(MODULE.BLOCKED_PROVENANCE_MISMATCH, self.evaluate_temp(root)["state"])

    def test_manifest_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION); m = root / MANIFEST_PATH; m.write_text(m.read_text().replace("a", "b", 1)); run_git(root, "add", MANIFEST_PATH); run_git(root, "commit", "-m", "tamper manifest")
            self.assertIn(self.evaluate_temp(root)["state"], (MODULE.BLOCKED_PROVENANCE_MISMATCH, MODULE.BLOCKED_MANIFEST_MISMATCH))

    def test_source_tamper_fails_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION); p = root / SOURCE_ROOT / "modules" / "V7-Core.ps1"; p.write_text("Write-Output 'changed'\n"); build_manifest(root); run_git(root, "add", SOURCE_ROOT); run_git(root, "commit", "-m", "source changed without provenance")
            self.assertEqual(MODULE.BLOCKED_PROVENANCE_MISMATCH, self.evaluate_temp(root)["state"])

    def test_untracked_source_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION); (root / SOURCE_ROOT / "local.ps1").write_text("Write-Output 'untracked'\n")
            self.assertEqual(MODULE.BLOCKED_UNTRACKED_SOURCE, self.evaluate_temp(root)["state"])

    def test_dirty_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION); (root / SOURCE_ROOT / "modules" / "V7-Core.ps1").write_text("Write-Output 'dirty'\n")
            self.assertEqual(MODULE.BLOCKED_DIRTY_BUILD_INPUT, self.evaluate_temp(root)["state"])

    def test_policy_cannot_grant_runtime_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); initialize_repository(root, declaration=DECLARATION); p = dict(POLICY); p["runtime_authority"] = True; write_json(root / ".pncc-dev" / "contracts" / "candidate-build-input-policy.json", p)
            result = self.evaluate_temp(root); self.assertEqual(MODULE.BLOCKED_INVALID_POLICY, result["state"]); self.assertFalse(result["runtime_authority"])


if __name__ == "__main__":
    unittest.main()
