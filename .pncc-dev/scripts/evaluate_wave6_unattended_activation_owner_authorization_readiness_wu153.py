#!/usr/bin/env python3
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
UUIDISH = re.compile(r"^[0-9a-fA-F-]{36}$")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def iso(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_contract(c):
    errors = []
    expected_false = c.get("authority", {})
    if c.get("state") != "READINESS_ONLY_NO_ACTIVATION": errors.append("contract_state")
    env = c.get("activation_envelope", {})
    if env.get("max_work_units") != 3: errors.append("max_work_units")
    if env.get("max_wall_clock_minutes") != 90: errors.append("max_wall_clock_minutes")
    if env.get("max_parallel_mutating_writers") != 1: errors.append("max_parallel_mutating_writers")
    if any(v is not False for v in expected_false.values()): errors.append("authority_not_zero")
    cons = c.get("future_owner_authorization_constraints", {})
    if cons.get("generic_chat_continuation_is_authority") is not False: errors.append("implicit_chat_authority")
    if cons.get("implicit_authorization_inference_forbidden") is not True: errors.append("implicit_inference")
    if c.get("candidate_validation_semantics", {}).get("valid_shape_grants_execution") is not False: errors.append("shape_grants_execution")
    return errors


def validate_candidate(c, a, fresh_main, expected_wu, now):
    errors = []
    required = c["future_owner_authorization_required_fields"]
    for k in required:
        if k not in a: errors.append("missing:" + k)
    if errors: return errors
    if not UUIDISH.match(str(a["authorization_id"])): errors.append("authorization_id")
    if a["issued_by"] != c["future_owner_authorization_constraints"]["issued_by"]: errors.append("issued_by")
    if not SHA40.match(str(a["authorized_main_sha"])) or a["authorized_main_sha"] != fresh_main: errors.append("authorized_main_sha")
    if a["activation_work_unit_id"] != expected_wu: errors.append("activation_work_unit_id")
    domains = a["permitted_conflict_domains"]
    if not isinstance(domains, list) or not domains or any((not isinstance(x, str) or not x or "*" in x) for x in domains): errors.append("permitted_conflict_domains")
    if not isinstance(a["max_work_units"], int) or not 1 <= a["max_work_units"] <= 3: errors.append("max_work_units")
    if not isinstance(a["max_wall_clock_minutes"], int) or not 1 <= a["max_wall_clock_minutes"] <= 90: errors.append("max_wall_clock_minutes")
    if a["max_parallel_mutating_writers"] != 1: errors.append("max_parallel_mutating_writers")
    if not SHA40.match(str(a["authority_grant_sha"])): errors.append("authority_grant_sha")
    if not SHA40.match(str(a["owner_receipt_sha"])): errors.append("owner_receipt_sha")
    if a["single_use"] is not True: errors.append("single_use")
    if a["replay_forbidden"] is not True: errors.append("replay_forbidden")
    if a.get("replayed") is True: errors.append("replayed")
    try:
        issued, expires = iso(a["issued_at"]), iso(a["expires_at"])
        if issued.tzinfo is None or expires.tzinfo is None: errors.append("timezone")
        if expires <= issued or expires <= now: errors.append("expired")
    except Exception:
        errors.append("timestamps")
    if a.get("runtime_required") is not False: errors.append("runtime_required")
    for forbidden in ["product_runtime_mutation", "runtime_action", "ruleset_security_mutation", "release_tag_promotion", "self_hosted_runner", "external_token_or_webhook", "force_or_bypass", "direct_main_engineering_write"]:
        if a.get(forbidden) is True: errors.append("forbidden:" + forbidden)
    return errors


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--contract", required=True)
    p.add_argument("--authorization-candidate")
    p.add_argument("--fresh-main")
    p.add_argument("--expected-activation-wu")
    p.add_argument("--now")
    args = p.parse_args()
    c = load(args.contract)
    contract_errors = validate_contract(c)
    out = {"contract_valid": not contract_errors, "contract_errors": contract_errors, "execution_authority_granted": False}
    if contract_errors:
        out["classification"] = "NOT_AUTHORIZED"
    elif not args.authorization_candidate:
        out["classification"] = c["terminal_if_valid"]
    else:
        if not args.fresh_main or not args.expected_activation_wu:
            out["classification"] = "NOT_AUTHORIZED"; out["authorization_errors"] = ["missing_fresh_context"]
        else:
            a = load(args.authorization_candidate)
            now = iso(args.now) if args.now else datetime.now(timezone.utc)
            errors = validate_candidate(c, a, args.fresh_main, args.expected_activation_wu, now)
            out["authorization_shape_valid"] = not errors
            out["authorization_errors"] = errors
            out["classification"] = "SHAPE_VALID_NO_EXECUTION" if not errors else "NOT_AUTHORIZED"
    print(json.dumps(out, sort_keys=True))
    return 0 if out["classification"] != "NOT_AUTHORIZED" else 2

if __name__ == "__main__":
    raise SystemExit(main())
