import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-wu159-bounded-unattended-window-durable-state.json"
EXIT_POLICY = ROOT / ".pncc-dev/contracts/wave6-exit-product-priority-policy.json"
ACTIVATION = ROOT / ".pncc-dev/contracts/wave6-wu156-bounded-unattended-activation.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_wu159_durable_state_is_bounded_and_not_live_qualified():
    c = load(CONTRACT)
    assert c["schema_version"] == 1
    assert c["role"] == "WAVE6_BOUNDED_UNATTENDED_WINDOW_DURABLE_STATE"
    assert c["work_unit_id"] == "PIPE-WU-159"
    assert c["issue_number"] == 366
    assert c["state"] == "DURABLE_STATE_ACTIVE_NOT_LIVE_QUALIFIED"
    assert c["exact_base_sha"] == "738aa7eaca6c3da65f039b499aa0243b1b254d86"
    assert c["conflict_domain"] == "wave6-bounded-unattended-window-durable-state"
    assert c["runtime_required"] is False
    assert c["live_qualification"]["performed"] is False
    assert c["live_qualification"]["claim_live_qualified"] is False
    assert c["remaining_permitted_domains"] == ["wave6-bounded-unattended-window-live-qualification"]
    assert c["next_expected_work_unit"] == "PIPE-WU-160"


def test_wu159_preserves_window_budget_and_single_writer():
    c = load(CONTRACT)
    w = c["current_window"]
    assert w["max_work_units"] == 3
    assert w["max_wall_clock_minutes"] == 90
    assert w["max_parallel_mutating_writers"] == 1
    assert w["work_units_consumed_in_current_window_after_wu159_merge"] == 2
    assert w["work_units_remaining_after_wu159_merge"] == 1
    assert w["fresh_provider_truth_each_work_unit"] is True
    assert w["fresh_writer_lease_each_work_unit"] is True
    assert w["exact_head_ci_before_merge"] is True
    assert w["writer_lease_released_before_merge"] is True
    assert w["pinned_expected_head_merge"] is True
    assert w["stop_on_first_governed_exception"] is True


def test_wu159_is_recovery_of_explicit_historical_domain_not_scope_expansion():
    c = load(CONTRACT)
    a = load(ACTIVATION)
    domain = c["conflict_domain"]
    assert domain in a["permitted_conflict_domains"]
    assert "wave6-bounded-unattended-window-live-qualification" in a["permitted_conflict_domains"]
    assert c["authority_continuity"]["historical_failed_successor"] == "PIPE-WU-157"
    assert c["authority_continuity"]["cas_repair_and_live_qualification"] == "PIPE-WU-158"
    assert c["authority_continuity"]["fresh_owner_continuation_authorization_present"] is True
    assert c["authority_continuity"]["new_pipeline_scope_granted"] is False


def test_wu159_preserves_fail_closed_stop_conditions():
    c = load(CONTRACT)
    required = {
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
    assert set(c["mandatory_stop_conditions"]) == required


def test_wu159_grants_no_forbidden_authority():
    authority = load(CONTRACT)["authority"]
    assert authority
    assert all(value is False for value in authority.values())


def test_wave6_exit_returns_primary_priority_to_product_after_terminal_qualification():
    c = load(CONTRACT)
    e = load(EXIT_POLICY)
    assert c["wave6_exit"]["after_terminal_live_qualification_primary_priority"] == "VPSCC_PRODUCT_DEVELOPMENT"
    assert c["wave6_exit"]["pipeline_work_mode_after_terminal"] == "MAINTENANCE_BY_EXCEPTION"
    assert c["wave6_exit"]["new_pipeline_maturity_expansion_by_default"] is False
    assert e["post_wave6"]["primary_priority"] == "VPSCC_PRODUCT_DEVELOPMENT"
    assert e["post_wave6"]["pipeline_work_mode"] == "MAINTENANCE_BY_EXCEPTION"
    assert e["post_wave6"]["new_pipeline_maturity_expansion_by_default"] is False
