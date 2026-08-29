#!/usr/bin/env python3
"""Read-only PNCC Work Unit selection and orchestration disposition.

This module reads provider truth, validates the current Wave-5 proof baseline,
classifies canonical Work Units and emits a deterministic orchestration
disposition. It never acquires a writer lease and never mutates GitHub/runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
WU_ID = re.compile(r"^[A-Z][A-Z0-9_-]*-[0-9]+$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
MARKER = re.compile(r"<!--\s*PNCC-WORK-UNIT(?P<attrs>.*?)-->", re.IGNORECASE | re.DOTALL)
WORK_UNIT_STATES = {"READY", "ACTIVE", "BLOCKED", "VERIFYING", "DONE", "SUPERSEDED"}
REQUIRED_MARKER_KEYS = {"schema", "id", "state", "conflict_domain", "base", "runtime_required"}
OPTIONAL_MARKER_KEYS = {"branch"}
EXPECTED_STABLE_VERSION = "7.0.1"
EXPECTED_STABLE_ATTESTATION = ".pncc-dev/attestations/stable-v7.0.1-completion.json"
EXPECTED_STABLE_FILENAME = "VPS-Control-v7.0.1.zip"
EXPECTED_STABLE_SHA = "22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72"
EXPECTED_STABLE_SIZE = 701893
EXPECTED_ADWF_SHA = "c7e0c059a901869d6369864e98d06238484778ec"
EXPECTED_PACK_DIGEST = "fbe69c4e93ff8b07e7d0dc6f0cbd1f9ceb80617f472f1fbe5a1ce181279a0c8c"
MUTATION_AUTHORITY = "NONE_BINDING_IS_PROOF_ONLY"


class SelectionError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SelectionError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def validate_readiness_guard(root: Path = ROOT) -> None:
    readiness = load_json(root / ".adwf-consumer" / "wave5-readiness.json")
    stable = load_json(root / EXPECTED_STABLE_ATTESTATION)
    binding = load_json(root / ".adwf-consumer" / "external-binding.json")

    if readiness.get("role") != "PNCC_WAVE5_ADWF_PROOF_READINESS" or readiness.get("state") != "WAVE5_ADWF_PROOF_BASELINE_READY":
        raise SelectionError("WAVE5_READINESS_NOT_READY")

    expected_baseline = {
        "version": EXPECTED_STABLE_VERSION,
        "completion_attestation": EXPECTED_STABLE_ATTESTATION,
        "completion_state": "STABLE_COMPLETE",
        "runtime_authority": True,
        "artifact_filename": EXPECTED_STABLE_FILENAME,
        "artifact_sha256": EXPECTED_STABLE_SHA,
        "artifact_size_bytes": EXPECTED_STABLE_SIZE,
    }
    if readiness.get("stable_baseline") != expected_baseline:
        raise SelectionError("WAVE5_STABLE_BASELINE_DRIFT")

    consumer = readiness.get("consumer", {})
    if consumer.get("mutation_authority") != MUTATION_AUTHORITY or consumer.get("managed_surface_adopted") is not False:
        raise SelectionError("WAVE5_READINESS_AUTHORITY_DRIFT")
    if consumer.get("project_pack") != "powershell" or consumer.get("project_pack_digest") != EXPECTED_PACK_DIGEST:
        raise SelectionError("WAVE5_PROJECT_PACK_DRIFT")

    safety = readiness.get("safety", {})
    forbidden_flags = (
        "autonomous_branch_mutation", "autonomous_merge", "autonomous_issue_close",
        "runtime_action_authority", "promotion_authority", "release_or_tag_authority",
        "ruleset_or_policy_mutation",
    )
    if any(safety.get(name) is not False for name in forbidden_flags):
        raise SelectionError("WAVE5_FORBIDDEN_AUTHORITY_PRESENT")
    framework = readiness.get("framework", {})
    if framework.get("source_sha") != EXPECTED_ADWF_SHA:
        raise SelectionError("WAVE5_ADWF_PIN_DRIFT")
    if framework.get("provider_ops_consumer_authority_granted") is not False:
        raise SelectionError("PROVIDER_OPS_AUTHORITY_UNEXPECTED")

    stable_expected = {
        "stable_version": EXPECTED_STABLE_VERSION,
        "state": "STABLE_COMPLETE",
        "runtime_authority": True,
        "artifact_filename": EXPECTED_STABLE_FILENAME,
        "artifact_sha256": EXPECTED_STABLE_SHA,
        "artifact_size_bytes": EXPECTED_STABLE_SIZE,
        "physical_startup_acceptance": "PASS",
        "fresh_nine_scope_reconcile": "PASS",
        "promotion_state": "PROMOTED",
        "stable_declared": True,
        "release_asset_verified": True,
        "next_frontier": "WAVE5_ADWF_AUTONOMOUS_EXECUTION",
        "artifact_rebuilt": False,
        "artifact_substituted": False,
        "runtime_mutation": False,
        "product_bytes_mutated": False,
        "runtime_bytes_mutated": False,
        "private_runtime_payload_published": False,
        "reserve_1080_lifecycle_mutation": False,
        "primary_1081_lifecycle_mutation": False,
    }
    for key, expected in stable_expected.items():
        if stable.get(key) != expected:
            raise SelectionError("STABLE_V701_TRUTH_DRIFT:" + key)

    if binding.get("framework", {}).get("source_sha") != EXPECTED_ADWF_SHA:
        raise SelectionError("EXTERNAL_BINDING_ADWF_PIN_DRIFT")
    if binding.get("project_pack") != {"id": "powershell", "digest": EXPECTED_PACK_DIGEST}:
        raise SelectionError("EXTERNAL_BINDING_PROJECT_PACK_DRIFT")
    if binding.get("mutation_authority") != MUTATION_AUTHORITY:
        raise SelectionError("EXTERNAL_BINDING_MUTATION_AUTHORITY_DRIFT")


def parse_issue_intake_marker(text: str) -> dict[str, Any] | None:
    if not isinstance(text, str):
        raise SelectionError("ISSUE_BODY_TEXT_REQUIRED")
    matches = list(MARKER.finditer(text))
    if not matches:
        return None
    if len(matches) != 1:
        raise SelectionError(f"WORK_UNIT_MARKER_COUNT:{len(matches)}")

    attrs_text = matches[0].group("attrs").strip()
    attrs: dict[str, str] = {}
    if not attrs_text:
        raise SelectionError("WORK_UNIT_MARKER_EMPTY")
    for token in attrs_text.split():
        if "=" not in token:
            raise SelectionError("WORK_UNIT_MARKER_TOKEN_INVALID")
        key, value = token.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key or not value:
            raise SelectionError("WORK_UNIT_MARKER_TOKEN_INVALID")
        if key in attrs:
            raise SelectionError(f"WORK_UNIT_MARKER_DUPLICATE_KEY:{key}")
        attrs[key] = value

    missing = REQUIRED_MARKER_KEYS - set(attrs)
    unknown = set(attrs) - REQUIRED_MARKER_KEYS - OPTIONAL_MARKER_KEYS
    if missing:
        raise SelectionError("WORK_UNIT_MARKER_MISSING:" + ",".join(sorted(missing)))
    if unknown:
        raise SelectionError("WORK_UNIT_MARKER_UNKNOWN:" + ",".join(sorted(unknown)))
    if attrs["schema"] != "1":
        raise SelectionError("WORK_UNIT_MARKER_SCHEMA_INVALID")
    if WU_ID.fullmatch(attrs["id"]) is None:
        raise SelectionError("WORK_UNIT_MARKER_ID_INVALID")
    state = attrs["state"].upper()
    if state not in WORK_UNIT_STATES:
        raise SelectionError("WORK_UNIT_MARKER_STATE_INVALID")
    if SHA40.fullmatch(attrs["base"]) is None:
        raise SelectionError("WORK_UNIT_MARKER_BASE_INVALID")
    runtime_raw = attrs["runtime_required"].lower()
    if runtime_raw not in {"true", "false"}:
        raise SelectionError("WORK_UNIT_MARKER_RUNTIME_INVALID")
    if not attrs["conflict_domain"].strip():
        raise SelectionError("WORK_UNIT_MARKER_CONFLICT_DOMAIN_INVALID")
    branch = attrs.get("branch")
    if branch is not None and not branch.strip():
        raise SelectionError("WORK_UNIT_MARKER_BRANCH_INVALID")

    return {
        "schema_version": 1,
        "work_unit_id": attrs["id"],
        "state": state,
        "conflict_domain": attrs["conflict_domain"],
        "branch": branch,
        "base_sha": attrs["base"],
        "runtime_required": runtime_raw == "true",
        "materialization_phase": "MATERIALIZED" if branch else "INTAKE",
    }


def _issue_number(issue: dict[str, Any]) -> int:
    value = issue.get("number", issue.get("issue_number"))
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise SelectionError("PROVIDER_ISSUE_NUMBER_INVALID")
    return value


def _is_pull_request(issue: dict[str, Any]) -> bool:
    return "pull_request" in issue and issue.get("pull_request") is not None


def _classify_marker(marker: dict[str, Any], default_head_sha: str) -> tuple[str, str | None]:
    state = marker["state"]
    if state in {"DONE", "SUPERSEDED"}:
        return "TERMINAL", f"STATE_{state}"
    if state == "BLOCKED":
        return "BLOCKED", "STATE_BLOCKED"
    if state == "VERIFYING":
        return "WAITING_PROVIDER", "STATE_VERIFYING"
    if marker["runtime_required"]:
        return "WAITING_RUNTIME", "PRIVATE_RUNTIME_REQUIRED"
    if marker["base_sha"] != default_head_sha:
        return "STALE_BASE", "BASE_DOES_NOT_MATCH_DEFAULT_HEAD"
    if state in {"READY", "ACTIVE"}:
        return "EXECUTABLE_READ_ONLY_SELECTION", None
    return "BLOCKED", "UNCLASSIFIED_STATE"


def _orchestration_disposition(classified: list[dict[str, Any]], selected: dict[str, Any] | None) -> str:
    if selected is not None:
        return "EXECUTABLE"
    non_terminal = [item for item in classified if item["classification"] != "TERMINAL"]
    classes = {item["classification"] for item in non_terminal}
    if "WAITING_RUNTIME" in classes:
        return "WAITING_RUNTIME"
    if classes & {"BLOCKED", "WAITING_PROVIDER", "STALE_BASE"}:
        return "BLOCKED"
    return "NO_WORK"


def _next_boundary(disposition: str) -> str:
    return {
        "EXECUTABLE": "DESIGN_DEFAULT_DENY_WRITER_LEASE_CLAIM_AUTHORITY",
        "WAITING_RUNTIME": "WAIT_FOR_PRIVATE_RUNTIME_EVIDENCE",
        "BLOCKED": "RECONCILE_PROVIDER_TRUTH_OR_GOVERNED_BOUNDARY",
        "NO_WORK": "WAIT_FOR_OR_MATERIALIZE_GOVERNED_WORK_UNIT",
    }[disposition]


def select_from_provider_issues(
    issues: list[dict[str, Any]], *, repository: str, default_branch: str,
    default_head_sha: str, observed_at: str,
) -> dict[str, Any]:
    if not isinstance(issues, list):
        raise SelectionError("PROVIDER_ISSUES_LIST_REQUIRED")
    if not isinstance(repository, str) or "/" not in repository:
        raise SelectionError("PROVIDER_REPOSITORY_INVALID")
    if not isinstance(default_branch, str) or not default_branch.strip():
        raise SelectionError("DEFAULT_BRANCH_INVALID")
    if SHA40.fullmatch(default_head_sha) is None:
        raise SelectionError("DEFAULT_HEAD_SHA_INVALID")

    canonical: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []

    for issue in issues:
        if not isinstance(issue, dict):
            raise SelectionError("PROVIDER_ISSUE_OBJECT_REQUIRED")
        number = _issue_number(issue)
        if _is_pull_request(issue):
            ignored.append({"issue": number, "reason": "PULL_REQUEST_NOT_ISSUE"})
            continue
        if str(issue.get("state", "open")).lower() != "open":
            ignored.append({"issue": number, "reason": "ISSUE_NOT_OPEN"})
            continue
        body = issue.get("body") or ""
        try:
            marker = parse_issue_intake_marker(body)
        except SelectionError as exc:
            if "PNCC-WORK-UNIT" in body.upper():
                malformed.append({"issue": number, "reason": str(exc)})
                continue
            raise
        if marker is None:
            ignored.append({"issue": number, "reason": "NO_CANONICAL_WORK_UNIT_MARKER"})
            continue
        canonical.append({"issue": number, "title": str(issue.get("title") or ""), "marker": marker})

    if malformed:
        raise SelectionError("MALFORMED_OPEN_WORK_UNIT_MARKER:" + json.dumps(malformed, sort_keys=True, separators=(",", ":")))

    ids: dict[str, list[int]] = {}
    domains: dict[str, list[int]] = {}
    for item in canonical:
        marker = item["marker"]
        if marker["state"] in {"DONE", "SUPERSEDED"}:
            continue
        ids.setdefault(marker["work_unit_id"], []).append(item["issue"])
        domains.setdefault(marker["conflict_domain"], []).append(item["issue"])
    duplicate_ids = {key: values for key, values in ids.items() if len(values) > 1}
    duplicate_domains = {key: values for key, values in domains.items() if len(values) > 1}
    if duplicate_ids:
        raise SelectionError("DUPLICATE_OPEN_WORK_UNIT_ID:" + json.dumps(duplicate_ids, sort_keys=True, separators=(",", ":")))
    if duplicate_domains:
        raise SelectionError("DUPLICATE_OPEN_CONFLICT_DOMAIN:" + json.dumps(duplicate_domains, sort_keys=True, separators=(",", ":")))

    classified: list[dict[str, Any]] = []
    executable: list[dict[str, Any]] = []
    for item in canonical:
        classification, reason = _classify_marker(item["marker"], default_head_sha)
        entry = {
            "issue": item["issue"],
            "work_unit_id": item["marker"]["work_unit_id"],
            "state": item["marker"]["state"],
            "conflict_domain": item["marker"]["conflict_domain"],
            "base_sha": item["marker"]["base_sha"],
            "branch": item["marker"]["branch"],
            "runtime_required": item["marker"]["runtime_required"],
            "materialization_phase": item["marker"]["materialization_phase"],
            "classification": classification,
            "reason": reason,
        }
        classified.append(entry)
        if classification == "EXECUTABLE_READ_ONLY_SELECTION":
            executable.append(entry)

    classified.sort(key=lambda item: (item["issue"], item["work_unit_id"]))
    executable.sort(key=lambda item: (item["issue"], item["work_unit_id"]))
    selected = executable[0] if executable else None
    disposition = _orchestration_disposition(classified, selected)

    return {
        "schema_version": 2,
        "role": "READ_ONLY_PROVIDER_WORK_UNIT_SELECTION",
        "state": "READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS",
        "repository": repository,
        "default_branch": default_branch,
        "default_branch_head_sha": default_head_sha,
        "observed_at": observed_at,
        "decision": "SELECTED" if selected else "NO_EXECUTABLE_WORK_UNIT",
        "orchestration_disposition": disposition,
        "selected": selected,
        "executable_count": len(executable),
        "canonical_work_units": classified,
        "ignored_issues": sorted(ignored, key=lambda item: item["issue"]),
        "mutation_authority": MUTATION_AUTHORITY,
        "provider_mutation_performed": False,
        "writer_lease_acquired": False,
        "runtime_action_performed": False,
        "promotion_or_release_action_performed": False,
        "next_boundary": _next_boundary(disposition),
    }


def _github_get_json(url: str, token: str | None) -> tuple[Any, dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "pncc-read-only-provider-selector",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload, {key.lower(): value for key, value in response.headers.items()}
    except (urllib.error.URLError, urllib.error.HTTPError, UnicodeError, json.JSONDecodeError) as exc:
        raise SelectionError("GITHUB_READ_FAILED:" + type(exc).__name__) from exc


def _next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        bits = [value.strip() for value in part.split(";")]
        if len(bits) >= 2 and bits[1] == 'rel="next"':
            return bits[0].strip()[1:-1]
    return None


def fetch_live_provider_truth(repository: str, default_branch: str, token: str | None) -> tuple[str, list[dict[str, Any]]]:
    encoded_branch = urllib.parse.quote(default_branch, safe="")
    commit_url = f"https://api.github.com/repos/{repository}/commits/{encoded_branch}"
    commit, _ = _github_get_json(commit_url, token)
    if not isinstance(commit, dict) or SHA40.fullmatch(str(commit.get("sha", ""))) is None:
        raise SelectionError("GITHUB_DEFAULT_HEAD_INVALID")
    default_head = str(commit["sha"])

    issues: list[dict[str, Any]] = []
    url: str | None = f"https://api.github.com/repos/{repository}/issues?state=open&per_page=100&sort=created&direction=asc"
    pages = 0
    while url:
        pages += 1
        if pages > 20:
            raise SelectionError("GITHUB_ISSUE_PAGINATION_LIMIT")
        page, headers = _github_get_json(url, token)
        if not isinstance(page, list):
            raise SelectionError("GITHUB_ISSUES_RESPONSE_INVALID")
        issues.extend(page)
        url = _next_link(headers.get("link"))
    return default_head, issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--live-github", action="store_true")
    parser.add_argument("--issues-json")
    parser.add_argument("--default-head-sha")
    parser.add_argument("--output")
    args = parser.parse_args()

    validate_readiness_guard(ROOT)
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    if args.live_github:
        head, issues = fetch_live_provider_truth(args.repository, args.default_branch, os.environ.get("GITHUB_TOKEN"))
    else:
        if not args.issues_json or not args.default_head_sha:
            raise SelectionError("OFFLINE_PROVIDER_INPUT_REQUIRED")
        payload = load_json(Path(args.issues_json))
        issues = payload if isinstance(payload, list) else payload.get("issues")
        head = args.default_head_sha

    result = select_from_provider_issues(
        issues,
        repository=args.repository,
        default_branch=args.default_branch,
        default_head_sha=head,
        observed_at=observed_at,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SelectionError as exc:
        print("READ_ONLY_PROVIDER_WORK_UNIT_SELECTION=BLOCKED")
        print("ERROR=" + str(exc))
        print("MUTATION_AUTHORITY=" + MUTATION_AUTHORITY)
        raise SystemExit(2)
