import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.pncc-dev/scripts/validate_reusable_autonomous_merge_close_authority_preparation.py'
CONTRACT = ROOT / '.pncc-dev/contracts/reusable-autonomous-merge-close-authority-preparation.json'
spec = importlib.util.spec_from_file_location('wu100_validate', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Wu100PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding='utf-8'))

    def validate_no_git(self, c):
        return mod.validate(c, ROOT, check_git_blob=False)

    def test_exact_preparation_contract_is_valid_without_git_probe(self):
        self.assertEqual(self.validate_no_git(copy.deepcopy(self.contract)), [])

    def test_owner_authorization_must_not_be_pregranted(self):
        c = copy.deepcopy(self.contract); c['owner_authorization_present'] = True
        self.assertIn('owner_authorization_present must remain false', self.validate_no_git(c))

    def test_reusable_merge_authority_must_remain_false(self):
        c = copy.deepcopy(self.contract); c['reusable_autonomous_merge_authority'] = True
        self.assertTrue(any('reusable_autonomous_merge_authority' in e for e in self.validate_no_git(c)))

    def test_reusable_close_authority_must_remain_false(self):
        c = copy.deepcopy(self.contract); c['reusable_autonomous_issue_close_authority'] = True
        self.assertTrue(any('reusable_autonomous_issue_close_authority' in e for e in self.validate_no_git(c)))

    def test_direct_main_write_never_prepared(self):
        c = copy.deepcopy(self.contract); c['direct_main_write_authority'] = True
        self.assertTrue(any('direct_main_write_authority' in e for e in self.validate_no_git(c)))

    def test_runtime_required_false_guard_is_mandatory(self):
        c = copy.deepcopy(self.contract); c['per_transaction_runtime_required_must_be_false'] = False
        self.assertTrue(any('per_transaction_runtime_required_must_be_false' in e for e in self.validate_no_git(c)))

    def test_full_current_head_ci_is_mandatory(self):
        c = copy.deepcopy(self.contract); c['per_transaction_current_head_full_ci_success_required'] = False
        self.assertTrue(any('per_transaction_current_head_full_ci_success_required' in e for e in self.validate_no_git(c)))

    def test_released_lease_is_mandatory(self):
        c = copy.deepcopy(self.contract); c['per_transaction_exact_released_writer_lease_required'] = False
        self.assertTrue(any('per_transaction_exact_released_writer_lease_required' in e for e in self.validate_no_git(c)))

    def test_provider_state_drift_guard_is_mandatory(self):
        c = copy.deepcopy(self.contract); c['per_transaction_no_provider_state_drift_after_release_required'] = False
        self.assertTrue(any('per_transaction_no_provider_state_drift_after_release_required' in e for e in self.validate_no_git(c)))

    def test_merge_eligibility_decision_is_mandatory(self):
        c = copy.deepcopy(self.contract); c['per_transaction_merge_eligible_decision_required'] = False
        self.assertTrue(any('per_transaction_merge_eligible_decision_required' in e for e in self.validate_no_git(c)))

    def test_close_eligibility_decision_is_mandatory(self):
        c = copy.deepcopy(self.contract); c['per_transaction_close_eligible_decision_required'] = False
        self.assertTrue(any('per_transaction_close_eligible_decision_required' in e for e in self.validate_no_git(c)))

    def test_unrelated_pr_issue_mutation_must_remain_forbidden(self):
        c = copy.deepcopy(self.contract); c['unrelated_pr_or_issue_mutation_forbidden'] = False
        self.assertTrue(any('unrelated_pr_or_issue_mutation_forbidden' in e for e in self.validate_no_git(c)))

    def test_policy_anchor_drift_blocks(self):
        c = copy.deepcopy(self.contract); c['eligibility_policy_blob_sha'] = '0' * 40
        self.assertTrue(any('eligibility_policy_blob_sha' in e for e in self.validate_no_git(c)))

    def test_scope_cannot_broaden(self):
        c = copy.deepcopy(self.contract); c['future_scope'] = 'UNBOUNDED_AUTONOMY'
        self.assertTrue(any('future_scope' in e for e in self.validate_no_git(c)))


if __name__ == '__main__':
    unittest.main()
