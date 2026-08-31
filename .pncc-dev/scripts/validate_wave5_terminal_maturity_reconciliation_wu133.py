#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

PNCC_DEV = Path(__file__).resolve().parents[1]
ROOT = PNCC_DEV.parent
EVIDENCE = PNCC_DEV / "contracts" / "wave5-terminal-maturity-reconciliation-wu133.json"

EXPECTED_BASE = "be9ebf31919477c23bc1325f37897925d82de6cf"
EXPECTED_BRANCH = "agent/PIPE-WU-133-terminal-wave5-maturity-reconciliation"
EXPECTED_CRITERIA = {
    "FRESH_PROVIDER_WORK_UNIT_SELECTION",
    "ROUTINE_HOSTED_ENGINEERING_WITHOUT_OWNER_MICROMANAGEMENT",
    "CI_HARNESS_CLASSIFICATION_AND_NON_PRODUCT_REPAIR",
    "DURABLE_WAITING_RUNTIME",
    "CROSS_SESSION_RESUME_WITHOUT_CHAT_RECONSTRUCTION",
}
EXPECTED_FRONTIER = {
    "schema_version": 1,
    "role": "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER",
    "state": "NONE",
}
EXPECTED_FRONTIER_PATH = ".pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json"
EXPECTED_FRONTIER_BLOB = "b4cf4f19e0d89884598427ad0a6729c997e7f1fe"


def git_blob_sha(path):
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def validate(data):
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    require(data.get("schema_version") == 1, "schema_version must be 1")
    require(data.get("role") == "WAVE5_TERMINAL_MATURITY_RECONCILIATION", "unexpected role")
    require(data.get("work_unit_id") == "PIPE-WU-133", "unexpected work unit")
    require(data.get("issue") == 314, "unexpected issue")
    require(data.get("state") == "COMPLETE", "WU133 evidence must be COMPLETE")
    require(data.get("verdict") == "WAVE5_COMPLETE", "Wave 5 exit criteria are not fully proven")
    require(data.get("base_sha") == EXPECTED_BASE, "base SHA mismatch")
    require(data.get("branch") == EXPECTED_BRANCH, "branch mismatch")
    require(data.get("runtime_required") is False, "runtime must not be required")
    require(data.get("runtime_authority_claimed") is False, "runtime authority must not be claimed")
    require(data.get("stable_or_promotion_claimed") is False, "Stable/promotion must not be claimed")
    require(data.get("authority_granted") is False, "evidence must not grant authority")
    require(data.get("higher_autonomy_authorized") is False, "higher autonomy must not be authorized")

    provider = data.get("provider_truth", {})
    require(provider.get("main_sha_at_reconciliation") == EXPECTED_BASE, "provider main mismatch")
    require(provider.get("writer_lease_generation") == 43, "writer lease generation mismatch")
    require(provider.get("frontier_state") == "NONE", "frontier state must remain NONE")
    require(provider.get("frontier_mutation_performed") is False, "frontier mutation must remain false")
    require(provider.get("frontier_path") == EXPECTED_FRONTIER_PATH, "historical frontier path mismatch")
    require(provider.get("frontier_blob_sha") == EXPECTED_FRONTIER_BLOB, "historical frontier blob mismatch")

    criteria = data.get("wave5_exit_criteria", [])
    require(isinstance(criteria, list), "exit criteria must be a list")
    ids = {item.get("id") for item in criteria if isinstance(item, dict)}
    require(ids == EXPECTED_CRITERIA and len(criteria) == len(EXPECTED_CRITERIA), "exact five Wave 5 exit criteria required")
    for item in criteria:
        if not isinstance(item, dict):
            errors.append("exit criterion must be object")
            continue
        cid = item.get("id", "UNKNOWN")
        require(item.get("status") == "PROVEN", f"{cid}: status must be PROVEN")
        evidence = item.get("evidence")
        require(isinstance(evidence, list) and evidence, f"{cid}: local evidence required")
        if isinstance(evidence, list):
            for ref in evidence:
                path = ROOT / ref.get("path", "")
                require(path.is_file(), f"{cid}: evidence path missing: {ref.get('path')}")
                if path.is_file():
                    require(git_blob_sha(path) == ref.get("blob_sha"), f"{cid}: evidence blob mismatch: {ref.get('path')}")
        for provider_ref in item.get("provider_evidence", []):
            require(provider_ref.get("kind") == "ISSUE", f"{cid}: provider evidence kind must be ISSUE")
            require(isinstance(provider_ref.get("number"), int) and provider_ref["number"] > 0, f"{cid}: provider issue number invalid")
            require(str(provider_ref.get("work_unit_id", "")).startswith("PIPE-WU-"), f"{cid}: provider work unit id invalid")

    anchor = data.get("anchor_impact", {})
    require(anchor.get("current_work_unit_changes_immutable_materialization_anchors") is False, "WU133 must not change immutable materialization anchors")
    require(anchor.get("frontier_change_in_wu133") is False, "WU133 must not change frontier")
    require(anchor.get("roadmap_change_in_wu133") is False, "WU133 must not change roadmap")
    require(anchor.get("future_frontier_activation_requires_separate_owner_governance") is True, "future frontier activation must require owner governance")
    expected_anchors = anchor.get("immutable_anchor_expectations", {})
    require(isinstance(expected_anchors, dict) and expected_anchors, "immutable anchor expectations required")
    if isinstance(expected_anchors, dict):
        for rel, expected in expected_anchors.items():
            path = ROOT / rel
            require(path.is_file(), f"immutable anchor missing: {rel}")
            if path.is_file():
                require(git_blob_sha(path) == expected, f"immutable anchor drift: {rel}")

    hbe = data.get("human_by_exception_capabilities", {})
    proven = hbe.get("proven_existing_authority_only", [])
    not_authorized = hbe.get("not_authorized_or_not_proven", [])
    require(isinstance(proven, list) and proven, "proven HBE capabilities required")
    require(isinstance(not_authorized, list) and not_authorized, "unproven/unauthorized HBE capabilities required")
    require("AUTOMATIC_FRONTIER_ACTIVATION_FROM_TERMINAL_NONE" in not_authorized, "terminal NONE auto-activation must remain unauthorized")
    require("HIGHER_AUTONOMY_GRANT" in not_authorized, "higher autonomy must remain unauthorized")

    proposal = data.get("post_wave5_frontier_proposal", {})
    require(proposal.get("proposal_state") == "NON_AUTHORIZING_PROPOSAL_ONLY", "proposal must be non-authorizing")
    require(proposal.get("materialized") is False, "proposal must not be materialized")
    require(proposal.get("authority_granted") is False, "proposal must not grant authority")
    require(proposal.get("current_frontier_remains_none") is True, "historical WU133 frontier must remain NONE")
    require(proposal.get("proposed_next_work_unit_id") == "PIPE-WU-134", "next proposed WU id mismatch")
    require(proposal.get("requires_explicit_owner_authorization") is True, "next boundary must require explicit owner authorization")
    require(proposal.get("suggested_next_boundary") == "OWNER_DECISION_POST_WAVE5_HBE_FRONTIER", "next proposal boundary mismatch")

    forbidden = data.get("forbidden_mutations", {})
    require(forbidden and all(value is False for value in forbidden.values()), "forbidden mutation recorded")
    require(data.get("next_boundary") == "OWNER_DECISION_POST_WAVE5_HBE_FRONTIER", "next boundary mismatch")
    return errors


def main():
    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("PIPE-WU-133 Wave 5 terminal maturity reconciliation: PASS")


if __name__ == "__main__":
    main()
