import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / ".pncc-dev" / "scripts" / "evaluate_candidate_build_input.py"
SPEC = importlib.util.spec_from_file_location("candidate_build_input_stable", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CandidateBuildInputStableVersionTests(unittest.TestCase):
    def test_stable_semver_is_admitted(self):
        self.assertIsNotNone(MODULE.VERSION_RX.fullmatch("7.0.0"))

    def test_existing_rc_semver_remains_admitted(self):
        self.assertIsNotNone(MODULE.VERSION_RX.fullmatch("7.0.0-rc14.39"))

    def test_malformed_versions_remain_rejected(self):
        for value in ("7.0", "v7.0.0", "7.0.0-rc", "7.0.0-beta1", "7.0.0.1"):
            with self.subTest(value=value):
                self.assertIsNone(MODULE.VERSION_RX.fullmatch(value))


if __name__ == "__main__":
    unittest.main()
