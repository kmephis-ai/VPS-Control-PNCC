#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pncc_provider_continuation",
    ROOT / ".pncc-dev/scripts/evaluate_provider_truth_continuation.py",
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)

HEAD = "a" * 40


def issue(number: int, *, state="open", body="", title=None):
    return {"number": number, "state": state, "body": body, "title": title or f"Issue {number}"}


def selected_result(count=1):
    selected = {
        "issue": 259,
        "work_unit_id": "PIPE-WU-106",
        "state": "READY",
        "conflict_domain": "wave5-provider-truth-planner-selector-continuation-integration",
        "base_sha": HEAD,
        "branch": None,
        "runtime_required": False,
        "materialization_phase": "INTAKE",
        "classification": "EXECUTABLE_READ_ONLY_SELECTION",
        "reason": None,
    }
    return {
        "schema_version": 2,
        "role": "READ_ONLY_PROVIDER_WORK_UNIT_SELECTION",
        "state": "READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS",
        "decision": "SELECTED",
        "orchestration_disposition": "EXECUTABLE",
        "selected": selected,
        "executable_count": count,
        "canonical_work_units": [selected],
        "provider_mutation_performed": False,
    }


def no_work_result():
    return {
        "schema_version": 2,
        "role": "READ_ONLY_PROVIDER_WORK_UNIT_SELECTION",
        "state": "READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS",
        "decision": "NO_EXECUTABLE_WORK_UNIT",
        "orchestration_disposition": "NO_WORK",
        "selected": None,
        "executable_count": 0,
        "canonical_work_units": [],
        "provider_mutation_performed": False,
    }


class FakeSelector:
    EXPECTED_ADWF_SHA = "c7e0c059a901869d6369864e98d06238484778ec"

    class SelectionError(ValueError):
        pass

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def select_from_provider_issues(self, *args, **kwargs):
        self.calls += 1
        return self.result


class FakePlanner:
    def __init__(self, result):
        self.result = result
        self.calls = 0
        self.snapshots = []

    def plan_materialization(self, snapshot):
        self.calls += 1
        self.snapshots.append(snapshot)
        return self.result


def planner_eligible():
    return {
        "schema_version": 1,
        "role": "GOVERNED_WORK_UNIT_MATERIALIZATION_PLAN",
        "decision": "MATERIALIZATION_ELIGIBLE",
        "reasons": [],
        "proposal": {"work_unit_id": "PIPE-WU-107"},
        "provider_mutation_performed": False,
        "issue_mutation_performed": False,
    }


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = mod.load_json(mod.POLICY_PATH)

    def evaluate(self, selector_result, planner_result=None, open_issues=None, history=None):
        selector = FakeSelector(selector_result)
        planner = FakePlanner(planner_result or planner_eligible())
        if open_issues is None:
            open_issues = [issue(259)]
        if history is None:
            history = list(open_issues)
        result = mod.evaluate_continuation(
            open_issues=open_issues,
            issue_history=history,
            repository="kmephis-ai/VPS-Control-PNCC",
            default_branch="main",
            default_head_sha=HEAD,
            observed_at="2026-08-30T08:00:00Z",
            provider_truth_fresh=True,
            issue_history_complete=True,
            policy=self.policy,
            selector_module=selector,
            planner_module=planner,
            check_anchors=False,
            guard_checker=lambda *_args, **_kwargs: "PROVEN_RECONCILED_PIN_DRIFT",
        )
        return result, selector, planner

    def test_policy_is_read_only_default_deny(self):
        mod.validate_policy(self.policy)
        self.assertTrue(self.policy["provider_truth_fresh_required"])
        self.assertTrue(all(self.policy[key] is False for key in mod.FALSE_AUTHORITIES))

    def test_canonical_anchor_map_is_exact(self):
        mod.validate_anchor_map(self.policy)

    def test_repository_guard_accepts_only_exact_reconciled_pin_drift(self):
        selector = mod.load_module("selector_for_wu106_test", mod.SELECTOR_PATH)
        self.assertEqual(
            mod.validate_selector_guard(selector, self.policy),
            "PROVEN_RECONCILED_PIN_DRIFT",
        )

    def test_exactly_one_executable_continues_without_planner(self):
        result, selector, planner = self.evaluate(selected_result())
        self.assertEqual(result["decision"], "CONTINUE_SELECTED_WORK_UNIT")
        self.assertEqual(result["selected"]["work_unit_id"], "PIPE-WU-106")
        self.assertEqual(selector.calls, 1)
        self.assertEqual(planner.calls, 0)
        self.assertIsNone(result["materialization_plan"])

    def test_multiple_executable_work_units_block(self):
        result, _, planner = self.evaluate(selected_result(count=2))
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("EXECUTABLE_SELECTION_NOT_EXACTLY_ONE", result["reasons"][0])
        self.assertEqual(planner.calls, 0)

    def test_no_work_derives_plan_only_materialization(self):
        history = [
            issue(257, state="closed", body="<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-105 state=READY conflict_domain=old base=" + HEAD + " runtime_required=false -->"),
        ]
        result, _, planner = self.evaluate(no_work_result(), open_issues=[], history=history)
        self.assertEqual(result["decision"], "PLAN_MATERIALIZATION")
        self.assertEqual(planner.calls, 1)
        snap = planner.snapshots[0]
        self.assertEqual(snap["selector_disposition"], "NO_WORK")
        self.assertTrue(snap["provider_truth_fresh"])
        self.assertTrue(snap["issue_history_complete"])
        self.assertFalse(result["provider_mutation_performed"])
        self.assertFalse(result["issue_mutation_performed"])

    def test_no_work_planner_block_propagates_fail_closed(self):
        blocked = {
            "decision": "BLOCKED",
            "reasons": ["FRONTIER_DRIFT"],
            "provider_mutation_performed": False,
            "issue_mutation_performed": False,
        }
        result, _, _ = self.evaluate(no_work_result(), planner_result=blocked, open_issues=[], history=[])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("MATERIALIZATION_PLANNER_BLOCKED:FRONTIER_DRIFT", result["reasons"][0])

    def test_no_frontier_is_terminal_read_only_decision(self):
        no_frontier = {
            "decision": "NO_FRONTIER",
            "reasons": [],
            "provider_mutation_performed": False,
            "issue_mutation_performed": False,
        }
        result, _, _ = self.evaluate(no_work_result(), planner_result=no_frontier, open_issues=[], history=[])
        self.assertEqual(result["decision"], "NO_FRONTIER")
        self.assertIsNone(result["next_boundary"])

    def test_waiting_runtime_never_calls_planner(self):
        waiting = no_work_result()
        waiting["orchestration_disposition"] = "WAITING_RUNTIME"
        result, _, planner = self.evaluate(waiting)
        self.assertEqual(result["decision"], "WAITING_RUNTIME")
        self.assertEqual(planner.calls, 0)
        self.assertFalse(result["runtime_action_performed"])

    def test_selector_block_is_fail_closed(self):
        blocked = no_work_result()
        blocked["orchestration_disposition"] = "BLOCKED"
        result, _, planner = self.evaluate(blocked)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(planner.calls, 0)

    def test_incomplete_issue_history_blocks(self):
        selector = FakeSelector(selected_result())
        planner = FakePlanner(planner_eligible())
        result = mod.evaluate_continuation(
            open_issues=[issue(259)],
            issue_history=[issue(259)],
            repository="kmephis-ai/VPS-Control-PNCC",
            default_branch="main",
            default_head_sha=HEAD,
            observed_at="2026-08-30T08:00:00Z",
            provider_truth_fresh=True,
            issue_history_complete=False,
            policy=self.policy,
            selector_module=selector,
            planner_module=planner,
            check_anchors=False,
            guard_checker=lambda *_args, **_kwargs: "PROVEN_RECONCILED_PIN_DRIFT",
        )
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("ISSUE_HISTORY_INCOMPLETE", result["reasons"][0])

    def test_open_history_mismatch_blocks(self):
        result, selector, planner = self.evaluate(
            selected_result(),
            open_issues=[issue(259, body="a")],
            history=[issue(259, body="b")],
        )
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(selector.calls, 0)
        self.assertEqual(planner.calls, 0)

    def test_all_decisions_report_zero_mutation(self):
        result, _, _ = self.evaluate(selected_result())
        for key in (
            "provider_mutation_performed",
            "issue_mutation_performed",
            "writer_lease_mutation_performed",
            "merge_performed",
            "runtime_action_performed",
        ):
            self.assertIs(result[key], False)


if __name__ == "__main__":
    unittest.main()
