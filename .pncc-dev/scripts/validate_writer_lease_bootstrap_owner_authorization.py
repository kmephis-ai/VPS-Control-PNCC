#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
a=json.loads((ROOT/'.pncc-dev/attestations/writer-lease-bootstrap-owner-authorization-wu096.json').read_text(encoding='utf-8'))
expected={
 'schema_version':1,
 'role':'WRITER_LEASE_BOOTSTRAP_OWNER_AUTHORIZATION',
 'work_unit_id':'PIPE-WU-096',
 'preparation_main':'2391b0d114ca2967f59bd701d9e181c5dfd8aad7',
 'prepared_contract_blob_sha':'5eb95085218cbe0bdaf9b678426fe3ecff327c27',
 'authorization_scope':'PROVIDER_STATE_BOOTSTRAP_AND_FIRST_WRITER_LEASE_ACQUISITION_ONLY',
 'state_branch':'pncc-provider-state',
 'registry_path':'.pncc-state/writer-lease-registry.json',
 'initial_registry_sha256':'a4d6f7946290c0a9d775b5b3d27676f09162b3085ad9d9301dc82af8a1276b11',
 'initial_registry_size':80,
 'authorization_state':'AUTHORIZED_PENDING_EXECUTION',
}
for k,v in expected.items():
    assert a.get(k)==v,(k,a.get(k),v)
for k in ('bootstrap_create_once_authorized','initial_registry_create_authorized','first_cas_bound_writer_lease_acquisition_authorized','fresh_provider_read_required','claim_eligible_required'):
    assert a.get(k) is True,k
for k in ('force_or_move_existing_branch_authorized','overwrite_existing_branch_authorized','silent_lease_steal_authorized','subsequent_lease_heartbeat_authorized','subsequent_lease_release_authorized','product_runtime_mutation_authorized','adwf_binding_mutation_authorized','release_tag_promotion_authorized','ruleset_policy_mutation_authorized','private_evidence_publication_authorized','reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized'):
    assert a.get(k) is False,k
print('WU096_OWNER_AUTHORIZATION=PASS')
