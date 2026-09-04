import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / ".pncc-dev" / "scripts" / "evaluate_candidate_build_input.py"
SPEC = importlib.util.spec_from_file_location("candidate_build_input_wu175", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

PREFIXES = [".pncc-dev/provenance/"]
CURRENT_PATH = ".pncc-dev/provenance/canonical-source-v7.0.2-patch.json"
PREVIOUS_PATH = ".pncc-dev/provenance/canonical-source-v7.0.1-patch.json"


def previous_blob(version="7.0.1", *, runtime_authority=False):
    return json.dumps(
        {
            "hash_semantics": "CANONICAL_GIT_BLOB_BYTES",
            "baseline": {
                "activated_candidate_version": version,
                "embedded_version": version,
            },
            "safety": {
                "runtime_authority": runtime_authority,
                "promotion_authority": False,
                "stable_done": False,
            },
        }
    ).encode("utf-8")


class CandidateBuildInputLineageWu175Tests(unittest.TestCase):
    def validate(self, provenance, baseline, blob=previous_blob()):
        with mock.patch.object(MODULE, "_git_blob", return_value=blob):
            return MODULE._validate_previous_runtime_lineage(
                Path("."),
                provenance_path=CURRENT_PATH,
                provenance=provenance,
                baseline=baseline,
                candidate_version="7.0.2",
                allowed_provenance_prefixes=PREFIXES,
            )

    def test_legacy_provenance_preserves_rc1438_invariant(self):
        error = self.validate({}, {"previous_runtime_version": "7.0.0-rc14.38"})
        self.assertIsNone(error)

    def test_legacy_provenance_rejects_other_previous_runtime(self):
        error = self.validate({}, {"previous_runtime_version": "7.0.1"})
        self.assertEqual("provenance previous_runtime_version mismatch", error)

    def test_parent_aware_v702_lineage_accepts_exact_previous_provenance(self):
        provenance = {
            "parent": {
                "previous_release_version": "7.0.1",
                "previous_provenance_path": PREVIOUS_PATH,
            }
        }
        error = self.validate(provenance, {"previous_runtime_version": "7.0.1"})
        self.assertIsNone(error)

    def test_parent_aware_lineage_rejects_baseline_parent_mismatch(self):
        provenance = {
            "parent": {
                "previous_release_version": "7.0.1",
                "previous_provenance_path": PREVIOUS_PATH,
            }
        }
        error = self.validate(provenance, {"previous_runtime_version": "7.0.0"})
        self.assertEqual("provenance previous_runtime_version mismatch", error)

    def test_parent_aware_lineage_rejects_unsafe_previous_path(self):
        provenance = {
            "parent": {
                "previous_release_version": "7.0.1",
                "previous_provenance_path": "../outside.json",
            }
        }
        error = self.validate(provenance, {"previous_runtime_version": "7.0.1"})
        self.assertEqual("provenance parent previous_provenance_path invalid", error)

    def test_parent_aware_lineage_rejects_missing_previous_provenance(self):
        provenance = {
            "parent": {
                "previous_release_version": "7.0.1",
                "previous_provenance_path": PREVIOUS_PATH,
            }
        }
        error = self.validate(provenance, {"previous_runtime_version": "7.0.1"}, blob=None)
        self.assertEqual("previous provenance is not available from exact HEAD", error)

    def test_parent_aware_lineage_rejects_previous_activation_mismatch(self):
        provenance = {
            "parent": {
                "previous_release_version": "7.0.1",
                "previous_provenance_path": PREVIOUS_PATH,
            }
        }
        error = self.validate(
            provenance,
            {"previous_runtime_version": "7.0.1"},
            blob=previous_blob("7.0.0"),
        )
        self.assertEqual("previous provenance activated_candidate_version mismatch", error)

    def test_parent_aware_lineage_rejects_previous_runtime_authority(self):
        provenance = {
            "parent": {
                "previous_release_version": "7.0.1",
                "previous_provenance_path": PREVIOUS_PATH,
            }
        }
        error = self.validate(
            provenance,
            {"previous_runtime_version": "7.0.1"},
            blob=previous_blob(runtime_authority=True),
        )
        self.assertEqual("previous provenance safety authority weakened: runtime_authority", error)


if __name__ == "__main__":
    unittest.main()
