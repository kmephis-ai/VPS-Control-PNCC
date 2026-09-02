import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".pncc-dev" / "contracts" / "wave6-wu160-bounded-unattended-window-live-qualification.json"


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_wu160_terminal_live_qualification_contract_is_bounded_and_fail_closed():
    c = load_contract()

    assert c["schema_version"] == 1
    assert c["role"] == "WAVE6_BOUNDED_UNATTENDED_WINDOW_LIVE_QUALIFICATION"
    assert c["work_unit_id"] == "PIPE-WU-160"
    assert c["issue_number"] == 368
    assert c["state"] == "LIVE_QUALIFICATION_READY_FOR_TERMINAL_MERGE"
    assert c["exact_base_sha"] == "8b7a02fdfac46afe4adff4bfec70f227ac133efa"
    assert c["conflict_domain"] == "wave6-bounded-unattended-window-live-qualification"
    assert c["runtime_required"] is False

    acquire = c["fresh_acquire_evidence"]
    assert acquire["required"] is True
    assert acquire["executor_conclusion"] == "SUCCESS"
    assert acquire["lease_id"] == "09d5905c-8894-4e89-a246-f73da9b38ddb"
    assert acquire["registry_generation"] == 75
    assert acquire["lease_state_at_branch_admission"] == "ACTIVE"

    req = c["terminal_qualification_requirements"]
    for key in (
        "fresh_writer_lease_acquire_success",
        "exact_wu_domain_base_branch_binding",
        "bounded_non_main_branch",
        "pull_request_to_exact_main",
        "exact_head_ci_terminal_green",
        "fresh_writer_lease_release_success",
        "writer_lease_released_before_merge",
        "provider_state_release_readback",
        "governed_expected_head_merge",
        "exact_current_main_equals_merge_sha_readback",
        "no_direct_main_engineering_write",
        "no_force_or_bypass",
    ):
        assert req[key] is True

    transition = c["terminal_transition"]
    assert transition["precondition_state"] == "LIVE_QUALIFICATION_READY_FOR_TERMINAL_MERGE"
    assert transition["terminal_state"] == "TERMINAL_PIPELINE_MATURITY_COMPLETE"
    assert transition["terminal_result"] == "BOUNDED_UNATTENDED_LIVE_QUALIFICATION_PASS"
    assert transition["must_not_claim_terminal_before_condition"] is True

    window = c["current_window_after_terminal"]
    assert window == {
        "max_work_units": 3,
        "max_wall_clock_minutes": 90,
        "max_parallel_mutating_writers": 1,
        "work_units_consumed": 3,
        "work_units_remaining": 0,
        "authorization_exhausted": True,
        "fourth_pipeline_work_unit_authorized": False,
    }

    pipeline = c["pipeline_after_terminal"]
    assert pipeline["remaining_permitted_domains"] == []
    assert pipeline["next_pipeline_work_unit"] == "NONE"
    assert pipeline["pipeline_maturity_program_state"] == "COMPLETE"
    assert pipeline["primary_priority"] == "VPSCC_PRODUCT_DEVELOPMENT"
    assert pipeline["pipeline_work_mode"] == "MAINTENANCE_BY_EXCEPTION"
    assert pipeline["new_pipeline_maturity_expansion_by_default"] is False
    assert pipeline["product_mutation_authorized_by_wu160"] is False

    authority = c["authority"]
    assert authority
    assert all(value is False for value in authority.values())
