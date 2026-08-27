#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".pncc-dev" / "scripts" / "validate_candidate_manifest.py"
EXAMPLE_PATH = REPO_ROOT / ".pncc-dev" / "examples" / "candidate-manifest.synthetic.json"
SCHEMA_PATH = REPO_ROOT / ".pncc-dev" / "schemas" / "candidate-manifest.schema.json"

spec = importlib.util.spec_from_file_location("pncc_candidate_manifest_validator", VALIDATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load candidate manifest validator")
validator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


def load_valid_manifest():
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


class CandidateManifestContractTests(unittest.TestCase):
    def assert_error_contains(self, manifest, needle):
        errors = validator.validate_manifest(manifest)
        self.assertTrue(errors, "expected validation failure")
        self.assertTrue(any(needle in error for error in errors), f"missing {needle!r} in {errors!r}")

    def test_valid_synthetic_manifest_passes_without_runtime_authority(self):
        manifest = load_valid_manifest()
        self.assertEqual([], validator.validate_manifest(manifest))
        self.assertEqual("SYNTHETIC_TEST_FIXTURE", manifest["artifact_role"])
        self.assertEqual("NOT_VERIFIED", manifest["runtime"]["qualification_state"])
        self.assertIsNone(manifest["runtime"]["evidence_ref"])
        self.assertFalse(manifest["runtime"]["promotion_eligible"])
        self.assertFalse(manifest["provenance"]["runtime_authority"])

    def test_schema_is_closed_at_root_and_runtime_boundaries(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["source"]["additionalProperties"])
        self.assertFalse(schema["properties"]["artifact"]["additionalProperties"])
        self.assertFalse(schema["properties"]["build"]["additionalProperties"])
        self.assertFalse(schema["properties"]["provenance"]["additionalProperties"])
        self.assertFalse(schema["properties"]["runtime"]["additionalProperties"])
        self.assertEqual("NOT_VERIFIED", schema["properties"]["runtime"]["properties"]["qualification_state"]["const"])
        self.assertFalse(schema["properties"]["runtime"]["properties"]["promotion_eligible"]["const"])

    def test_wrong_schema_version_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["schema_version"] = 2
        self.assert_error_contains(manifest, "SCHEMA_VERSION_INVALID")

    def test_unknown_root_field_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["unexpected"] = True
        self.assert_error_contains(manifest, "ROOT:UNKNOWN_KEYS")

    def test_unknown_nested_field_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["artifact"]["unexpected"] = "x"
        self.assert_error_contains(manifest, "ARTIFACT:UNKNOWN_KEYS")

    def test_malformed_source_sha_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["source"]["commit_sha"] = "ABC123"
        self.assert_error_contains(manifest, "SOURCE:COMMIT_SHA_INVALID")

    def test_malformed_artifact_sha256_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["artifact"]["sha256"] = "0" * 63
        self.assert_error_contains(manifest, "ARTIFACT:SHA256_INVALID")

    def test_zero_artifact_size_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["artifact"]["size_bytes"] = 0
        self.assert_error_contains(manifest, "ARTIFACT:SIZE_BYTES_POSITIVE_INTEGER_REQUIRED")

    def test_missing_required_engineering_check_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["engineering_checks"] = [
            check for check in manifest["engineering_checks"] if check["name"] != "quality-deep"
        ]
        self.assert_error_contains(manifest, "MISSING_REQUIRED:quality-deep")

    def test_duplicate_engineering_check_name_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["engineering_checks"].append(copy.deepcopy(manifest["engineering_checks"][0]))
        self.assert_error_contains(manifest, "DUPLICATE_NAME:repo-integrity")

    def test_failed_or_pending_check_fails_closed(self):
        for conclusion in ("FAILURE", "PENDING", "UNKNOWN"):
            with self.subTest(conclusion=conclusion):
                manifest = load_valid_manifest()
                manifest["engineering_checks"][0]["conclusion"] = conclusion
                self.assert_error_contains(manifest, "ENGINEERING_CHECKS:repo-integrity:NON_SUCCESS")

    def test_check_subject_sha_must_equal_source_sha(self):
        manifest = load_valid_manifest()
        manifest["engineering_checks"][0]["subject_sha"] = "1" * 40
        self.assert_error_contains(manifest, "SUBJECT_SHA_MISMATCH")

    def test_runtime_verified_claim_is_forbidden_in_hosted_manifest(self):
        manifest = load_valid_manifest()
        manifest["runtime"]["qualification_state"] = "RUNTIME_VERIFIED"
        self.assert_error_contains(manifest, "QUALIFICATION_MUST_BE_NOT_VERIFIED")

    def test_runtime_evidence_ref_is_forbidden_while_not_verified(self):
        manifest = load_valid_manifest()
        manifest["runtime"]["evidence_ref"] = "private://runtime/evidence.zip"
        self.assert_error_contains(manifest, "EVIDENCE_REF_FORBIDDEN_WHILE_NOT_VERIFIED")

    def test_promotion_eligibility_is_forbidden_in_contract_foundation(self):
        manifest = load_valid_manifest()
        manifest["runtime"]["promotion_eligible"] = True
        self.assert_error_contains(manifest, "PROMOTION_ELIGIBLE_FORBIDDEN")

    def test_synthetic_fixture_cannot_claim_hosted_runtime_candidate_builder(self):
        manifest = load_valid_manifest()
        manifest["build"]["builder"] = "GITHUB_HOSTED"
        self.assert_error_contains(manifest, "SYNTHETIC_BUILDER_REQUIRED")

    def test_synthetic_fixture_requires_synthetic_source_semantics(self):
        manifest = load_valid_manifest()
        manifest["source"]["identity_semantic"] = "EXACT_SOURCE_COMMIT"
        self.assert_error_contains(manifest, "SYNTHETIC_SOURCE_IDENTITY_REQUIRED")

    def test_runtime_candidate_cannot_claim_sanitized_fixture_identity(self):
        manifest = load_valid_manifest()
        manifest["artifact_role"] = "RUNTIME_CANDIDATE"
        manifest["source"]["identity_semantic"] = "SANITIZED_PUBLIC_FIXTURE"
        manifest["source"]["path"] = "legacy/v7-rc14.38-sanitized"
        manifest["build"]["builder"] = "GITHUB_HOSTED"
        manifest["provenance"]["artifact_origin"] = "SANITIZED_PUBLIC_FIXTURE"
        manifest["provenance"]["sanitation_state"] = "SANITIZED_PUBLIC"
        errors = validator.validate_manifest(manifest)
        self.assertIn("SEMANTICS:RUNTIME_CANDIDATE_EXACT_SOURCE_REQUIRED", errors)
        self.assertIn("SEMANTICS:SANITIZED_RC1438_RUNTIME_CANDIDATE_FORBIDDEN", errors)
        self.assertIn("SEMANTICS:RUNTIME_CANDIDATE_BUILD_OUTPUT_REQUIRED", errors)
        self.assertIn("SEMANTICS:RUNTIME_CANDIDATE_EXACT_BUILD_OUTPUT_REQUIRED", errors)

    def test_runtime_candidate_rejects_sanitized_rc1438_path_even_with_exact_source_label(self):
        manifest = load_valid_manifest()
        manifest["artifact_role"] = "RUNTIME_CANDIDATE"
        manifest["source"]["identity_semantic"] = "EXACT_SOURCE_COMMIT"
        manifest["source"]["path"] = "legacy/v7-rc14.38-sanitized/VPS-Control-v7.ps1"
        manifest["build"]["builder"] = "GITHUB_HOSTED"
        manifest["provenance"]["artifact_origin"] = "BUILD_OUTPUT"
        manifest["provenance"]["sanitation_state"] = "EXACT_BUILD_OUTPUT"
        self.assert_error_contains(manifest, "SANITIZED_RC1438_RUNTIME_CANDIDATE_FORBIDDEN")

    def test_source_path_traversal_fails_closed(self):
        manifest = load_valid_manifest()
        manifest["source"]["path"] = "../legacy/v7-rc14.38-sanitized"
        self.assert_error_contains(manifest, "SAFE_RELATIVE_PATH_REQUIRED")

    def test_artifact_filename_must_be_basename(self):
        manifest = load_valid_manifest()
        manifest["artifact"]["filename"] = "out/PNCC.zip"
        self.assert_error_contains(manifest, "FILENAME_BASENAME_REQUIRED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
