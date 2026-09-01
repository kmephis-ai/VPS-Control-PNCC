import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/foundations/windows-v7/V7-StateSnapshot.ps1'
CONTRACT = ROOT / '.pncc-dev/contracts/product-state-snapshot-contract-wu143.json'
TOPOLOGY_WORKFLOW = ROOT / '.github/workflows/wave5-writer-lease-registry-topology.yml'
WU105_VALIDATOR = ROOT / '.pncc-dev/scripts/check_wu105_provenance_compatibility.py'
CANONICAL_PACKAGE_ROOT = 'src/windows-v7'
CANONICAL_PACKAGE_TREE = 'e1ae13566acb61a084fe612c5b93fb5d6e278fcb'

EXPECTED_ANCHORS = {
    'src/windows-v7/VPS-Control-v7.ps1': '5ec83f2de8be1c468ee3991032e917ea21f5d212',
    'src/windows-v7/modules/V7-StatusCenter.ps1': '2f3f73799c5d70dbfc2f24870a3cd86cf91b0496',
    'src/windows-v7/modules/V7-Observability.ps1': 'ef9c446e4a131610d04a3e884c068e599a548e6c',
    'src/windows-v7/VPS-Control-v7-TUNNEL-CONTRACT.json': 'b77a594f1bc57b5961ab332a6e60b735ef317c3f',
    '.github/workflows/wave6-hbe-periodic-health-drift-wu137.yml': '524ff581fb1c68d25a9c4d3b3ed56cd995fa82f2',
}


def git_blob(path: str) -> str:
    return subprocess.check_output(
        ['git', 'hash-object', path], cwd=ROOT, text=True
    ).strip()


def git_tree(path: str) -> str:
    return subprocess.check_output(
        ['git', 'rev-parse', f'HEAD:{path}'], cwd=ROOT, text=True
    ).strip()


class ProductStateSnapshotContractWU143Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
        cls.source_bytes = SOURCE.read_bytes()
        cls.source = cls.source_bytes.decode('utf-8-sig')
        cls.source_lower = cls.source.lower()
        cls.topology_workflow = TOPOLOGY_WORKFLOW.read_text(encoding='utf-8')

    def test_identity_source_and_powershell_compatibility_are_exact(self):
        c = self.contract
        self.assertEqual(c['schema_version'], 1)
        self.assertEqual(c['role'], 'PNCC_PRODUCT_STATE_SNAPSHOT_CONTRACT_FOUNDATION')
        self.assertEqual(c['work_unit_id'], 'PIPE-WU-143')
        self.assertEqual(c['issue_number'], 331)
        self.assertEqual(c['authorized_base_sha'], '2db7048707ec4abcca660cdcf1659a49c9a9fe08')
        self.assertFalse(c['runtime_required'])
        self.assertEqual(c['integration_state'], 'FOUNDATION_NOT_WIRED_OUTSIDE_CANONICAL_PACKAGE_NO_RUNTIME_CHANGE')
        self.assertEqual(c['source']['path'], SOURCE.relative_to(ROOT).as_posix())
        self.assertEqual(c['source']['entrypoint'], 'New-V7StateSnapshotContract')
        self.assertEqual(c['source']['powershell_minimum'], '5.1')
        self.assertEqual(c['source']['blob_sha'], git_blob(str(SOURCE.relative_to(ROOT))))
        self.assertTrue(self.source_bytes.startswith(b'\xef\xbb\xbf'))
        self.assertTrue(self.source.startswith('#requires -Version 5.1'))

    def test_foundation_is_deliberately_outside_current_candidate_package(self):
        boundary = self.contract['packaging_boundary']
        self.assertEqual(boundary['canonical_package_source_root'], CANONICAL_PACKAGE_ROOT)
        self.assertEqual(boundary['authorized_base_tree_sha'], CANONICAL_PACKAGE_TREE)
        self.assertEqual(git_tree(CANONICAL_PACKAGE_ROOT), CANONICAL_PACKAGE_TREE)
        self.assertEqual(boundary['foundation_source_root'], 'src/foundations/windows-v7')
        self.assertFalse(boundary['foundation_in_current_candidate_package'])
        self.assertFalse(boundary['candidate_source_declaration_modified'])
        self.assertFalse(boundary['candidate_provenance_modified'])
        self.assertFalse(boundary['candidate_manifest_modified'])
        self.assertFalse(boundary['candidate_version_modified'])
        self.assertFalse(boundary['release_or_promotion_authority_claimed'])
        self.assertTrue(SOURCE.relative_to(ROOT).as_posix().startswith(boundary['foundation_source_root'] + '/'))
        self.assertFalse(SOURCE.relative_to(ROOT).as_posix().startswith(CANONICAL_PACKAGE_ROOT + '/'))

    def test_contract_is_read_only_and_contains_no_external_mutation_primitives(self):
        c = self.contract['contract']
        self.assertTrue(c['read_only'])
        self.assertFalse(c['secrets_included'])
        self.assertTrue(c['inputs_are_preobserved'])
        for key in (
            'performs_network_probe', 'performs_process_control', 'performs_persistence',
            'performs_routing_mutation', 'performs_tunnel_lifecycle_action',
        ):
            self.assertFalse(c[key], key)

        forbidden_source_tokens = (
            'start-process', 'stop-process', 'set-content', 'add-content', 'out-file',
            'write-textatomic', 'invoke-webrequest', 'invoke-restmethod', 'new-netfirewall',
            'set-netfirewall', 'remove-netfirewall', 'set-itemproperty', 'remove-itemproperty',
            'start-v7', 'stop-v7', 'ensure-sockstunnel', 'applyroutingchange',
        )
        for token in forbidden_source_tokens:
            self.assertNotIn(token, self.source_lower, token)

    def test_structured_state_schema_is_explicit(self):
        c = self.contract['contract']
        self.assertEqual(c['name'], 'PNCC_STATE_SNAPSHOT')
        self.assertEqual(c['schema_version'], 1)
        self.assertEqual(
            c['top_level_fields'],
            [
                'SchemaVersion', 'Contract', 'CapturedAt', 'ReadOnly', 'SecretsIncluded',
                'Overall', 'RuntimeEvidence', 'RoutingTunnelId', 'Tunnels', 'Modules',
                'Watchdog', 'Proxifier', 'LastKnownGood',
            ],
        )
        self.assertEqual(
            c['module_fields'],
            ['Id', 'Desired', 'Configured', 'Observed', 'Effective', 'Reason', 'Health', 'LatencyMs', 'FailureClass'],
        )
        for field in c['top_level_fields'] + c['module_fields']:
            self.assertIn(field, self.source)

    def test_observed_and_reason_are_not_synthesized_when_runtime_does_not_expose_them(self):
        semantics = self.contract['contract']['transition_semantics']
        self.assertIn('ELSE_NULL', semantics['Observed'])
        self.assertIn('ELSE_NULL', semantics['Reason'])
        self.assertIn("@('Observed','ObservedState')", self.source)
        self.assertIn("@('Reason','DecisionReason','LastReason')", self.source)
        self.assertIn('return $null', self.source)
        self.assertNotIn("Observed = $health", self.source)
        self.assertNotIn("Reason = $failureClass", self.source)

    def test_collection_shapes_are_stable_for_zero_one_or_many_modules(self):
        shape = self.contract['contract']['collection_shape']
        self.assertEqual(shape['Modules'], 'ALWAYS_ARRAY_ZERO_ONE_OR_MANY')
        self.assertEqual(shape['Tunnels'], 'ALWAYS_ARRAY_EXACTLY_TWO_IN_CURRENT_DUAL_TUNNEL_CONTRACT')
        self.assertIn('[string[]]$ModuleNames = @()', self.source)
        self.assertIn('Modules = @($moduleRows)', self.source)
        self.assertIn('Tunnels = @($primaryTunnel, $reserveTunnel)', self.source)
        self.assertIn('if ([string]::IsNullOrWhiteSpace([string]$module)) { continue }', self.source)

    def test_dual_tunnel_lifecycle_contract_is_preserved(self):
        tunnels = {row['id']: row for row in self.contract['tunnel_invariants']}
        self.assertEqual(tunnels['PRIMARY_AUTO']['port'], 1081)
        self.assertEqual(tunnels['PRIMARY_AUTO']['lifecycle'], 'AUTO')
        self.assertTrue(tunnels['PRIMARY_AUTO']['automation_may_manage_lifecycle'])
        self.assertEqual(tunnels['RESERVE_MANUAL']['port'], 1080)
        self.assertEqual(tunnels['RESERVE_MANUAL']['lifecycle'], 'MANUAL_ONLY')
        self.assertFalse(tunnels['RESERVE_MANUAL']['automation_may_manage_lifecycle'])
        self.assertIn("Id = 'PRIMARY_AUTO'", self.source)
        self.assertIn('Port = 1081', self.source)
        self.assertIn("Id = 'RESERVE_MANUAL'", self.source)
        self.assertIn('Port = 1080', self.source)
        self.assertIn("Lifecycle = 'MANUAL_ONLY'", self.source)
        self.assertIn('AutomationMayManageLifecycle = $false', self.source)

    def test_existing_product_and_wu137_anchors_are_byte_preserved(self):
        self.assertEqual(self.contract['byte_preserved_existing_product_anchors'], EXPECTED_ANCHORS)
        for path, expected in EXPECTED_ANCHORS.items():
            self.assertEqual(git_blob(path), expected, path)
        self.assertEqual(
            self.contract['stable_routing_baseline_sha256'],
            '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e',
        )

    def test_historical_wu105_provenance_guard_is_branch_gated_without_weakening_global_topology_checks(self):
        repair = self.contract['ci_harness_repair']
        self.assertEqual(repair['classification'], 'HARNESS_OR_VALIDATION_DEFECT')
        self.assertEqual(repair['pre_repair_workflow_blob_sha'], 'd031588f5f9a675c5e3dde03bf327e229f2aa1a8')
        self.assertEqual(repair['post_repair_workflow_blob_sha'], git_blob(str(TOPOLOGY_WORKFLOW.relative_to(ROOT))))
        self.assertEqual(repair['validator_blob_sha'], 'bd597373ac25d932b772316540d5bdc57d41bf7f')
        self.assertEqual(git_blob(str(WU105_VALIDATOR.relative_to(ROOT))), repair['validator_blob_sha'])
        self.assertFalse(repair['validator_modified'])
        self.assertTrue(repair['guard_branch_gated'])
        self.assertTrue(repair['workflow_permissions_unchanged'])
        self.assertFalse(repair['product_runtime_semantics_changed'])
        self.assertFalse(repair['ruleset_or_security_policy_changed'])

        exact_condition = "if: github.event_name == 'pull_request' && github.head_ref == 'agent/PIPE-WU-105-adwf-consumer-provenance-reconciliation'"
        self.assertIn(exact_condition, self.topology_workflow)
        self.assertIn('python3 .pncc-dev/scripts/check_wu105_provenance_compatibility.py', self.topology_workflow)
        self.assertIn('permissions:\n  contents: read', self.topology_workflow)
        self.assertNotIn('contents: write', self.topology_workflow)
        for marker in (
            'Validate topology policy',
            'Run adversarial registry topology tests',
            'Preserve durable Writer Lease v1 validation',
            'Assert no live provider-state bootstrap or mutation exists',
            'Assert repository remains clean',
            'Run WU143 terminal WU105 guard regression when present',
        ):
            self.assertIn(marker, self.topology_workflow)

    def test_forbidden_scope_and_mutation_report_fail_closed(self):
        forbidden = self.contract['forbidden_mutations']
        self.assertTrue(forbidden)
        self.assertTrue(all(forbidden.values()))
        report = self.contract['mutation_report']
        self.assertTrue(report['ci_harness_modified'])
        for key, value in report.items():
            if key == 'ci_harness_modified':
                continue
            self.assertIs(value, False, key)
        self.assertEqual(
            self.contract['next_boundary'],
            'SEPARATE_OWNER_GOVERNED_INTEGRATION_INTO_WINFORMS_CLI_OR_API_CLIENT',
        )


if __name__ == '__main__':
    unittest.main()
