import importlib.util
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

POLICY = {
    "schema_version": 1,
    "contract_id": "PNCC_CANDIDATE_BUILD_INPUT_READINESS_V1",
    "declaration_path": ".pncc-dev/candidate-source.json",
    "allowed_source_root_prefixes": ["src/"],
    "allowed_build_recipe_prefixes": ["build/"],
    "forbidden_prefixes": ["legacy/", ".pncc-dev/examples/", "docs/", ".github/"],
    "product_source_extensions": [".ps1", ".psm1", ".psd1", ".cmd", ".vbs"],
    "runtime_authority": False,
    "hosted_ci_is_runtime_truth": False,
}

DECLARATION = {
    "schema_version": 1,
    "source_identity_semantic": "EXACT_SOURCE_COMMIT",
    "source_roots": ["src/pncc"],
    "build_recipe": "build/build_candidate.py",
}


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def initialize_repository(root: Path, declaration=None, *, source=True, recipe=True, source_content="Write-Output 'PNCC'\n") -> None:
    run_git(root, "init")
    run_git(root, "config", "user.name", "PNCC Test")
    run_git(root, "config", "user.email", "pncc-test@example.invalid")
    write_json(root / ".pncc-dev" / "contracts" / "candidate-build-input-policy.json", POLICY)
    if declaration is not None:
        write_json(root / ".pncc-dev" / "candidate-source.json", declaration)
    if source:
        source_path = root / "src" / "pncc" / "main.ps1"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(source_content, encoding="utf-8")
    if recipe:
        recipe_path = root / "build" / "build_candidate.py"
        recipe_path.parent.mkdir(parents=True, exist_ok=True)
        recipe_path.write_text("print('synthetic build recipe')\n", encoding="utf-8")
    run_git(root, "add", "-A")
    completed = run_git(root, "commit", "-m", "test fixture")
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)


class CandidateBuildInputReadinessTests(unittest.TestCase):
    def evaluate_temp(self, root: Path):
        return MODULE.evaluate(root, root / ".pncc-dev" / "contracts" / "candidate-build-input-policy.json")

    def test_current_repository_is_explicitly_blocked_without_source_declaration(self):
        result = MODULE.evaluate(REPO_ROOT, REPO_ROOT / ".pncc-dev" / "contracts" / "candidate-build-input-policy.json")
        self.assertEqual(MODULE.BLOCKED_MISSING_SOURCE_DECLARATION, result["state"])
        self.assertFalse(result["can_build"])
        self.assertFalse(result["runtime_authority"])
        self.assertFalse(result["promotion_authority"])

    def test_require_ready_cli_fails_closed_for_current_repository(self):
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--repository-root", str(REPO_ROOT), "--require-ready"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(3, completed.returncode)
        self.assertIn("CANDIDATE_BUILD_INPUT_STATE=BLOCKED_MISSING_SOURCE_DECLARATION", completed.stdout)
        self.assertIn("CANDIDATE_BUILD_BLOCKED", completed.stderr)

    def test_valid_tracked_canonical_source_and_recipe_are_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repository(root, DECLARATION)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.READY, result["state"])
            self.assertTrue(result["can_build"])
            self.assertRegex(result["subject_sha"], r"^[0-9a-f]{40}$")

    def test_legacy_source_root_is_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaration = dict(DECLARATION)
            declaration["source_roots"] = ["legacy/v7-rc14.38-sanitized"]
            initialize_repository(root, declaration, source=False)
            legacy = root / "legacy" / "v7-rc14.38-sanitized" / "VPS-Control-v7.ps1"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("Write-Output 'legacy'\n", encoding="utf-8")
            run_git(root, "add", "-A")
            run_git(root, "commit", "-m", "legacy fixture")
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_FORBIDDEN_SOURCE_PREFIX, result["state"])

    def test_build_recipe_under_legacy_is_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaration = dict(DECLARATION)
            declaration["build_recipe"] = "legacy/build.py"
            initialize_repository(root, declaration, recipe=False)
            path = root / "legacy" / "build.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("print('legacy')\n", encoding="utf-8")
            run_git(root, "add", "-A")
            run_git(root, "commit", "-m", "legacy recipe")
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_FORBIDDEN_SOURCE_PREFIX, result["state"])

    def test_missing_source_root_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repository(root, DECLARATION, source=False)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_MISSING_SOURCE_ROOT, result["state"])

    def test_source_root_without_product_files_is_empty_for_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repository(root, DECLARATION, source=False)
            keep = root / "src" / "pncc" / ".gitkeep"
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_text("", encoding="utf-8")
            run_git(root, "add", "-A")
            run_git(root, "commit", "-m", "empty source placeholder")
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_EMPTY_SOURCE_ROOT, result["state"])

    def test_untracked_source_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repository(root, DECLARATION)
            (root / "src" / "pncc" / "local.ps1").write_text("Write-Output 'untracked'\n", encoding="utf-8")
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_UNTRACKED_SOURCE, result["state"])

    def test_missing_build_recipe_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repository(root, DECLARATION, recipe=False)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_MISSING_BUILD_RECIPE, result["state"])

    def test_untracked_build_recipe_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repository(root, DECLARATION, recipe=False)
            recipe = root / "build" / "build_candidate.py"
            recipe.parent.mkdir(parents=True, exist_ok=True)
            recipe.write_text("print('untracked')\n", encoding="utf-8")
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_UNTRACKED_BUILD_RECIPE, result["state"])

    def test_dirty_tracked_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repository(root, DECLARATION)
            (root / "src" / "pncc" / "main.ps1").write_text("Write-Output 'modified'\n", encoding="utf-8")
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_DIRTY_BUILD_INPUT, result["state"])

    def test_source_path_traversal_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaration = dict(DECLARATION)
            declaration["source_roots"] = ["src/../legacy"]
            initialize_repository(root, declaration)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, result["state"])

    def test_build_recipe_path_traversal_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaration = dict(DECLARATION)
            declaration["build_recipe"] = "build/../legacy.py"
            initialize_repository(root, declaration)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, result["state"])

    def test_unknown_declaration_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaration = dict(DECLARATION)
            declaration["unexpected"] = True
            initialize_repository(root, declaration)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, result["state"])

    def test_duplicate_source_roots_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaration = dict(DECLARATION)
            declaration["source_roots"] = ["src/pncc", "src/pncc"]
            initialize_repository(root, declaration)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, result["state"])

    def test_non_exact_source_semantic_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaration = dict(DECLARATION)
            declaration["source_identity_semantic"] = "SANITIZED_PUBLIC_FIXTURE"
            initialize_repository(root, declaration)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, result["state"])

    def test_source_root_outside_governed_src_prefix_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            declaration = dict(DECLARATION)
            declaration["source_roots"] = ["product"]
            initialize_repository(root, declaration)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_INVALID_DECLARATION, result["state"])

    def test_policy_cannot_grant_runtime_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_repository(root, DECLARATION)
            policy = dict(POLICY)
            policy["runtime_authority"] = True
            write_json(root / ".pncc-dev" / "contracts" / "candidate-build-input-policy.json", policy)
            result = self.evaluate_temp(root)
            self.assertEqual(MODULE.BLOCKED_INVALID_POLICY, result["state"])
            self.assertFalse(result["runtime_authority"])


if __name__ == "__main__":
    unittest.main()
