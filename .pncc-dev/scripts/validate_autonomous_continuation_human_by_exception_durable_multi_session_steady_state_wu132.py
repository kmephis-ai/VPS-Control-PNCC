#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

PNCC_DEV = Path(__file__).resolve().parents[1]
EVIDENCE = PNCC_DEV / "contracts" / "autonomous-continuation-human-by-exception-durable-multi-session-steady-state-wu132.json"
EXPECTED_BASE = "3e7c86b1235f3bcb9b94c3218f3cfa41636e5f3a"
EXPECTED_BRANCH = "agent/PIPE-WU-132-human-by-exception-durable-multi-session-steady-state-existing-authority-only"
EXPECTED_ROUTES = {
    "OWNER_ESCALATION_REQUIRED",
    "WAIT_ONLY",
    "STOP_ONLY",
    "SEPARATE_AUTHORITY_REQUIRED",
    "BLOCKED",
}


def validate(data):
    errors = []

    def require(cond, msg):
        if not cond:
            errors.append(msg)

    require(data.get("role") == "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_MULTI_SESSION_STEADY_STATE_EVIDENCE", "unexpected role")
    require(data.get("work_unit_id") == "PIPE-WU-132", "unexpected work unit")
    require(data.get("issue") == 312, "unexpected issue")
    require(data.get("state") == "COMPLETE", "evidence not complete")
    require(data.get("base_sha") == EXPECTED_BASE, "base SHA mismatch")
    require(data.get("branch") == EXPECTED_BRANCH, "branch mismatch")
    require(data.get("runtime_required") is False, "runtime must not be required")
    auth = data.get("authority", {})
    require(auth.get("existing_authority_only") is True, "existing authority only must be true")
    require(auth.get("higher_authority_claimed") is False, "higher authority must not be claimed")
    require(data.get("required_completed_iterations") == 2, "required iterations must be 2")
    sessions = data.get("sessions", [])
    require(data.get("completed_iterations") == len(sessions) == 2, "exactly two completed sessions required")
    fingerprints = []
    ids = []
    for session in sessions:
        sid = session.get("session_id")
        ids.append(sid)
        require(session.get("fresh_provider_truth") is True, f"{sid}: fresh provider truth missing")
        require(session.get("persisted_decisions_discarded") is True, f"{sid}: persisted decisions not discarded")
        require(session.get("decisions_recomputed") is True, f"{sid}: decisions not recomputed")
        require(session.get("delegated_transaction_count") == 1, f"{sid}: transaction count must be one")
        require(session.get("replay_outcome") == "REJECTED", f"{sid}: replay must be rejected")
        canonical = session.get("canonical_fingerprint_input", "")
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        actual = session.get("completed_transaction_fingerprint_sha256")
        fingerprints.append(actual)
        require(actual == expected, f"{sid}: fingerprint mismatch")
    require(len(ids) == len(set(ids)), "session IDs must be unique")
    require(len(fingerprints) == len(set(fingerprints)), "completed transaction fingerprints must be unique")
    if len(sessions) == 2:
        a, b = sessions
        require(a.get("transaction") == "WRITER_LEASE_ACQUIRE", "session-a transaction mismatch")
        require(a.get("registry_generation_before") == 40 and a.get("registry_generation_after") == 41, "lease generation must advance 40 -> 41")
        require(b.get("transaction") == "WORK_UNIT_BRANCH_CREATE", "session-b transaction mismatch")
        require(b.get("branch_readback_sha") == EXPECTED_BASE, "session-b branch readback mismatch")
    require(data.get("historical_lease_semantics") == "EXPIRED_OR_RELEASED_OBSERVATION_ONLY", "historical lease semantics mismatch")
    require(set(data.get("human_by_exception_routes_preserved", [])) == EXPECTED_ROUTES, "HBE routes not preserved")
    forbidden = data.get("forbidden_mutations", {})
    require(forbidden and all(value is False for value in forbidden.values()), "forbidden mutation recorded")
    frontier = data.get("next_frontier", {})
    require(frontier.get("id") == "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_DURABLE_MULTI_SESSION_STEADY_STATE_EXECUTION_WITH_EXISTING_AUTHORITY_ONLY", "next frontier mismatch")
    require(frontier.get("materialized") is False, "unmaterialized WU133 must not be claimed materialized")
    return errors


def main():
    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("PIPE-WU-132 durable multi-session steady-state evidence: PASS")


if __name__ == "__main__":
    main()
