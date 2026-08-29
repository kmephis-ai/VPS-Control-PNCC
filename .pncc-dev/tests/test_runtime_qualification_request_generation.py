import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_runtime_qualification_request.py"
SPEC = importlib.util.spec_from_file_location("pncc_runtime_request_generator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


SOURCE_SHA = "1e097775d11fcd7b4639045c36a5b4e9404696a4"
ARTIFACT_SHA = "1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599"
PROVIDER_DIGEST = "b" * 64
RUN_ID = 33199999999


def stable_manifest(version="7.0.0"):
    return {
        "schema_version": 1,
        "contract_id": "PNCC_CANDIDATE_ARTIFACT_TRUTH_V1",
        "candidate_id": f"PNCC-V{version}-1E097775D11F",
        "artifact_role": "RUNTIME_CANDIDATE",
        "source": {
            "repository": "kmephis-ai/VPS-Control-PNCC",
            "commit_sha": SOURCE_SHA,
            "ref": "refs/heads/main",
            "identity_semantic": "EXACT_SOURCE_COMMIT",
            "path": "src/windows-v7",
        },
        "artifact": {
            "filename": f"VPS-Control-v{version}.zip",
            "sha256": ARTIFACT_SHA,
            "size_bytes": 700897,
        },
        "build": {
            "workflow": "candidate-builder",
            "run_id": RUN_ID,
            "run_attempt": 1,
            "job_name": "candidate-builder-main",
            "created_at_utc": "2026-08-28T15:41:25Z",
            "builder": "GITHUB_HOSTED",
        },
        "provenance": {
            "artifact_origin": "BUILD_OUTPUT",
            "sanitation_state": "EXACT_BUILD_OUTPUT",
            "attestation_state": "HOSTED_PROVENANCE_RECORDED",
            "runtime_authority": False,
        },
        "runtime": {
            "qualification_state": "NOT_VERIFIED",
            "evidence_ref": None,
            "promotion_eligible": False,
        },
    }


class RuntimeQualificationRequestGenerationTests(unittest.TestCase):
    def _build(self, version="7.0.0"):
        return MODULE.build_request(
            manifest=stable_manifest(version),
            provider_artifact_id=987654321,
            provider_artifact_digest=PROVIDER_DIGEST,
            provider_build_run_id=RUN_ID,
            origin_work_unit_id="PIPE-WU-082",
        )

    def test_stable_v7_request_binds_provider_identity_and_preserves_invariants(self):
        request = self._build("7.0.0")
        self.assertEqual(request["contract_id"], "PNCC_RUNTIME_QUALIFICATION_REQUEST_V1")
        self.assertEqual(request["request_id"], "PNCC-RQ-V7.0.0-1E097775D11F")
        self.assertEqual(request["origin_work_unit_id"], "PIPE-WU-082")
        self.assertEqual(request["candidate"]["candidate_id"], "PNCC-V7.0.0-1E097775D11F")
        self.assertEqual(request["candidate"]["source_sha"], SOURCE_SHA)
        self.assertEqual(request["candidate"]["artifact_filename"], "VPS-Control-v7.0.0.zip")
        self.assertEqual(request["candidate"]["artifact_sha256"], ARTIFACT_SHA)
        self.assertEqual(request["candidate"]["artifact_size_bytes"], 700897)
        self.assertEqual(request["candidate"]["provider_artifact_id"], 987654321)
        self.assertEqual(request["candidate"]["provider_artifact_digest"], PROVIDER_DIGEST)
        self.assertEqual(request["candidate"]["provider_build_run_id"], RUN_ID)
        self.assertEqual(request["required_scopes"], MODULE.REQUIRED_SCOPES)
        self.assertEqual(request["expected_invariants"], MODULE.EXPECTED_INVARIANTS)
        self.assertEqual(request["state"], "RUNTIME_PENDING")
        self.assertIs(request["runtime_authority"], False)
        self.assertIs(request["promotion_eligible"], False)

    def test_stable_patch_v701_request_is_version_bound(self):
        request = self._build("7.0.1")
        self.assertEqual(request["request_id"], "PNCC-RQ-V7.0.1-1E097775D11F")
        self.assertEqual(request["candidate"]["candidate_id"], "PNCC-V7.0.1-1E097775D11F")
        self.assertEqual(request["candidate"]["artifact_filename"], "VPS-Control-v7.0.1.zip")
        self.assertIs(request["runtime_authority"], False)
        self.assertIs(request["promotion_eligible"], False)

    def test_provider_run_mismatch_fails_closed(self):
        with self.assertRaisesRegex(MODULE.RequestError, "provider build run mismatch"):
            MODULE.build_request(
                manifest=stable_manifest(),
                provider_artifact_id=1,
                provider_artifact_digest=PROVIDER_DIGEST,
                provider_build_run_id=RUN_ID + 1,
                origin_work_unit_id="PIPE-WU-082",
            )

    def test_rc_candidate_is_rejected_for_stable_request(self):
        manifest = stable_manifest()
        manifest["candidate_id"] = "PNCC-RC14.39-1E097775D11F"
        manifest["artifact"]["filename"] = "VPS-Control-v7.0.0-rc14.39.zip"
        with self.assertRaisesRegex(MODULE.RequestError, "Stable 7.0.x candidate required"):
            MODULE.build_request(
                manifest=manifest,
                provider_artifact_id=1,
                provider_artifact_digest=PROVIDER_DIGEST,
                provider_build_run_id=RUN_ID,
                origin_work_unit_id="PIPE-WU-082",
            )

    def test_malformed_provider_digest_fails_closed(self):
        with self.assertRaisesRegex(MODULE.RequestError, "provider artifact digest"):
            MODULE.build_request(
                manifest=stable_manifest(),
                provider_artifact_id=1,
                provider_artifact_digest="sha256:" + PROVIDER_DIGEST,
                provider_build_run_id=RUN_ID,
                origin_work_unit_id="PIPE-WU-082",
            )

    def test_candidate_source_suffix_mismatch_fails_closed(self):
        manifest = stable_manifest("7.0.1")
        manifest["candidate_id"] = "PNCC-V7.0.1-AAAAAAAAAAAA"
        with self.assertRaisesRegex(MODULE.RequestError, "candidate id/source SHA mismatch"):
            MODULE.build_request(
                manifest=manifest,
                provider_artifact_id=1,
                provider_artifact_digest=PROVIDER_DIGEST,
                provider_build_run_id=RUN_ID,
                origin_work_unit_id="PIPE-WU-082",
            )

    def test_candidate_artifact_version_mismatch_fails_closed(self):
        manifest = stable_manifest("7.0.1")
        manifest["artifact"]["filename"] = "VPS-Control-v7.0.0.zip"
        with self.assertRaisesRegex(MODULE.RequestError, "unexpected Stable artifact filename"):
            MODULE.build_request(
                manifest=manifest,
                provider_artifact_id=1,
                provider_artifact_digest=PROVIDER_DIGEST,
                provider_build_run_id=RUN_ID,
                origin_work_unit_id="PIPE-WU-082",
            )


if __name__ == "__main__":
    unittest.main()
