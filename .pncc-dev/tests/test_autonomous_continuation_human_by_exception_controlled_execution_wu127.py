#!/usr/bin/env python3
from __future__ import annotations
import copy, importlib.util, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'.pncc-dev/scripts/validate_autonomous_continuation_human_by_exception_controlled_execution_wu127.py'
EVIDENCE=ROOT/'.pncc-dev/contracts/autonomous-continuation-human-by-exception-controlled-execution-wu127.json'
spec=importlib.util.spec_from_file_location('wu127_validator',SCRIPT)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class Wu127ControlledExecutionTests(unittest.TestCase):
    def setUp(self):
        self.e=json.loads(EVIDENCE.read_text())
        self.r={"schema_version":1,"role":"WRITER_LEASE_REGISTRY","generation":35,"entries":[{
          "schema_version":1,"role":"WRITER_LEASE","lease_id":"b7d7e6b9-13fd-4cd6-a122-0c7b352e0cb5",
          "work_unit_id":"PIPE-WU-127","conflict_domain":"wave5-autonomous-continuation-human-by-exception-operationalization-execution-existing-authority-only",
          "holder":"chatgpt-wave5-writer","base_sha":"0e2506e64645192236e95caad253104507c26591",
          "branch":"agent/PIPE-WU-127-controlled-human-by-exception-execution-existing-authority-only",
          "state":"ACTIVE","generation":35,"acquired_at":"2026-08-30T20:01:53Z","heartbeat_at":"2026-08-30T20:01:53Z","expires_at":"2026-08-30T21:01:53Z"}]}
    def ok(self,e=None,r=None):
        return mod.validate(e or self.e,r or self.r,check_anchors=False)
    def blocked(self,mutator):
        e=copy.deepcopy(self.e); mutator(e)
        with self.assertRaises(mod.EvidenceError): self.ok(e=e)
    def test_canonical_evidence_validates(self):
        out=self.ok(); self.assertEqual(out['status'],'VALID'); self.assertEqual(out['transaction_count'],1)
    def test_second_transaction_forbidden(self):
        self.blocked(lambda e:e.__setitem__('second_controlled_transaction_performed',True))
    def test_transaction_limit_cannot_expand(self):
        self.blocked(lambda e:e['controlled_transaction'].__setitem__('transaction_count',2))
    def test_operationalizer_cannot_gain_mutation_authority(self):
        self.blocked(lambda e:e['controlled_transaction'].__setitem__('operationalizer_mutation_authority',True))
    def test_operationalization_outcome_must_remain_existing_authority_only(self):
        self.blocked(lambda e:e['controlled_transaction'].__setitem__('operationalization_outcome','HIGHER_AUTONOMY'))
    def test_provider_state_must_not_change_for_branch_create(self):
        self.blocked(lambda e:e['controlled_transaction']['provider_state_after'].__setitem__('state_branch_head_sha','1'*40))
    def test_owner_escalation_cannot_mutate(self):
        self.blocked(lambda e:e['boundary_validation']['OWNER_ESCALATION_REQUIRED'].__setitem__('mutation_permitted',True))
    def test_wait_cannot_replay(self):
        self.blocked(lambda e:e['boundary_validation']['WAIT_ONLY'].__setitem__('automatic_replay_permitted',True))
    def test_higher_autonomy_forbidden(self):
        self.blocked(lambda e:e.__setitem__('higher_autonomy_authorized',True))
    def test_inferred_authority_forbidden(self):
        self.blocked(lambda e:e.__setitem__('inferred_or_fallback_authority_used',True))
    def test_registry_generation_drift_blocks(self):
        r=copy.deepcopy(self.r); r['generation']=36
        with self.assertRaises(mod.EvidenceError): self.ok(r=r)
    def test_second_active_lease_blocks(self):
        r=copy.deepcopy(self.r); y=copy.deepcopy(r['entries'][0]); y['lease_id']='00000000-0000-0000-0000-000000000000'; y['work_unit_id']='PIPE-WU-999'; r['entries'].append(y)
        with self.assertRaises(mod.EvidenceError): self.ok(r=r)

if __name__=='__main__': unittest.main()
