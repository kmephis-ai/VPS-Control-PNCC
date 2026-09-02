#!/usr/bin/env python3
import json
import sys
from pathlib import Path

FALSE_AUTHORITY_KEYS = {
    "unattended_mutation_activation",
    "new_merge_authority",
    "new_branch_authority",
    "new_issue_authority",
    "workflow_rerun_authority",
    "provider_mutation_authority",
    "scheduler_mutation_authority",
    "runtime_action_authority",
    "product_runtime_mutation_authority",
    "ruleset_security_mutation_authority",
    "release_tag_promotion_authority",
    "reserve_1080_lifecycle_mutation_authority",
    "primary_1081_lifecycle_mutation_authority",
    "v631_mutation_authority",
    "self_hosted_runner_authority",
    "force_or_bypass_authority",
    "private_evidence_publication_authority",
}

REQUIRED_STOPS = {
    "NO_DETERMINISTIC_NEXT_WORK_UNIT",
    "MAIN_OR_PROVIDER_STATE_DRIFT",
    "WAITING_RUNTIME",
    "POLICY_OR_SECURITY_AUTHORITY_REQUIRED",
    "RELEASE_TAG_OR_PROMOTION_BOUNDARY",
    "WRITER_LEASE_CONFLICT_OR_EXPIRY",
    "WORK_UNIT_OR_WALL_CLOCK_BUDGET_EXHAUSTED",
    "UNKNOWN_OR_STALE_PROVIDER_TRUTH",
}


def evaluate(contract):
    reasons = []
    if contract.get("schema_version") != 1:
        reasons.append("SCHEMA_VERSION")
    if contract.get("role") != "WAVE6_BOUNDED_UNATTENDED_DEVELOPMENT_WINDOW_READINESS":
        reasons.append("ROLE")
    if contract.get("state") != "READINESS_ONLY_NO_ACTIVATION":
        reasons.append("STATE")

    envelope = contract.get("recommended_initial_envelope") or {}
    if not isinstance(envelope.get("max_work_units"), int) or not (1 <= envelope["max_work_units"] <= 3):
        reasons.append("WORK_UNIT_BUDGET")
    if not isinstance(envelope.get("max_wall_clock_minutes"), int) or not (1 <= envelope["max_wall_clock_minutes"] <= 90):
        reasons.append("TIME_BUDGET")
    if envelope.get("max_parallel_mutating_writers") != 1:
        reasons.append("PARALLEL_MUTATING_WRITERS")
    for key in (
        "fresh_provider_truth_each_work_unit",
        "stop_on_first_governed_exception",
    ):
        if envelope.get(key) is not True:
            reasons.append(key.upper())
    for key in (
        "carry_authority_across_work_units",
        "reuse_writer_lease_across_conflict_domains",
    ):
        if envelope.get(key) is not False:
            reasons.append(key.upper())

    auth = contract.get("authority") or {}
    for key in sorted(FALSE_AUTHORITY_KEYS):
        if auth.get(key) is not False:
            reasons.append("AUTHORITY_" + key.upper())

    stops = set(contract.get("mandatory_stop_conditions") or [])
    if not REQUIRED_STOPS.issubset(stops):
        reasons.append("STOP_CONDITIONS")

    durable = contract.get("durable_stop_semantics") or {}
    for key in (
        "persist_reason",
        "preserve_completed_work",
        "release_active_writer_lease_if_lawfully_releasable",
        "no_guessing_or_authority_escalation",
        "resume_requires_fresh_provider_reconciliation",
    ):
        if durable.get(key) is not True:
            reasons.append("DURABLE_" + key.upper())

    activation = contract.get("activation_decision") or {}
    if activation.get("performed") is not False:
        reasons.append("ACTIVATION_PERFORMED")
    if activation.get("separate_owner_decision_required") is not True:
        reasons.append("OWNER_DECISION_BOUNDARY")
    if activation.get("default_without_new_owner_authorization") != "DO_NOT_ACTIVATE_UNATTENDED_MUTATION":
        reasons.append("DEFAULT_ACTIVATION")

    state = "PASS" if not reasons else "FAIL_CLOSED"
    return {
        "schema_version": 1,
        "role": "WAVE6_WU152_BOUNDED_UNATTENDED_WINDOW_READINESS_RESULT",
        "state": state,
        "ready_for_owner_activation_decision": not reasons,
        "unattended_mutation_activated": False,
        "authority_granted": False,
        "reasons": reasons,
    }


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: evaluate_wave6_bounded_unattended_window_readiness_wu152.py <contract.json>")
    contract = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    result = evaluate(contract)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
