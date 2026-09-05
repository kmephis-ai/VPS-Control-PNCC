import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-wu206-post-remediation-installer-artifact-readiness.json"
WORKFLOW = ROOT / ".github/workflows/wave6-wu206-post-remediation-installer-artifact-readiness.yml"


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_exact_current_identity_and_reference_candidate():
    c = load_contract()
    assert c["schema_version"] == 1
    assert c["role"] == "POST_REMEDIATION_INSTALLER_ARTIFACT_AUTHORITY_READINESS"
    assert c["work_unit_id"] == "PIPE-WU-206"
    assert c["source_main_sha"] == "7eba68fd235be2ea6ef39389eb990e231a69ceec"
    assert c["canonical_installer_definition"] == {
        "path": "installer/windows/VPS-Control-PNCC.iss",
        "git_blob_sha": "b744a7446e86b34b4be1df01349e7c033da81644",
    }
    q = c["qualified_reference_candidate"]
    assert q["source_work_unit_id"] == "PIPE-WU-205"
    assert q["filename"] == "VPS-Control-PNCC-v7.0.2-setup.exe"
    assert q["size_bytes"] == 2230927
    assert q["sha256"] == "b3d9a6d7e6562933d405333be51de94ccd009cabeaf6ab6877a0616b61d3b8a6"
    assert q["candidates_identical"] is True


def test_wu200_authority_is_explicitly_non_transferable():
    c = load_contract()
    old = c["superseded_artifact_authority"]
    assert old["issue_number"] == 450
    assert old["work_unit_id"] == "PIPE-WU-200"
    assert old["bound_installer_definition_git_blob_sha"] == "d30a158aef3535a9066608495b45abcf41112926"
    assert old["bound_execution_main_sha"] == "ceb649ae1f5c4c65614fb9db02d716ea71087b7c"
    assert old["classification"] == "PRE_REMEDIATION_ARTIFACT_AUTHORITY_NON_TRANSFERABLE"
    assert old["transferable_to_current_definition"] is False
    assert old["bound_installer_definition_git_blob_sha"] != c["canonical_installer_definition"]["git_blob_sha"]


def test_wu206_has_zero_build_upload_or_product_authority():
    a = load_contract()["wu206_authority"]
    assert a["control_plane_contract"] is True
    assert a["readiness_classification"] is True
    assert a["exact_identity_binding"] is True
    for key in (
        "compiler_acquisition", "compiler_installation", "compiler_execution", "binary_build",
        "artifact_upload", "artifact_publication", "artifact_persistence", "product_runtime_mutation",
        "self_hosted_runner", "release", "tag", "stable_transition", "reserve_1080_lifecycle_mutation",
        "primary_1081_lifecycle_mutation", "v631_mutation", "ruleset_security_weakening", "force_bypass",
    ):
        assert a[key] is False, key


def test_future_grant_shape_is_fail_closed_and_exactly_bound():
    c = load_contract()
    g = c["future_owner_grant_required"]
    assert g["required"] is True
    assert g["must_bind_post_merge_exact_main"] is True
    assert g["must_bind_installer_definition_git_blob_sha"] == c["canonical_installer_definition"]["git_blob_sha"]
    assert g["must_bind_pinned_compiler_sha256"] == c["pinned_compiler"]["sha256"]
    assert g["allowed_artifact_filename"] == "VPS-Control-PNCC-v7.0.2-setup.exe"
    assert g["artifact_count"] == 1
    assert g["github_hosted_windows_only"] is True
    assert g["sha256_provenance_required"] is True
    assert g["short_retention_required"] is True
    for key in (
        "release_tag_stable_forbidden", "other_product_runtime_mutation_forbidden",
        "self_hosted_runner_forbidden", "lifecycle_1080_1081_changes_forbidden",
        "v631_mutation_forbidden", "ruleset_security_weakening_forbidden", "force_bypass_forbidden",
    ):
        assert g[key] is True, key
    assert c["classification"] == "POST_REMEDIATION_ARTIFACT_AUTHORITY_REQUIRES_FRESH_OWNER_GRANT"


def test_workflow_is_validation_only_and_least_authority():
    wf = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "pull_request:",
        "contents: read",
        "test_wu206_post_remediation_installer_artifact_readiness.py",
        "7eba68fd235be2ea6ef39389eb990e231a69ceec",
    )
    for token in required:
        assert token in wf
    forbidden = (
        "workflow_dispatch", "issues:", "schedule:", "self-hosted", "upload-artifact", "actions/cache",
        "Invoke-WebRequest", "curl ", "wget ", "Start-Process", "ISCC.exe", "innosetup-7.1.0-x64.exe",
        "contents: write", "issues: write", "pull-requests: write", "security-events: write",
    )
    for token in forbidden:
        assert token not in wf, token
