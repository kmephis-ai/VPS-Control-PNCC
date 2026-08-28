#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STRICT_PATH = REPO_ROOT / ".pncc-dev" / "scripts" / "validate_governed_candidate_manifest.py"
EXAMPLE_PATH = REPO_ROOT / ".pncc-dev" / "examples" / "candidate-manifest.synthetic.json"

SPEC = importlib.util.spec_from_file_location("pncc_governed_candidate_manifest", STRICT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load strict validator")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

SHA = "c7f9dd033f108a5cf73cb869ee184159c89803f8"
REQUIRED = (
    "repo-integrity", "powershell-static", "truth-contract", "adwf-binding", "pipeline-state",
    "quality-fast", "quality-deep", "candidate-artifact-truth",
    "candidate-build-input-readiness", "canonical-source-admission",
)


def governed_fixture(version="7.0.0"):
    value = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    stable = version == "7.0.0"
    value["candidate_id"] = ("PNCC-V7.0.0-" if stable else "PNCC-RC14.39-") + "C7F9DD033F10"
    value["artifact_role"] = "RUNTIME_CANDIDATE"
    value["source"] = {
        "repository": "kmephis-ai/VPS-Control-PNCC", "commit_sha": SHA,
        "ref": "refs/heads/main", "identity_semantic": "EXACT_SOURCE_COMMIT", "path": "src/windows-v7",
    }
    value["artifact"] = {"filename": f"VPS-Control-v{version}.zip", "sha256": "a" * 64, "size_bytes": 12345}
    value["build"] = {
        "workflow": "candidate-builder", "run_id": 123, "run_attempt": 1,
        "job_name": "candidate-builder-main", "created_at_utc": "2026-08-27T18:00:00Z", "builder": "GITHUB_HOSTED",
    }
    value["tool_versions"]["candidate_version"] = version
    value["engineering_checks"] = [{"name": name, "conclusion": "SUCCESS", "subject_sha": SHA} for name in REQUIRED]
    value["provenance"] = {
        "artifact_origin": "BUILD_OUTPUT", "sanitation_state": "EXACT_BUILD_OUTPUT",
        "attestation_state": "HOSTED_PROVENANCE_RECORDED", "runtime_authority": False,
    }
    value["runtime"] = {"qualification_state": "NOT_VERIFIED", "evidence_ref": None, "promotion_eligible": False}
    return value


class GovernedCandidateManifestTests(unittest.TestCase):
    def assert_error(self, value, needle):
        errors = VALIDATOR.validate_governed_manifest(value)
        self.assertTrue(any(needle in error for error in errors), errors)

    def test_valid_stable_candidate_passes(self):
        self.assertEqual([], VALIDATOR.validate_governed_manifest(governed_fixture("7.0.0")))

    def test_existing_rc_candidate_remains_accepted(self):
        self.assertEqual([], VALIDATOR.validate_governed_manifest(governed_fixture("7.0.0-rc14.39")))

    def test_requires_runtime_candidate_role(self):
        value = governed_fixture(); value["artifact_role"] = "SYNTHETIC_TEST_FIXTURE"
        self.assert_error(value, "ARTIFACT_ROLE_RUNTIME_CANDIDATE_REQUIRED")

    def test_requires_protected_main_ref(self):
        value = governed_fixture(); value["source"]["ref"] = "refs/heads/feature"
        self.assert_error(value, "PROTECTED_MAIN_REF_REQUIRED")

    def test_requires_canonical_source_path(self):
        value = governed_fixture(); value["source"]["path"] = "legacy/v7-rc14.38-sanitized"
        self.assert_error(value, "CANONICAL_WINDOWS_V7_SOURCE_REQUIRED")

    def test_requires_version_bound_filename(self):
        value = governed_fixture(); value["artifact"]["filename"] = "other.zip"
        self.assert_error(value, "ARTIFACT_FILENAME_VERSION_IDENTITY_REQUIRED")

    def test_requires_version_bound_candidate_id(self):
        value = governed_fixture(); value["candidate_id"] = "PNCC-RC14.39-C7F9DD033F10"
        self.assert_error(value, "CANDIDATE_ID_VERSION_IDENTITY_REQUIRED")

    def test_unsupported_version_fails_closed(self):
        value = governed_fixture(); value["tool_versions"]["candidate_version"] = "7.0.1"
        self.assert_error(value, "CANDIDATE_VERSION_UNSUPPORTED")

    def test_requires_candidate_builder_workflow(self):
        value = governed_fixture(); value["build"]["workflow"] = "other"
        self.assert_error(value, "CANDIDATE_BUILDER_WORKFLOW_REQUIRED")

    def test_requires_candidate_builder_main_job(self):
        value = governed_fixture(); value["build"]["job_name"] = "candidate-builder-reproducibility"
        self.assert_error(value, "CANDIDATE_BUILDER_MAIN_JOB_REQUIRED")

    def test_requires_all_same_sha_engineering_checks(self):
        value = governed_fixture()
        value["engineering_checks"] = [check for check in value["engineering_checks"] if check["name"] != "canonical-source-admission"]
        self.assert_error(value, "MISSING_ENGINEERING_CHECKS:canonical-source-admission")

    def test_requires_hosted_provenance(self):
        value = governed_fixture(); value["provenance"]["attestation_state"] = "NOT_ATTESTED"
        self.assert_error(value, "HOSTED_PROVENANCE_REQUIRED")

    def test_runtime_and_promotion_claims_fail_closed(self):
        value = governed_fixture(); value["runtime"]["qualification_state"] = "RUNTIME_VERIFIED"; value["runtime"]["promotion_eligible"] = True
        errors = VALIDATOR.validate_governed_manifest(value)
        self.assertTrue(any("RUNTIME_MUST_BE_NOT_VERIFIED" in error for error in errors))
        self.assertTrue(any("PROMOTION_ELIGIBLE_FORBIDDEN" in error for error in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
