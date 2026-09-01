import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "evaluate_wave6_wu137_redundant_observer_wu144.py"
)
SPEC = importlib.util.spec_from_file_location("wu144_eval", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


def z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def payload(observed, runs):
    return {"observed_at": z(observed), "workflow_runs": runs}


def run(run_id, created, conclusion="success", status="completed", event="schedule"):
    return {
        "id": run_id,
        "event": event,
        "status": status,
        "conclusion": conclusion,
        "created_at": z(created),
        "head_sha": "a" * 40,
    }


class WU144EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.base = datetime(2026, 9, 1, 0, 17, tzinfo=timezone.utc)

    def evaluate_for(self, flags, observed=None):
        if observed is None:
            observed = self.base + timedelta(hours=len(flags) - 1, minutes=50)
        runs = []
        for index, healthy in enumerate(flags):
            if healthy:
                nominal = self.base + timedelta(hours=index)
                runs.append(run(1000 + index, nominal + timedelta(minutes=20)))
        return MOD.evaluate(payload(observed, runs))

    def test_exact_45_minute_boundary_qualifies(self):
        observed = self.base + timedelta(minutes=46)
        result = MOD.evaluate(
            payload(observed, [run(1, self.base + timedelta(minutes=45))])
        )
        self.assertEqual(result["state"], "RECOVERED_SINGLE")
        self.assertTrue(result["opportunities"][-1]["healthy_delivered"])

    def test_after_45_minute_boundary_does_not_qualify(self):
        observed = self.base + timedelta(hours=1, minutes=46)
        result = MOD.evaluate(
            payload(observed, [run(1, self.base + timedelta(minutes=46))])
        )
        first = [x for x in result["opportunities"] if x["nominal_at"] == z(self.base)][0]
        self.assertFalse(first["healthy_delivered"])
        self.assertIn(1, result["ignored_run_ids"])

    def test_before_nominal_does_not_qualify(self):
        observed = self.base + timedelta(minutes=46)
        result = MOD.evaluate(
            payload(observed, [run(1, self.base - timedelta(seconds=1))])
        )
        self.assertFalse(result["opportunities"][-1]["healthy_delivered"])
        self.assertIn(1, result["ignored_run_ids"])

    def test_four_consecutive_healthy_is_stable(self):
        result = self.evaluate_for([True, True, True, True])
        self.assertEqual(result["state"], "STABLE_DELIVERY_OBSERVED")
        self.assertEqual(result["consecutive_healthy"], 4)

    def test_three_consecutive_misses_is_review_eligible(self):
        result = self.evaluate_for([True, True, True, False, False, False])
        self.assertEqual(result["state"], "REMEDIATION_REVIEW_ELIGIBLE")
        self.assertTrue(result["consecutive_miss_trigger"])

    def test_two_of_six_triggers_rolling_ratio(self):
        result = self.evaluate_for([True, False, True, False, False, False])
        self.assertEqual(result["state"], "REMEDIATION_REVIEW_ELIGIBLE")
        self.assertTrue(result["rolling_ratio_trigger"])
        self.assertAlmostEqual(result["rolling_delivered_ratio"], 2 / 6)

    def test_three_of_six_ratio_boundary_does_not_trigger_ratio(self):
        result = self.evaluate_for([True, False, True, False, True, False])
        self.assertFalse(result["rolling_ratio_trigger"])
        self.assertEqual(result["state"], "RECOVERED_INTERMITTENT")

    def test_duplicate_healthy_runs_count_one_opportunity(self):
        observed = self.base + timedelta(minutes=50)
        result = MOD.evaluate(
            payload(
                observed,
                [
                    run(1, self.base + timedelta(minutes=10)),
                    run(2, self.base + timedelta(minutes=20)),
                ],
            )
        )
        self.assertEqual(result["healthy_delivered_opportunities"], 1)
        self.assertEqual(result["opportunities"][-1]["duplicate_healthy_run_count"], 1)

    def test_terminal_failure_has_priority(self):
        observed = self.base + timedelta(minutes=50)
        result = MOD.evaluate(
            payload(observed, [run(1, self.base + timedelta(minutes=10), "failure")])
        )
        self.assertEqual(result["state"], "WU137_EXECUTION_UNHEALTHY_OBSERVED")
        self.assertEqual(result["unhealthy_run_ids"], [1])
        self.assertFalse(result["mutation_authority"])

    def test_nonterminal_run_has_priority(self):
        observed = self.base + timedelta(minutes=50)
        result = MOD.evaluate(
            payload(
                observed,
                [run(1, self.base + timedelta(minutes=10), None, "in_progress")],
            )
        )
        self.assertEqual(result["state"], "WU137_EXECUTION_NONTERMINAL_OBSERVED")
        self.assertEqual(result["nonterminal_run_ids"], [1])

    def test_non_schedule_event_fails_closed(self):
        observed = self.base + timedelta(minutes=50)
        with self.assertRaises(MOD.ProviderDataError):
            MOD.evaluate(
                payload(
                    observed,
                    [run(1, self.base + timedelta(minutes=10), event="pull_request")],
                )
            )

    def test_duplicate_run_id_fails_closed(self):
        observed = self.base + timedelta(minutes=50)
        r = run(1, self.base + timedelta(minutes=10))
        with self.assertRaises(MOD.ProviderDataError):
            MOD.evaluate(payload(observed, [r, dict(r)]))

    def test_future_provider_timestamp_fails_closed(self):
        observed = self.base + timedelta(minutes=50)
        with self.assertRaises(MOD.ProviderDataError):
            MOD.evaluate(payload(observed, [run(1, observed + timedelta(seconds=1))]))

    def test_malformed_provider_timestamp_fails_closed(self):
        observed = self.base + timedelta(minutes=50)
        bad = run(1, self.base + timedelta(minutes=10))
        bad["created_at"] = "not-a-timestamp"
        with self.assertRaises(MOD.ProviderDataError):
            MOD.evaluate(payload(observed, [bad]))

    def test_unsorted_runs_are_deterministic(self):
        observed = self.base + timedelta(hours=1, minutes=50)
        runs = [
            run(2, self.base + timedelta(hours=1, minutes=10)),
            run(1, self.base + timedelta(minutes=10)),
        ]
        a = MOD.evaluate(payload(observed, runs))
        b = MOD.evaluate(payload(observed, list(reversed(runs))))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
