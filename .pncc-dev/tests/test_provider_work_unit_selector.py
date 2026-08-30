#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pncc_provider_selector",
    ROOT / ".pncc-dev" / "scripts" / "select_provider_work_unit.py",
)
selector = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(selector)

HEAD = "a" * 40
OTHER = "b" * 40


def marker(*, wid="PIPE-WU-079", state="ACTIVE", domain="wave5-selector", base=HEAD, runtime=False, branch=None):
    attrs = ["schema=1", f"id={wid}", f"state={state}", f"conflict_domain={domain}"]
    if branch is not None:
        attrs.append(f"branch={branch}")
    attrs.extend([f"base={base}", f"runtime_required={'true' if runtime else 'false'}"])
    return "<!-- PNCC-WORK-UNIT " + " ".join(attrs) + " -->"


def issue(number, body, title=None, **extra):
    value = {"number": number, "title": title or f"Issue {number}", "body": body, "state": "open"}
    value.update(extra)
    return value


class MarkerTests(unittest.TestCase):
    def test_current_intake_marker_without_branch(self):
        parsed = selector.parse_issue_intake_marker(marker())
        self.assertEqual(parsed["materialization_phase"], "INTAKE")
        self.assertIsNone(parsed["branch"])
        self.assertEqual(parsed["work_unit_id"], "PIPE-WU-079")

    def test_legacy_materialized_marker_with_branch(self):
        parsed = selector.parse_issue_intake_marker(marker(branch="agent/PIPE-WU-079-a1"))
        self.assertEqual(parsed["materialization_phase"], "MATERIALIZED")
        self.assertEqual(parsed["branch"], "agent/PIPE-WU-079-a1")

    def test_attribute_order_is_not_semantic(self):
        body = f"<!-- PNCC-WORK-UNIT runtime_required=false base={HEAD} conflict_domain=x state=READY id=PIPE-WU-080 schema=1 -->"
        self.assertEqual(selector.parse_issue_intake_marker(body)["work_unit_id"], "PIPE-WU-080")

    def test_unmarked_issue_is_not_work_unit(self):
        self.assertIsNone(selector.parse_issue_intake_marker("umbrella tracker"))

    def test_missing_required_attribute_blocks(self):
        body = "<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-080 state=READY conflict_domain=x runtime_required=false -->"
        with self.assertRaisesRegex(selector.SelectionError, "WORK_UNIT_MARKER_MISSING:base"):
            selector.parse_issue_intake_marker(body)

    def test_unknown_attribute_blocks(self):
        with self.assertRaisesRegex(selector.SelectionError, "WORK_UNIT_MARKER_UNKNOWN:authority"):
            selector.parse_issue_intake_marker(marker().replace(" -->", " authority=write -->"))

    def test_duplicate_marker_blocks(self):
        with self.assertRaisesRegex(selector.SelectionError, "WORK_UNIT_MARKER_COUNT:2"):
            selector.parse_issue_intake_marker(marker() + "\n" + marker(wid="PIPE-WU-080", domain="other"))


class SelectionTests(unittest.TestCase):
    def select(self, issues):
        return selector.select_from_provider_issues(
            issues,
            repository="kmephis-ai/VPS-Control-PNCC",
            default_branch="main",
            default_head_sha=HEAD,
            observed_at="2026-08-29T07:00:00Z",
        )

    def test_no_governed_work_is_no_work(self):
        result = self.select([issue(1, "provenance residual"), issue(6, "umbrella"), issue(15, "provider admin")])
        self.assertEqual(result["decision"], "NO_EXECUTABLE_WORK_UNIT")
        self.assertEqual(result["orchestration_disposition"], "NO_WORK")
        self.assertEqual(result["next_boundary"], "WAIT_FOR_OR_MATERIALIZE_GOVERNED_WORK_UNIT")
        self.assertEqual([x["issue"] for x in result["ignored_issues"]], [1, 6, 15])

    def test_current_wu_is_executable_read_only(self):
        result = self.select([issue(1, "residual"), issue(188, marker())])
        self.assertEqual(result["decision"], "SELECTED")
        self.assertEqual(result["orchestration_disposition"], "EXECUTABLE")
        self.assertEqual(result["selected"]["work_unit_id"], "PIPE-WU-079")
        self.assertEqual(result["next_boundary"], "DESIGN_DEFAULT_DENY_WRITER_LEASE_CLAIM_AUTHORITY")
        self.assertFalse(result["provider_mutation_performed"])
        self.assertFalse(result["writer_lease_acquired"])
        self.assertEqual(result["mutation_authority"], "NONE_BINDING_IS_PROOF_ONLY")

    def test_deterministic_lowest_issue_selection(self):
        result = self.select([
            issue(200, marker(wid="PIPE-WU-081", domain="d2")),
            issue(190, marker(wid="PIPE-WU-080", domain="d1")),
        ])
        self.assertEqual(result["selected"]["issue"], 190)
        self.assertEqual(result["executable_count"], 2)

    def test_runtime_required_is_waiting_runtime(self):
        result = self.select([issue(190, marker(wid="PIPE-WU-080", runtime=True))])
        self.assertEqual(result["canonical_work_units"][0]["classification"], "WAITING_RUNTIME")
        self.assertEqual(result["orchestration_disposition"], "WAITING_RUNTIME")
        self.assertEqual(result["next_boundary"], "WAIT_FOR_PRIVATE_RUNTIME_EVIDENCE")

    def test_waiting_runtime_has_priority_over_generic_block(self):
        result = self.select([
            issue(190, marker(wid="PIPE-WU-080", domain="runtime", runtime=True)),
            issue(191, marker(wid="PIPE-WU-081", state="BLOCKED", domain="blocked")),
        ])
        self.assertEqual(result["orchestration_disposition"], "WAITING_RUNTIME")

    def test_stale_base_is_blocked_disposition(self):
        result = self.select([issue(190, marker(wid="PIPE-WU-080", base=OTHER))])
        self.assertEqual(result["canonical_work_units"][0]["classification"], "STALE_BASE")
        self.assertEqual(result["orchestration_disposition"], "BLOCKED")
        self.assertEqual(result["next_boundary"], "RECONCILE_PROVIDER_TRUTH_OR_GOVERNED_BOUNDARY")

    def test_blocked_and_verifying_are_blocked_disposition(self):
        result = self.select([
            issue(190, marker(wid="PIPE-WU-080", state="BLOCKED", domain="d1")),
            issue(191, marker(wid="PIPE-WU-081", state="VERIFYING", domain="d2")),
        ])
        self.assertEqual([x["classification"] for x in result["canonical_work_units"]], ["BLOCKED", "WAITING_PROVIDER"])
        self.assertEqual(result["orchestration_disposition"], "BLOCKED")

    def test_only_terminal_markers_are_no_work(self):
        result = self.select([
            issue(190, marker(wid="PIPE-WU-080", state="DONE", domain="d1")),
            issue(191, marker(wid="PIPE-WU-081", state="SUPERSEDED", domain="d2")),
        ])
        self.assertEqual(result["orchestration_disposition"], "NO_WORK")

    def test_terminal_open_marker_is_ignored_for_conflict_collision(self):
        result = self.select([
            issue(190, marker(wid="PIPE-WU-080", state="DONE", domain="same")),
            issue(191, marker(wid="PIPE-WU-081", state="READY", domain="same")),
        ])
        self.assertEqual(result["decision"], "SELECTED")
        self.assertEqual(result["selected"]["work_unit_id"], "PIPE-WU-081")

    def test_duplicate_open_work_unit_id_blocks(self):
        with self.assertRaisesRegex(selector.SelectionError, "DUPLICATE_OPEN_WORK_UNIT_ID"):
            self.select([
                issue(190, marker(wid="PIPE-WU-080", domain="d1")),
                issue(191, marker(wid="PIPE-WU-080", domain="d2")),
            ])

    def test_duplicate_open_conflict_domain_blocks(self):
        with self.assertRaisesRegex(selector.SelectionError, "DUPLICATE_OPEN_CONFLICT_DOMAIN"):
            self.select([
                issue(190, marker(wid="PIPE-WU-080", domain="same")),
                issue(191, marker(wid="PIPE-WU-081", domain="same")),
            ])

    def test_malformed_open_marker_blocks_provider_truth(self):
        malformed = "<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-080 state=READY conflict_domain=x runtime_required=false -->"
        with self.assertRaisesRegex(selector.SelectionError, "MALFORMED_OPEN_WORK_UNIT_MARKER"):
            self.select([issue(190, malformed)])

    def test_pull_request_entries_from_issues_endpoint_are_ignored(self):
        result = self.select([issue(190, marker(), pull_request={"url": "https://example.invalid/pr/190"})])
        self.assertEqual(result["orchestration_disposition"], "NO_WORK")
        self.assertEqual(result["ignored_issues"][0]["reason"], "PULL_REQUEST_NOT_ISSUE")

    def test_result_is_default_deny_schema_v2(self):
        result = self.select([issue(190, marker())])
        self.assertEqual(result["schema_version"], 2)
        self.assertFalse(result["provider_mutation_performed"])
        self.assertFalse(result["writer_lease_acquired"])
        self.assertFalse(result["runtime_action_performed"])
        self.assertFalse(result["promotion_or_release_action_performed"])


class ReadinessGuardTests(unittest.TestCase):
    def test_repository_readiness_guard_is_transition_safe(self):
        readiness = json.loads((ROOT / ".adwf-consumer/wave5-readiness.json").read_text(encoding="utf-8"))
        if readiness.get("framework", {}).get("source_sha") == selector.EXPECTED_ADWF_SHA:
            selector.validate_readiness_guard(ROOT)
            return
        frontier = json.loads((ROOT / ".pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json").read_text(encoding="utf-8"))
        self.assertEqual(frontier.get("state"), "ACTIVE")
        self.assertEqual(frontier.get("frontier_id"), "PROVIDER_TRUTH_PLANNER_SELECTOR_CONTINUATION_INTEGRATION")
        self.assertEqual(frontier.get("runtime_required"), False)
        self.assertEqual(
            frontier.get("next_natural_boundary"),
            "EXACT_HEAD_CI_INSPECTION_CLASSIFICATION_RECOVERY_INTEGRATION",
        )
        with self.assertRaisesRegex(selector.SelectionError, "^WAVE5_ADWF_PIN_DRIFT$"):
            selector.validate_readiness_guard(ROOT)

    def test_selector_is_bound_to_current_v701_truth_not_v700(self):
        source = (ROOT / ".pncc-dev/scripts/select_provider_work_unit.py").read_text(encoding="utf-8")
        self.assertIn("stable-v7.0.1-completion.json", source)
        self.assertIn("22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72", source)
        self.assertNotIn("stable-v7.0.0-completion.json", source)
        self.assertNotIn("1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599", source)

    def test_readiness_baseline_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for rel in (
                ".adwf-consumer/wave5-readiness.json",
                ".adwf-consumer/external-binding.json",
                ".pncc-dev/attestations/stable-v7.0.1-completion.json",
            ):
                src = ROOT / rel
                dst = tmp / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
            path = tmp / ".adwf-consumer/wave5-readiness.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["stable_baseline"]["version"] = "7.0.0"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(selector.SelectionError, "WAVE5_STABLE_BASELINE_DRIFT"):
                selector.validate_readiness_guard(tmp)


if __name__ == "__main__":
    unittest.main()
