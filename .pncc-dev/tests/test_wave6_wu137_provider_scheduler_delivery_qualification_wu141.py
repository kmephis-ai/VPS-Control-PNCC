#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = ROOT / ".pncc-dev/contracts/wave6-wu137-provider-scheduler-delivery-qualification-wu141.json"
ACTIVATION_PATH = ROOT / ".pncc-dev/contracts/wave6-hbe-periodic-health-drift-activation-wu137.json"
WORKFLOW_PATH = ROOT / ".github/workflows/wave6-hbe-periodic-health-drift-wu137.yml"
FRONTIER_PATH = ROOT / ".pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json"

EXPECTED_ANCHORS = {
    ".github/workflows/wave6-hbe-periodic-health-drift-wu137.yml": "524ff5813cb45476fa332f7ebfdc195931ce0dff",
    ".pncc-dev/contracts/wave6-hbe-periodic-health-drift-activation-wu137.json": "37e08c46e021e04f1be6b799009b6f24111c1ac3",
    ".pncc-dev/scripts/evaluate_wave6_hbe_periodic_health_drift_wu137.py": "d478fdc13afcf81b30d59952a44cc2aad8d5d5fe",
    ".pncc-dev/tests/test_wave6_hbe_periodic_health_drift_wu137.py": "d1e292178284663e4a5b6636d857c145aa31748e",
    ".pncc-dev/contracts/wave6-hbe-periodic-health-drift-authority-proposal-wu136.json": "7605105488aafad7400c26c13a5c8f5515d40a02",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git_blob(relative: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(ROOT / relative)], text=True
    ).strip()


class TestWU141ProviderSchedulerDeliveryQualification(unittest.TestCase):
    def test_terminal_artifact_is_observational_not_repair_authority(self):
        a = load_json(ARTIFACT_PATH)
        self.assertEqual(a["schema_version"], 1)
        self.assertEqual(a["role"], "WAVE6_WU137_PROVIDER_SCHEDULER_DELIVERY_QUALIFICATION")
        self.assertEqual(a["work_unit_id"], "PIPE-WU-141")
        self.assertEqual(a["issue_number"], 327)
        self.assertEqual(a["state"], "COMPLETE")
        self.assertEqual(a["verdict"], "PROVIDER_SCHEDULER_DELIVERY_NOT_OBSERVED")
        self.assertEqual(a["authorized_base_sha"], "7e85b5d3d4efabc2369ed301bd392c81dcd55b01")
        self.assertFalse(a["runtime_required"])
        c = a["classification"]
        self.assertFalse(c["configuration_defect_proven"])
        self.assertFalse(c["external_provider_blocked_proven"])
        self.assertEqual(c["external_provider_correlation"], "STRONG_NON_AUTHORITATIVE")
        self.assertFalse(c["schedule_delivery_observed"])
        self.assertFalse(c["repair_authorized"])
        self.assertFalse(c["authority_granted"])
        self.assertTrue(all(value is False for value in a["mutation_report"].values()))

    def test_provider_snapshot_is_exact_and_bounded_to_elapsed_ticks(self):
        a = load_json(ARTIFACT_PATH)
        p = a["provider_evidence"]
        self.assertEqual(p["main_sha"], "7e85b5d3d4efabc2369ed301bd392c81dcd55b01")
        self.assertEqual(p["default_branch"], "main")
        self.assertFalse(p["repository_disabled"])
        self.assertEqual(p["wu137_merged_at"], "2026-08-31T17:40:59Z")
        self.assertEqual(p["canonical_cron_utc"], "17 * * * *")
        self.assertEqual(
            p["elapsed_nominal_ticks"],
            [
                "2026-08-31T18:17:00Z",
                "2026-08-31T19:17:00Z",
                "2026-08-31T20:17:00Z",
            ],
        )
        self.assertEqual(p["repository_schedule_run_count"], 0)
        self.assertEqual(p["authorization_issue_number"], 322)
        self.assertEqual(p["authorization_issue_state"], "closed")
        self.assertTrue(p["authorization_tokens_present"])
        self.assertEqual(p["canonical_frontier_state"], "NONE")
        self.assertEqual(p["ruleset_id"], 21585301)
        self.assertEqual(p["ruleset_enforcement"], "active")
        self.assertEqual(p["ruleset_bypass_actors"], [])
        self.assertEqual(p["ruleset_current_user_can_bypass"], "never")
        self.assertTrue(p["strict_required_status_checks_policy"])
        self.assertEqual(
            p["required_check_contexts"],
            ["repo-integrity", "powershell-static", "truth-contract"],
        )
        self.assertEqual(
            p["required_check_conclusions"],
            {
                "repo-integrity": "success",
                "powershell-static": "success",
                "truth-contract": "success",
            },
        )
        self.assertEqual(p["writer_lease_registry_generation"], 55)
        self.assertEqual(p["writer_lease_id"], "d6b01933-066f-4697-bc96-be44fd087ee2")
        self.assertEqual(
            p["provider_state_commit_sha_after_wu141_lease_acquisition"],
            "241e07147dc12954a57abd5d5c426b7322d86734",
        )
        self.assertEqual(
            p["writer_lease_registry_blob_sha"],
            "4122c57c2198e9bf70e6ba91793f8b6e52d7ebff",
        )

    def test_wu137_and_proposal_anchors_are_byte_identical(self):
        artifact = load_json(ARTIFACT_PATH)
        self.assertEqual(artifact["wu137_immutable_anchor_blobs"], EXPECTED_ANCHORS)
        for relative, expected in EXPECTED_ANCHORS.items():
            with self.subTest(path=relative):
                self.assertEqual(git_blob(relative), expected)

    def test_wu137_schedule_and_permissions_remain_read_only(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        low = text.lower()
        self.assertIn("cron: '17 * * * *'", text)
        self.assertIn("if: github.event_name == 'schedule'", text)
        for token in (
            "contents: read",
            "issues: read",
            "pull-requests: read",
            "actions: read",
            "checks: read",
        ):
            self.assertIn(token, text)
        for token in (
            "contents: write",
            "issues: write",
            "pull-requests: write",
            "actions: write",
            "checks: write",
            "workflow_dispatch:",
            "git push",
            "gh pr merge",
            "gh issue close",
            "--method post",
            "--method patch",
            "--method put",
            "--method delete",
            "self-hosted",
        ):
            self.assertNotIn(token, low)

    def test_activation_and_frontier_do_not_grant_new_authority(self):
        activation = load_json(ACTIVATION_PATH)
        self.assertEqual(activation["activation_state"], "OWNER_AUTHORIZED_ACTIVE")
        self.assertEqual(activation["monitoring"]["cadence_seconds"], 3600)
        self.assertEqual(activation["monitoring"]["cron_utc"], "17 * * * *")
        self.assertEqual(activation["monitoring"]["overlap_policy"], "SKIP_IF_PREVIOUS_RUN_ACTIVE")
        self.assertEqual(
            activation["monitoring"]["missed_run_policy"],
            "NO_CATCH_UP_BURST_REEVALUATE_FRESH_PROVIDER_TRUTH",
        )
        self.assertTrue(all(value is False for value in activation["authority"].values()))
        self.assertEqual(load_json(FRONTIER_PATH)["state"], "NONE")

    def test_future_real_run_supersedes_observational_gap_without_repair_claim(self):
        a = load_json(ARTIFACT_PATH)
        e = a["evidence_interpretation"]
        self.assertFalse(e["provider_schedule_delivery_is_proven"])
        self.assertFalse(e["repository_configuration_defect_is_proven"])
        self.assertFalse(e["current_evidence_requires_wu137_repair"])
        self.assertTrue(e["real_future_schedule_run_supersedes_this_observational_gap_for_delivery_proof"])
        self.assertEqual(
            a["next_boundary"],
            "WAIT_FOR_REAL_PROVIDER_SCHEDULE_RUN_OR_SEPARATE_OWNER_DECISION",
        )


if __name__ == "__main__":
    unittest.main()
