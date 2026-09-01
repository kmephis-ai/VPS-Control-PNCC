import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_wave6_cross_workflow_scheduler_correlation_wu146.py"
SPEC = importlib.util.spec_from_file_location("wu146", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)
UTC = timezone.utc

def z(dt): return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
def run(i, dt, status="completed", conclusion="success", event="schedule", sha=None):
    return {"id": i, "event": event, "status": status, "conclusion": conclusion, "created_at": z(dt), "head_sha": sha or MOD.EXPECTED_MAIN}

def base(observed=None):
    observed = observed or datetime(2026,9,1,16,53,tzinfo=UTC)
    return {
        "observed_at": z(observed),
        "main_sha": MOD.EXPECTED_MAIN,
        "wu142_classification": MOD.WU142_CLASSIFICATION,
        "wu137": {"name":"wave6-hbe-periodic-health-drift-wu137","path":MOD.WU137_PATH,"cron_minute":17,"registered_on_default_branch":True,"runs":[run(10, datetime(2026,9,1,13,31,tzinfo=UTC))]},
        "wu144": {"name":"wave6-wu137-redundant-observer-wu144","path":MOD.WU144_PATH,"cron_minute":7,"registered_on_default_branch":True,"runs":[]},
    }

class Tests(unittest.TestCase):
    def test_current_correlation(self):
        r=MOD.evaluate(base()); self.assertEqual(r["state"],"CROSS_WORKFLOW_SCHEDULE_DELIVERY_DEGRADATION_CORRELATED"); self.assertTrue(r["correlation"]["repository_local_cross_workflow_correlation"])
    def test_immature_waits(self):
        r=MOD.evaluate(base(datetime(2026,9,1,16,51,tzinfo=UTC))); self.assertEqual(r["state"],"WAITING_MATURE_OBSERVATION_WINDOW")
    def test_inside_window_contradicts(self):
        p=base(); p["wu144"]["runs"]=[run(20, datetime(2026,9,1,16,30,tzinfo=UTC))]
        with self.assertRaisesRegex(MOD.ProviderDataError,"CONTRADICTED"): MOD.evaluate(p)
    def test_exact_deadline_contradicts(self):
        p=base(); p["wu144"]["runs"]=[run(20, datetime(2026,9,1,16,52,tzinfo=UTC))]
        with self.assertRaises(MOD.ProviderDataError): MOD.evaluate(p)
    def test_late_delivery_does_not_erase_miss(self):
        p=base(datetime(2026,9,1,17,20,tzinfo=UTC)); p["wu144"]["runs"]=[run(20, datetime(2026,9,1,16,53,tzinfo=UTC))]
        r=MOD.evaluate(p); self.assertEqual(r["state"],"CROSS_WORKFLOW_SCHEDULE_DELIVERY_DEGRADATION_CORRELATED"); self.assertEqual(r["evidence"]["wu144_late_run_ids_after_first_deadline"],[20])
    def test_second_matured_miss_proven(self):
        r=MOD.evaluate(base(datetime(2026,9,1,17,53,tzinfo=UTC))); self.assertTrue(r["correlation"]["wu144_second_matured_delivery_miss_proven"]); self.assertEqual(r["evidence"]["wu144_second_window_run_ids"],[])
    def test_second_window_delivery_does_not_erase_first_correlation(self):
        p=base(datetime(2026,9,1,17,53,tzinfo=UTC)); p["wu144"]["runs"]=[run(20,datetime(2026,9,1,17,30,tzinfo=UTC))]
        r=MOD.evaluate(p); self.assertEqual(r["state"],"CROSS_WORKFLOW_SCHEDULE_DELIVERY_DEGRADATION_CORRELATED"); self.assertFalse(r["correlation"]["wu144_second_matured_delivery_miss_proven"]); self.assertEqual(r["evidence"]["wu144_second_window_run_ids"],[20])
    def test_wu137_failure_priority(self):
        p=base(); p["wu137"]["runs"]=[run(10,datetime(2026,9,1,13,31,tzinfo=UTC),conclusion="failure")]
        self.assertEqual(MOD.evaluate(p)["state"],"WU137_EXECUTION_UNHEALTHY_OBSERVED")
    def test_wu137_nonterminal_priority(self):
        p=base(); p["wu137"]["runs"]=[run(10,datetime(2026,9,1,13,31,tzinfo=UTC),status="in_progress",conclusion=None)]
        self.assertEqual(MOD.evaluate(p)["state"],"WU137_EXECUTION_NONTERMINAL_OBSERVED")
    def test_no_wu137_is_insufficient(self):
        p=base(); p["wu137"]["runs"]=[]; self.assertEqual(MOD.evaluate(p)["state"],"INSUFFICIENT_WU137_DELIVERY_EVIDENCE")
    def test_wrong_path_fails(self):
        p=base(); p["wu144"]["path"]="x"; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_wrong_cron_fails(self):
        p=base(); p["wu144"]["cron_minute"]=17; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_not_default_registered_fails(self):
        p=base(); p["wu144"]["registered_on_default_branch"]=False; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_name_collision_fails(self):
        p=base(); p["wu144"]["name"]=p["wu137"]["name"]; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_main_drift_fails(self):
        p=base(); p["main_sha"]="a"*40; self.assertRaisesRegex(MOD.ProviderDataError,"MAIN_SHA_DRIFT",MOD.evaluate,p)
    def test_wu142_drift_fails(self):
        p=base(); p["wu142_classification"]="OTHER"; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_duplicate_run_fails(self):
        p=base(); r=p["wu137"]["runs"][0]; p["wu137"]["runs"]=[r,dict(r)]; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_future_run_fails(self):
        p=base(); p["wu137"]["runs"]=[run(10,datetime(2026,9,1,16,54,tzinfo=UTC))]; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_non_schedule_fails(self):
        p=base(); p["wu137"]["runs"]=[run(10,datetime(2026,9,1,13,31,tzinfo=UTC),event="workflow_dispatch")]; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_bad_sha_fails(self):
        p=base(); p["wu137"]["runs"][0]["head_sha"]="bad"; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_unknown_input_key_fails(self):
        p=base(); p["extra"]=1; self.assertRaises(MOD.ProviderDataError,MOD.evaluate,p)
    def test_authority_all_false(self):
        r=MOD.evaluate(base()); self.assertTrue(r["authority"]); self.assertTrue(all(v is False for v in r["authority"].values()))
    def test_blocked_authority_all_false(self):
        r=MOD.blocked("X"); self.assertTrue(r["authority"]); self.assertTrue(all(v is False for v in r["authority"].values()))
    def test_duplicate_json_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"x.json"; f.write_text('{"a":1,"a":2}',encoding="utf-8")
            self.assertRaises(MOD.ProviderDataError,MOD.load_json,f)

if __name__ == "__main__": unittest.main()
