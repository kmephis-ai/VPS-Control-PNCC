#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / ".pncc-dev/contracts/exact-head-ci-inspection-classification-policy.json"
EVALUATOR = ROOT / ".pncc-dev/scripts/evaluate_exact_head_ci_inspection_classification.py"

spec = importlib.util.spec_from_file_location("wu107_ci", EVALUATOR)
ci = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ci)


def run(name, status="completed", conclusion="success", *, head="2"*40, attribution=None, run_id=1):
    return {
        "id": run_id,
        "name": name,
        "head_sha": head,
        "status": status,
        "conclusion": conclusion,
        "failure_attribution": attribution,
    }


def snapshot(runs, *, head="2"*40, observed=None, fresh=True, complete=True, effective=True, superseded=True):
    return {
        "schema_version": 1,
        "role": "EXACT_HEAD_CI_PROVIDER_SNAPSHOT",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "provider_truth_fresh": fresh,
        "inventory_complete": complete,
        "effective_inventory": effective,
        "superseded_runs_accounted_for": superseded,
        "pr_number": 262,
        "pr_base_sha": "1"*40,
        "pr_head_sha": head,
        "observed_pr_head_sha": observed or head,
        "workflow_runs": runs,
    }


def required_success(head="2"*40):
    names = [
        "pipeline-state",
        "wave5-provider-work-unit-selection",
        "public-safety",
        "quality-fast",
        "quality-deep",
    ]
    return [run(name, head=head, run_id=i+1) for i, name in enumerate(names)]


class ExactHeadCiInspectionClassificationWu107Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        ci.validate_policy(cls.policy)

    def evaluate(self, snap):
        return ci.evaluate_exact_head_ci(snap, policy=self.policy, check_anchors=False)

    def test_policy_anchors_are_exact_and_authorities_default_deny(self):
        ci.validate_anchor_map(self.policy)
        for key in ci.FALSE_AUTHORITIES:
            self.assertIs(self.policy[key], False, key)

    def test_all_success(self):
        result = self.evaluate(snapshot(required_success()))
        self.assertEqual(result["decision"], "CI_SUCCESS")
        self.assertEqual(result["pending_workflows"], [])
        self.assertEqual(result["failed_workflows"], [])
        self.assertFalse(result["provider_mutation_performed"])
        self.assertFalse(result["merge_performed"])

    def test_pending_wins_without_failure_recovery(self):
        runs = required_success()
        runs[3] = run("quality-fast", status="in_progress", conclusion=None, run_id=4)
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "CI_PENDING")
        self.assertEqual(result["pending_workflows"], ["quality-fast"])

    def test_explicit_harness_attribution(self):
        runs = required_success()
        runs[3] = run(
            "quality-fast",
            conclusion="failure",
            run_id=4,
            attribution={
                "classification": "HARNESS_OR_VALIDATION_DEFECT",
                "source": "HOSTED_CI_JOB_STEP_LOG_OR_MACHINE_EVIDENCE",
                "evidence": ["validator traceback attributes failure to test harness input normalization"],
                "harness_or_validation_surface_implicated": True,
                "product_runtime_surface_implicated": False,
            },
        )
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "HARNESS_OR_VALIDATION_DEFECT_CANDIDATE")

    def test_explicit_product_runtime_candidate_attribution(self):
        runs = required_success()
        runs[4] = run(
            "quality-deep",
            conclusion="failure",
            run_id=5,
            attribution={
                "classification": "PRODUCT_RUNTIME_DEFECT_CANDIDATE",
                "source": "HOSTED_CI_JOB_STEP_LOG_OR_MACHINE_EVIDENCE",
                "evidence": ["machine evidence identifies product/runtime source behavior under the failing contract"],
                "harness_or_validation_surface_implicated": False,
                "product_runtime_surface_implicated": True,
            },
        )
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "PRODUCT_RUNTIME_DEFECT_CANDIDATE")

    def test_missing_attribution_is_ambiguity_not_product_guess(self):
        runs = required_success()
        runs[4] = run("quality-deep", conclusion="failure", run_id=5)
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "PROVIDER_ENVIRONMENT_AMBIGUITY")

    def test_workflow_name_never_implies_product_defect(self):
        runs = required_success()
        runs.append(run("product-runtime-super-scary-name", conclusion="failure", run_id=6))
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "PROVIDER_ENVIRONMENT_AMBIGUITY")

    def test_mixed_harness_and_product_attribution_is_ambiguity(self):
        runs = required_success()
        runs[3] = run(
            "quality-fast",
            conclusion="failure",
            run_id=4,
            attribution={
                "classification": "HARNESS_OR_VALIDATION_DEFECT",
                "source": "HOSTED_CI_JOB_STEP_LOG_OR_MACHINE_EVIDENCE",
                "evidence": ["harness evidence"],
                "harness_or_validation_surface_implicated": True,
                "product_runtime_surface_implicated": False,
            },
        )
        runs[4] = run(
            "quality-deep",
            conclusion="failure",
            run_id=5,
            attribution={
                "classification": "PRODUCT_RUNTIME_DEFECT_CANDIDATE",
                "source": "HOSTED_CI_JOB_STEP_LOG_OR_MACHINE_EVIDENCE",
                "evidence": ["product candidate evidence"],
                "harness_or_validation_surface_implicated": False,
                "product_runtime_surface_implicated": True,
            },
        )
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "PROVIDER_ENVIRONMENT_AMBIGUITY")

    def test_head_drift_blocks(self):
        result = self.evaluate(snapshot(required_success(), observed="3"*40))
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("PR_HEAD_DRIFT", result["reasons"])

    def test_incomplete_inventory_blocks(self):
        result = self.evaluate(snapshot(required_success(), complete=False))
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("CI_INVENTORY_INCOMPLETE", result["reasons"])

    def test_missing_required_workflow_blocks(self):
        runs = required_success()[:-1]
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertTrue(any(x.startswith("REQUIRED_WORKFLOW_MISSING:") for x in result["reasons"]))

    def test_duplicate_effective_workflow_name_blocks(self):
        runs = required_success()
        runs.append(run("quality-fast", run_id=99))
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("DUPLICATE_EFFECTIVE_WORKFLOW_NAME:quality-fast", result["reasons"])

    def test_unknown_status_blocks(self):
        runs = required_success()
        runs[0] = run("pipeline-state", status="mystery", conclusion=None, run_id=1)
        result = self.evaluate(snapshot(runs))
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("WORKFLOW_STATUS_UNKNOWN:pipeline-state", result["reasons"])


if __name__ == "__main__":
    unittest.main()
