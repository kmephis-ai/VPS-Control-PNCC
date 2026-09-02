#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_DOMAINS = [
    "wave6-bounded-unattended-activation",
    "wave6-bounded-unattended-window-durable-state",
    "wave6-bounded-unattended-window-live-qualification",
]
REQUIRED_STOPS = {
    "NO_DETERMINISTIC_NEXT_WORK_UNIT",
    "MAIN_OR_PROVIDER_STATE_DRIFT",
    "CI_FAILURE_REQUIRES_UNAUTHORIZED_SCOPE",
    "WAITING_RUNTIME",
    "PRODUCT_OR_RUNTIME_MUTATION_REQUIRED",
    "POLICY_OR_SECURITY_AUTHORITY_REQUIRED",
    "RULESET_OR_SECURITY_WEAKENING_REQUIRED",
    "RELEASE_TAG_OR_PROMOTION_BOUNDARY",
    "RESERVE_1080_LIFECYCLE_BOUNDARY",
    "PRIMARY_1081_RUNTIME_LIFECYCLE_BOUNDARY",
    "V631_MUTATION_BOUNDARY",
    "SELF_HOSTED_RUNNER_REQUIRED",
    "WRITER_LEASE_CONFLICT_OR_EXPIRY",
    "WORK_UNIT_OR_WALL_CLOCK_BUDGET_EXHAUSTED",
    "UNKNOWN_OR_STALE_PROVIDER_TRUTH",
}
FORBIDDEN_TRUE_KEYS = {
    "product_runtime_mutation",
    "reserve_1080_lifecycle_mutation",
    "primary_1081_lifecycle_mutation",
    "v631_mutation",
    "ruleset_security_weakening",
    "release_tag_promotion",
    "self_hosted_runner",
    "external_token_webhook_scheduler",
    "force_or_bypass",
    "direct_main_engineering_write",
    "wildcard_conflict_domain",
}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("TIMESTAMP_NOT_UTC_Z")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)


def validate(receipt, contract, readiness, expected_main, now=None):
    errors = []
    def require(condition, code):
        if not condition:
            errors.append(code)

    require(receipt.get("schema_version") == 1, "RECEIPT_SCHEMA")
    require(receipt.get("role") == "WAVE6_BOUNDED_UNATTENDED_OWNER_RECEIPT", "RECEIPT_ROLE")
    require(contract.get("schema_version") == 1, "CONTRACT_SCHEMA")
    require(contract.get("role") == "WAVE6_BOUNDED_UNATTENDED_ACTIVATION", "CONTRACT_ROLE")
    require(contract.get("status") == "ACTIVE_AFTER_GOVERNED_MERGE_ONLY", "CONTRACT_STATUS")
    require(readiness.get("role") == "WAVE6_UNATTENDED_ACTIVATION_OWNER_AUTHORIZATION_READINESS", "READINESS_ROLE")

    exact_pairs = (
        "authorization_id", "issued_by", "authorized_main_sha", "activation_work_unit_id",
        "permitted_conflict_domains", "max_work_units", "max_wall_clock_minutes",
        "max_parallel_mutating_writers", "authority_grant_sha", "issued_at", "expires_at",
        "single_use", "replay_forbidden",
    )
    for key in exact_pairs:
        require(receipt.get(key) == contract.get(key), "RECEIPT_CONTRACT_MISMATCH_" + key.upper())

    require(contract.get("issued_by") == "kmephis-ai", "ISSUER")
    require(contract.get("authorized_main_sha") == expected_main, "AUTHORIZED_MAIN")
    require(SHA40.fullmatch(str(expected_main or "")) is not None, "EXPECTED_MAIN_SHA40")
    require(contract.get("activation_work_unit_id") == "PIPE-WU-156", "ACTIVATION_WU")
    require(contract.get("activation_issue_number") == 361, "ACTIVATION_ISSUE")
    require(contract.get("permitted_conflict_domains") == EXPECTED_DOMAINS, "EXACT_DOMAINS")
    domains = contract.get("permitted_conflict_domains") or []
    require(all(isinstance(x, str) and x and "*" not in x for x in domains), "NON_WILDCARD_DOMAINS")
    require(len(set(domains)) == len(EXPECTED_DOMAINS), "UNIQUE_DOMAINS")

    require(contract.get("max_work_units") == 3, "MAX_WORK_UNITS")
    require(contract.get("work_units_consumed_by_activation") == 1, "CONSUMED_BY_ACTIVATION")
    require(contract.get("work_units_remaining_after_activation") == 2, "REMAINING_AFTER_ACTIVATION")
    require(contract.get("max_wall_clock_minutes") == 90, "MAX_WALL_CLOCK")
    require(contract.get("max_parallel_mutating_writers") == 1, "MAX_MUTATING_WRITERS")
    require(SHA40.fullmatch(str(contract.get("authority_grant_sha", ""))) is not None, "AUTHORITY_GRANT_SHA40")
    require(SHA40.fullmatch(str(contract.get("owner_receipt_sha", ""))) is not None, "OWNER_RECEIPT_SHA40")
    require(contract.get("authority_grant_sha") == "ab80e34923fae92124ee1fb1b43e33b63499239d", "AUTHORITY_GRANT_PIN")
    require(contract.get("owner_receipt_sha") == "a26d2c28cb01022e7e625ff358fa0e94ffa177b9", "OWNER_RECEIPT_PIN")
    require(contract.get("single_use") is True, "SINGLE_USE")
    require(contract.get("replay_forbidden") is True, "REPLAY_FORBIDDEN")

    envelope = readiness.get("activation_envelope", {})
    require(contract.get("max_work_units", 999) <= envelope.get("max_work_units", -1), "READINESS_WU_BOUND")
    require(contract.get("max_wall_clock_minutes", 999) <= envelope.get("max_wall_clock_minutes", -1), "READINESS_TIME_BOUND")
    require(contract.get("max_parallel_mutating_writers") == envelope.get("max_parallel_mutating_writers") == 1, "READINESS_WRITER_BOUND")

    admission = contract.get("admission", {})
    for key in (
        "fresh_provider_truth_each_work_unit", "fresh_writer_lease_each_mutating_work_unit",
        "exact_head_ci_success_before_each_merge", "writer_lease_released_before_each_merge",
        "pinned_expected_head_merge", "stop_on_first_governed_exception",
    ):
        require(admission.get(key) is True, "ADMISSION_" + key.upper())
    require(admission.get("carry_authority_across_work_units") is False, "NO_AUTHORITY_CARRY")
    require(admission.get("reuse_writer_lease_across_conflict_domains") is False, "NO_LEASE_REUSE")

    require(REQUIRED_STOPS.issubset(set(contract.get("mandatory_stop_conditions", []))), "MANDATORY_STOPS")
    authority = contract.get("authority", {})
    require(authority.get("bounded_unattended_mutation_within_explicit_domains") is True, "BOUNDED_AUTHORITY")
    for key in FORBIDDEN_TRUE_KEYS:
        require(authority.get(key) is False, "FORBIDDEN_AUTHORITY_" + key.upper())

    try:
        issued = _parse_utc(contract.get("issued_at"))
        expires = _parse_utc(contract.get("expires_at"))
        require(expires > issued, "TIME_ORDER")
        require((expires - issued).total_seconds() <= 90 * 60, "TIME_ENVELOPE")
        if now is not None:
            require(issued <= now < expires, "AUTHORIZATION_EXPIRED_OR_NOT_YET_VALID")
    except (ValueError, TypeError):
        errors.append("TIMESTAMP_PARSE")

    require(contract.get("terminal_after_merge") == "BOUNDED_UNATTENDED_WINDOW_ACTIVE", "TERMINAL")
    require(contract.get("next_expected_work_unit") == "PIPE-WU-157", "NEXT_WU")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--readiness", required=True)
    parser.add_argument("--expected-main", required=True)
    parser.add_argument("--now", default=None)
    args = parser.parse_args()
    now = _parse_utc(args.now) if args.now else None
    errors = validate(_load(args.receipt), _load(args.contract), _load(args.readiness), args.expected_main, now)
    print(json.dumps({"result": "ACTIVATION_AUTHORIZATION_VALID" if not errors else "NOT_AUTHORIZED", "errors": errors}, sort_keys=True))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
