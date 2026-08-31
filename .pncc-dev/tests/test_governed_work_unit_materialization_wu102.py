from pathlib import Path
import copy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".pncc-dev/scripts"
sys.path.insert(0, str(SCRIPTS))
import plan_governed_work_unit_materialization as planner


BASE = "0a562bdd2964629c4624be476f2569004a1e79e4"


def marker(wu_id="PIPE-WU-102", state="DONE", base=BASE, runtime=False, domain="historical-domain"):
    return (
        f"<!-- PNCC-WORK-UNIT schema=1 id={wu_id} state={state} "
        f"conflict_domain={domain} base={base} runtime_required={'true' if runtime else 'false'} -->"
    )


def issue(number, body, state="closed"):
    return {"number": number, "state": state, "body": body}


def active_frontier():
    """Stable synthetic ACTIVE frontier for historical WU102 planner tests.

    These tests exercise planner behavior, not the mutable live Wave-5 frontier.
    Keeping the fixture local prevents a legitimate canonical transition to
    terminal NONE from rewriting the semantics of historical ACTIVE scenarios.
    """
    return {
        "schema_version": 1,
        "role": "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER",
        "state": "ACTIVE",
        "frontier_id": "WU102_TEST_ACTIVE_FRONTIER",
        "title_template": "{work_unit_id} — Synthetic governed materialization test",
        "goal": "Exercise deterministic governed Work Unit materialization.",
        "conflict_domain": "wu102-synthetic-materialization-test",
        "runtime_required": False,
        "scope": ["exercise planner behavior"],
        "forbidden_scope": ["grant mutation authority"],
        "required_checks": ["pipeline-state"],
        "exit_criteria": ["planner result is deterministic"],
        "next_natural_boundary": "WU102_TEST_BOUNDARY",
    }


def snapshot():
    return {
        "schema_version": 1,
        "role": "GOVERNED_WORK_UNIT_MATERIALIZATION_SNAPSHOT",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "default_head_sha": BASE,
        "observed_at": "2026-08-29T20:30:00Z",
        "provider_truth_fresh": True,
        "issue_history_complete": True,
        "selector_disposition": "NO_WORK",
        "issues": [
            issue(1, "provenance residual", state="open"),
            issue(6, "umbrella", state="open"),
            issue(15, "ruleset admin", state="open"),
            issue(249, marker(), state="closed"),
        ],
    }


class GovernedWorkUnitMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.policy = planner.load_json(planner.POLICY_PATH)
        self.frontier = active_frontier()

    def plan(self, snap=None, policy=None, frontier=None, **kwargs):
        return planner.plan_materialization(
            snap or snapshot(),
            policy=policy or self.policy,
            frontier=frontier or self.frontier,
            **kwargs,
        )

    def test_canonical_policy_and_anchor_map_are_exact(self):
        self.assertEqual(planner.validate_policy(self.policy), [])
        self.assertEqual(planner.validate_anchor_map(self.policy), [])

    def test_no_work_proposes_deterministic_next_work_unit(self):
        result = self.plan()
        self.assertEqual(result["decision"], "MATERIALIZATION_ELIGIBLE")
        proposal = result["proposal"]
        self.assertEqual(proposal["work_unit_id"], "PIPE-WU-103")
        self.assertEqual(proposal["base_sha"], BASE)
        self.assertFalse(proposal["runtime_required"])
        self.assertTrue(proposal["title"].startswith("PIPE-WU-103 — "))
        self.assertIn("id=PIPE-WU-103 state=READY", proposal["body"])
        self.assertIn(f"base={BASE}", proposal["body"])
        self.assertIn("runtime_required=false", proposal["body"])
        self.assertFalse(result["provider_mutation_performed"])
        self.assertFalse(result["issue_mutation_performed"])

    def test_proposal_is_independent_of_provider_issue_order(self):
        a = snapshot()
        b = copy.deepcopy(a)
        b["issues"] = list(reversed(b["issues"]))
        self.assertEqual(self.plan(a)["proposal"], self.plan(b)["proposal"])

    def test_unrelated_open_issues_do_not_block(self):
        snap = snapshot()
        snap["issues"].append(issue(777, "ordinary open issue", state="open"))
        self.assertEqual(self.plan(snap)["decision"], "MATERIALIZATION_ELIGIBLE")

    def test_any_open_canonical_work_unit_blocks(self):
        snap = snapshot()
        snap["issues"].append(issue(250, marker("PIPE-WU-999", state="READY"), state="open"))
        result = self.plan(snap)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertTrue(any("OPEN_CANONICAL_WORK_UNIT_PRESENT" in r for r in result["reasons"]))

    def test_malformed_canonical_marker_blocks_fail_closed(self):
        snap = snapshot()
        snap["issues"].append(issue(250, "<!-- PNCC-WORK-UNIT schema=1 id=BROKEN -->", state="closed"))
        result = self.plan(snap)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertTrue(any("MALFORMED_CANONICAL_MARKER" in r for r in result["reasons"]))

    def test_selector_must_have_proven_no_work(self):
        snap = snapshot()
        snap["selector_disposition"] = "EXECUTABLE"
        result = self.plan(snap)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("SELECTOR_DISPOSITION_NOT_NO_WORK", result["reasons"])

    def test_provider_truth_must_be_fresh_and_complete(self):
        snap = snapshot()
        snap["provider_truth_fresh"] = False
        self.assertEqual(self.plan(snap)["decision"], "BLOCKED")
        snap = snapshot()
        snap["issue_history_complete"] = False
        self.assertEqual(self.plan(snap)["decision"], "BLOCKED")

    def test_policy_authority_drift_blocks(self):
        policy = copy.deepcopy(self.policy)
        policy["issue_create_authority"] = True
        result = self.plan(policy=policy)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("POLICY_FORBIDDEN_AUTHORITY:issue_create_authority", result["reasons"])

    def test_anchor_drift_blocks(self):
        policy = copy.deepcopy(self.policy)
        policy["anchor_blobs"]["selector"] = "0" * 40
        result = self.plan(policy=policy)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertTrue(any(r.startswith("ANCHOR_DRIFT:selector:") for r in result["reasons"]))

    def test_runtime_frontier_blocks(self):
        frontier = copy.deepcopy(self.frontier)
        frontier["runtime_required"] = True
        result = self.plan(frontier=frontier)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("FRONTIER_RUNTIME_MUST_BE_FALSE", result["reasons"])

    def test_none_frontier_returns_no_frontier(self):
        frontier = {
            "schema_version": 1,
            "role": "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER",
            "state": "NONE",
        }
        result = self.plan(frontier=frontier)
        self.assertEqual(result["decision"], "NO_FRONTIER")
        self.assertIsNone(result["proposal"])

    def test_generated_marker_round_trips_through_canonical_selector(self):
        result = self.plan()
        selector = planner.load_selector()
        parsed = selector.parse_issue_intake_marker(result["proposal"]["body"])
        self.assertEqual(parsed["work_unit_id"], "PIPE-WU-103")
        self.assertEqual(parsed["state"], "READY")
        self.assertEqual(parsed["base_sha"], BASE)
        self.assertFalse(parsed["runtime_required"])
        self.assertIsNone(parsed["branch"])

    def test_higher_historical_suffix_advances_id(self):
        snap = snapshot()
        snap["issues"].append(issue(300, marker("PIPE-WU-120"), state="closed"))
        result = self.plan(snap)
        self.assertEqual(result["proposal"]["work_unit_id"], "PIPE-WU-121")

    def test_default_head_must_be_exact_sha(self):
        snap = snapshot()
        snap["default_head_sha"] = "bad"
        result = self.plan(snap)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("DEFAULT_HEAD_SHA_INVALID", result["reasons"])


if __name__ == "__main__":
    unittest.main()
