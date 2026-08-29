from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[2]
RECEIPT=ROOT/'.pncc-dev/attestations/writer-lease-bounded-branch-execution-wu098.json'
AUTH=ROOT/'.pncc-dev/contracts/writer-lease-lifecycle-branch-execution-authorized.json'

class BoundedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.r=json.loads(RECEIPT.read_text(encoding='utf-8'))
        self.a=json.loads(AUTH.read_text(encoding='utf-8'))

    def test_exact_authorization_binding(self):
        self.assertEqual(self.r['work_unit_id'],'PIPE-WU-098')
        self.assertEqual(self.r['authorization_scope'],self.a['authorization_scope'])
        self.assertEqual(self.r['authorization_main_sha'],'05e9cfd022f76da3155229b149992811d756679d')
        self.assertEqual(self.r['authorization_contract_blob_sha'],'95e9f1ff1548221fca31ebba9c6e8d3432e9345d')
        self.assertIs(self.a['owner_authorization_present'],True)
        self.assertIs(self.a['owner_authorization_binding_complete'],True)

    def test_selection_and_claim_are_exact(self):
        self.assertEqual(self.r['selection_disposition'],'EXECUTABLE')
        self.assertEqual(self.r['selection_classification'],'EXECUTABLE_READ_ONLY_SELECTION')
        self.assertEqual(self.r['claim_decision'],'CLAIM_ELIGIBLE')
        self.assertEqual(self.r['selected_base_sha'],self.r['authorization_main_sha'])

    def test_lease_binding(self):
        self.assertEqual(self.r['lease_id'],'286acee0-6ec0-4246-95b2-0ed0d450db86')
        self.assertEqual(self.r['lease_generation'],2)
        self.assertEqual(self.r['conflict_domain'],'wave5-writer-lease-lifecycle-authority-preparation')
        self.assertEqual(self.r['holder'],'chatgpt-wave5-writer')
        self.assertEqual(self.r['execution_branch'],'agent/PIPE-WU-098-bounded-execution')
        self.assertNotEqual(self.r['execution_branch'],'main')
        self.assertEqual(self.r['provider_state_head_at_acquisition'],'6a6e03883b9f0cb69b833aaa0e8cf8aebcf8404a')
        self.assertEqual(self.r['registry_blob_sha_at_acquisition'],'de87911025431de15d000141a2939cf14ea200f7')
        self.assertEqual(self.r['registry_payload_sha256_at_acquisition'],'e388bf0850f2263b039f5f96fd4486ffe0219436e97295acc5866f2512d4a702')

    def test_forbidden_operations_remain_false(self):
        for k in ['direct_main_write_performed','autonomous_merge_performed','autonomous_issue_close_performed','runtime_action_performed','adwf_binding_mutation_performed','release_tag_promotion_performed','ruleset_policy_mutation_performed','private_evidence_publication_performed','reserve_1080_lifecycle_mutation_performed','primary_1081_lifecycle_mutation_performed']:
            self.assertIs(self.r[k],False,k)
        for k in ['direct_main_write_authority','autonomous_merge_authority','autonomous_issue_close_authority','lease_steal_authority','force_ref_update_authority','runtime_action_authority','adwf_binding_mutation_authority','promotion_release_tag_authority','ruleset_policy_mutation_authority','private_evidence_publication_authority','reserve_1080_lifecycle_mutation_authority','primary_1081_lifecycle_mutation_authority']:
            self.assertIs(self.a[k],False,k)

    def test_pr_boundary_is_open_and_exact(self):
        self.assertEqual(self.r['pr_number'],238)
        self.assertEqual(self.r['pr_base_branch'],'main')
        self.assertEqual(self.r['pr_base_sha'],self.r['authorization_main_sha'])
        self.assertEqual(self.r['pr_head_branch'],self.r['execution_branch'])
        self.assertIs(self.r['pr_head_must_equal_execution_branch'],True)
        self.assertEqual(self.r['execution_state'],'PR_OPEN_CI_PENDING')

if __name__=='__main__': unittest.main()
