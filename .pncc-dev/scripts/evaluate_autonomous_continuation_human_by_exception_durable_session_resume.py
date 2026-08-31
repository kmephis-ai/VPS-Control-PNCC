#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

FALSE_AUTHORITY_FIELDS = (
    "provider_mutation_authority","issue_mutation_authority","branch_mutation_authority",
    "pull_request_mutation_authority","writer_lease_mutation_authority","workflow_rerun_authority",
    "merge_authority","runtime_action_authority","product_runtime_mutation_authority",
    "adwf_binding_mutation_authority","adwf_repository_mutation_authority",
    "release_tag_promotion_authority","ruleset_policy_mutation_authority",
    "private_evidence_publication_authority","force_ref_update_authority",
    "silent_lease_steal_authority","reserve_1080_lifecycle_mutation_authority",
    "primary_1081_lifecycle_mutation_authority","authority_granted","higher_autonomy_authorized",
)

def _no_dupes(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise ValueError(f"duplicate JSON key: {k}")
        out[k]=v
    return out

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_no_dupes)

def validate_policy(p):
    assert p["schema_version"] == 1
    assert p["role"] == "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_SESSION_RESUME_POLICY"
    assert p["policy_state"] == "READY"
    assert p["mode"] == "HBE_DURABLE_SESSION_RESUME_EXISTING_AUTHORITY_ONLY"
    b=p["definition_binding"]
    assert b["work_unit_id"]=="PIPE-WU-130" and b["issue_number"]==308
    assert b["base_main_sha"]=="f6f942f40db14eac28b97fa79429f3ad49f1b9ae"
    assert b["runtime_required"] is False
    d=p["definition_provider_truth"]
    assert d["registry_generation"]==39 and d["lease_generation"]==39
    assert d["lease_id"]=="7435a7f5-9dcb-4c87-a803-62e0561f6153"
    assert p["anchors"]["predecessor_hbe_steady_state_execution"]["blob_sha"]=="b644be019b821a7f2de30a05102f1ae8efb8d964"
    assert p["anchors"]["generic_durable_resume_policy"]["blob_sha"]=="4305cd65c2ed7eaf67a6a6df24d3b4bb4d612446"
    assert p["anchors"]["reusable_writer_lease_grant"]["blob_sha"]=="717e1f9081915f40fad2e0620c64245a650ca235"
    assert p["transaction_semantics"]["completed_transaction_replay_forbidden"] is True
    assert p["writer_lease_resume_semantics"]["expired_historical_active_mutation_forbidden"] is True
    assert p["writer_lease_resume_semantics"]["fresh_monotonic_claim_required_when_no_exact_owned_active_unexpired_lease"] is True
    assert p["checkpoint_contract"]["checkpoint_never_grants_mutation_authority"] is True
    for k in FALSE_AUTHORITY_FIELDS:
        assert p[k] is False, k
    return True

def blocked(reason):
    return {
        "decision":"BLOCKED","reason":reason,
        "mutation_performed":False,"mutation_permitted_by_this_policy":False,
        "historical_lease_mutation_performed":False,"transaction_replay_performed":False,
        "authority_granted":False,"higher_autonomy_authorized":False,
    }

def decision(name, reason, delegated=None, next_generation=None):
    out={
        "decision":name,"reason":reason,
        "mutation_performed":False,"mutation_permitted_by_this_policy":False,
        "historical_lease_mutation_performed":False,"transaction_replay_performed":False,
        "authority_granted":False,"higher_autonomy_authorized":False,
    }
    if delegated is not None:
        out["delegated_authority_identity"]=delegated
    if next_generation is not None:
        out["required_minimum_next_generation"]=next_generation
    return out

def evaluate(p, s):
    try:
        validate_policy(p)
    except Exception as e:
        return blocked(f"POLICY_INVALID:{e}")
    if s.get("schema_version") != 1 or s.get("role") != "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_SESSION_CHECKPOINT":
        return blocked("CHECKPOINT_CONTRACT_MISMATCH")
    required=p["checkpoint_contract"]["required_top_level_fields"]
    if any(k not in s for k in required):
        return blocked("CHECKPOINT_REQUIRED_FIELD_MISSING")
    if not all(s.get(k) is True for k in ("provider_truth_fresh","main_fresh","selection_fresh","branch_readback_fresh","pr_ci_readback_fresh_when_applicable")):
        return blocked("FRESH_READBACK_REQUIRED")
    wu=s.get("selected_work_unit") or {}
    if any(k not in wu for k in p["checkpoint_contract"]["selected_work_unit_required_fields"]):
        return blocked("SELECTED_WORK_UNIT_INCOMPLETE")
    if wu.get("marker_state")!="READY" or wu.get("runtime_required") is not False:
        return blocked("WORK_UNIT_NOT_EXECUTABLE_PUBLIC_CONTROL_PLANE")
    if wu.get("base_sha") != s.get("current_main_sha"):
        return blocked("MAIN_SELECTION_BASE_DRIFT")
    branch=s.get("branch_state") or {}
    if any(k not in branch for k in p["checkpoint_contract"]["branch_state_required_fields"]):
        return blocked("BRANCH_STATE_INCOMPLETE")
    if branch.get("present") is not True or branch.get("name") != s.get("expected_branch"):
        return blocked("BOUNDED_BRANCH_MISSING_OR_MISMATCH")
    if branch.get("base_sha") != wu.get("base_sha"):
        return blocked("BRANCH_BASE_DRIFT")
    ps=s.get("provider_state") or {}
    if any(k not in ps for k in p["checkpoint_contract"]["provider_state_required_fields"]):
        return blocked("PROVIDER_STATE_INCOMPLETE")
    if not isinstance(ps.get("registry_generation"), int) or ps["registry_generation"] < p["definition_provider_truth"]["registry_generation"]:
        return blocked("REGISTRY_GENERATION_STALE")
    if s.get("historical_lease_rewrite_requested") is True:
        return blocked("HISTORICAL_LEASE_REWRITE_FORBIDDEN")
    hbe=s.get("hbe_boundary")
    mapping=p["hbe_boundaries"]
    if hbe not in mapping:
        return blocked("UNKNOWN_HBE_BOUNDARY")
    if hbe=="OWNER_ESCALATION_REQUIRED":
        return decision("OWNER_ESCALATION_REQUIRED","OWNER_EXCEPTION_NO_MUTATION")
    if hbe=="WAIT_ONLY":
        return decision("WAIT_ONLY","HBE_WAIT_NO_MUTATION")
    if hbe=="STOP_ONLY":
        return decision("STOP_ONLY","HBE_TERMINAL_NO_MUTATION")
    if hbe=="SEPARATE_AUTHORITY_REQUIRED":
        return decision("SEPARATE_AUTHORITY_REQUIRED","HBE_SEPARATE_AUTHORITY_FAIL_CLOSED")
    if hbe=="BLOCKED":
        return blocked("HBE_BLOCKED")
    boundary=s.get("transaction_boundary")
    if boundary not in p["transaction_semantics"]["allowed_boundaries"]:
        return blocked("UNKNOWN_TRANSACTION_BOUNDARY")
    if boundary=="TRANSACTION_OUTCOME_UNKNOWN":
        return decision("RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH","NO_REPLAY_RECONCILE_FIRST")
    if boundary=="PROVIDER_READBACK_PENDING":
        return decision("WAIT_FOR_FRESH_PROVIDER_READBACK","NO_MUTATION_UNTIL_READBACK")
    completed=s.get("completed_transaction_fingerprints")
    if not isinstance(completed,list) or len(completed)!=len(set(completed)):
        return blocked("INVALID_OR_DUPLICATE_COMPLETED_TRANSACTION_FINGERPRINTS")
    nxt=s.get("next_transaction_fingerprint")
    if nxt is not None and nxt in completed:
        return blocked("COMPLETED_TRANSACTION_REPLAY_FORBIDDEN")
    if s.get("persisted_control_loop_reuse_requested") or s.get("persisted_admission_reuse_requested") or s.get("persisted_ci_reuse_requested") or s.get("persisted_cas_reuse_requested"):
        return blocked("PERSISTED_DECISION_OR_TOKEN_REUSE_FORBIDDEN")
    conflicts=ps.get("unexpired_active_in_conflict_domain")
    if not isinstance(conflicts,int) or conflicts < 0:
        return blocked("INVALID_CONFLICT_COUNT")
    lease=ps.get("exact_owned_lease")
    if lease is not None:
        for k in ("lease_id","work_unit_id","conflict_domain","holder","base_sha","branch","state","generation","expired"):
            if k not in lease:
                return blocked("EXACT_OWNED_LEASE_INCOMPLETE")
        if lease["work_unit_id"]!=wu["work_unit_id"] or lease["conflict_domain"]!=wu["conflict_domain"] or lease["base_sha"]!=wu["base_sha"] or lease["branch"]!=s["expected_branch"]:
            return blocked("EXACT_OWNED_LEASE_BINDING_MISMATCH")
        if not isinstance(lease["generation"],int) or lease["generation"]>ps["registry_generation"]:
            return blocked("LEASE_GENERATION_INVALID")
        if lease["state"]=="ACTIVE" and lease["expired"] is False:
            if conflicts != 1:
                return blocked("LIVE_OWNED_LEASE_TOPOLOGY_MISMATCH")
            return decision("RECOMPUTE_FRESH_CONTINUATION","LIVE_EXACT_LEASE_PRESENT_RECOMPUTE_CONTROL_LOOP")
        if lease["state"] not in ("ACTIVE","RELEASED"):
            return blocked("UNKNOWN_LEASE_STATE")
        if conflicts != 0:
            return blocked("OTHER_UNEXPIRED_ACTIVE_LEASE_BLOCKS_FRESH_CLAIM")
    else:
        if conflicts != 0:
            return blocked("UNOWNED_UNEXPIRED_ACTIVE_LEASE_BLOCKS_FRESH_CLAIM")
    return decision(
        "FRESH_MONOTONIC_LEASE_REQUIRED",
        "NO_EXACT_OWNED_ACTIVE_UNEXPIRED_LEASE",
        p["writer_lease_resume_semantics"]["fresh_claim_delegated_authority_identity"],
        ps["registry_generation"]+1,
    )

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--policy",required=True)
    ap.add_argument("--checkpoint")
    ap.add_argument("--self-check",action="store_true")
    args=ap.parse_args()
    p=load_json(args.policy)
    if args.self_check:
        validate_policy(p)
        print(json.dumps({"policy":"PASS","authority_granted":False},sort_keys=True))
        return
    if not args.checkpoint:
        raise SystemExit("--checkpoint required unless --self-check")
    s=load_json(args.checkpoint)
    print(json.dumps(evaluate(p,s),sort_keys=True))

if __name__=="__main__":
    main()
