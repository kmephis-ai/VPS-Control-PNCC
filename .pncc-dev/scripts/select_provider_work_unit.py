#!/usr/bin/env python3
"""Read-only PNCC Work Unit selection from fresh GitHub provider truth.

This is an intake/selection layer only. It never acquires a writer lease and never
performs a provider mutation. Materialized CURRENT_WORK_UNIT, checkpoint, lease
and resume semantics remain authoritative after selection.
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
EXPECTED_STABLE_SHA = "1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599"
EXPECTED_ADWF_SHA = "c7e0c059a901869d6369864e98d06238484778ec"
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
    stable = load_json(root / ".pncc-dev" / "attestations" / "stable-v7.0.0-completion.json")
    binding = load_json(root / ".adwf-consumer" / "external-binding.json")

    if readiness.get("state") != "WAVE5_ADWF_PROOF_BASELINE_READY":
        raise SelectionError("WAVE5_READINESS_NOT_READY")
    consumer = readiness.get("consumer", {})
    if consumer.get("mutation_authority") != MUTATION_AUTHORITY or consumer.get("managed_surface_adopted") is not False:
        raise SelectionError("WAVE5_READINESS_AUTHORITY_DRIFT")
    safety = readiness.get("safety", {})
    forbidden_flags = (
        "autonomous_branch_mutation", "autonomous_merge", "autonomous_issue_close",
        "runtime_action_authority", "promotion_authority", "release_or_tag_authority",
        "ruleset_or_policy_mutation",
    )
    if any(safety.get(name) is not False for name in forbidden_flags):
        raise SelectionError("WAVE5_FORBIDDEN_AUTHORITY_PRESENT")
    if readiness.get("framework", {}).get("source_sha") != EXPECTED_ADWF_SHA:
        raise SelectionError("WAVE5_ADWF_PIN_DRIFT")
    if readiness.get("framework", {}).get("provider_ops_consumer_authority_granted") is not False:
        raise SelectionError("PROVIDER_OPS_AUTHORITY_UNEXPECTED")

    if stable.get("state") != "STABLE_COMPLETE" or stable.get("runtime_authority") is not True:
        raise SelectionError("STABLE_COMPLETION_NOT_PROVEN")
    if stable.get("artifact_sha256") != EXPECTED_STABLE_SHA or stable.get("fresh_nine_scope_reconcile") != "PASS":
        raise SelectionError("STABLE_IDENTITY_OR_RECONCILE_DRIFT")

    if binding.get("framework", {}).get("source_sha") != EXPECTED_ADWF_SHA:
        raise SelectionError("EXTERNAL_BINDING_ADWF_PIN_DRIFT")
    if binding.get("mutation_authority") != MUTATION_AUTHORITY:
        raise SelectionError("EXTERNAL_BINDING_MUTATION_AUTHORITY_DRIFT")


def parse_issue_intake_marker(text: str) -> dict[str, Any] | None:
    """Parse the canonical Issue intake marker.

    The Issue-intake phase may omit branch because branch materialization happens
    after provider-truth selection. A legacy/materialized marker may include it.
    """
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
        canonical.append({
            "issue": number,
            "title": str(issue.get("title") or ""),
            "marker": marker,
        })

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

    executable.sort(key=lambda item: (item["issue"], item["work_unit_id"]))
    selected = executable[0] if executable else None

    return {
        "schema_version": 1,
        "role": "READ_ONLY_PROVIDER_WORK_UNIT_SELECTION",
        "state": "READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS",
        "repository": repository,
        "default_branch": default_branch,
        "default_branch_head_sha": default_head_sha,
        "observed_at": observed_at,
        "decision": "SELECTED" if selected else "NO_EXECUTABLE_WORK_UNIT",
        "selected": selected,
        "executable_count": len(executable),
        "canonical_work_units": classified,
        "ignored_issues": sorted(ignored, key=lambda item: item["issue"]),
        "mutation_authority": MUTATION_AUTHORITY,
        "provider_mutation_performed": False,
        "writer_lease_acquired": False,
        "runtime_action_performed": False,
        "promotion_or_release_action_performed": False,
        "next_boundary": "DESIGN_DEFAULT_DENY_WRITER_LEASE_CLAIM_AUTHORITY" if selected else "WAIT_FOR_OR_MATERIALIZE_GOVERNED_WORK_UNIT",
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
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return payload, response_headers
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

    try:
        validate_readiness_guard(ROOT)
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if args.live_github:
            if args.issues_json or args.default_head_sha:
                raise SelectionError("LIVE_AND_FIXTURE_INPUTS_MUTUALLY_EXCLUSIVE")
            default_head, issues = fetch_live_provider_truth(args.repository, args.default_branch, os.environ.get("GITHUB_TOKEN"))
        else:
            if not args.issues_json or not args.default_head_sha:
                raise SelectionError("FIXTURE_INPUTS_REQUIRED")
            issues = load_json(Path(args.issues_json))
            default_head = args.default_head_sha

        result = select_from_provider_issues(
            issues,
            repository=args.repository,
            default_branch=args.default_branch,
            default_head_sha=default_head,
            observed_at=observed_at,
        )
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        if args.output:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        return 0
    except SelectionError as exc:
        result = {
            "schema_version": 1,
            "role": "READ_ONLY_PROVIDER_WORK_UNIT_SELECTION",
            "state": "BLOCKED",
            "reason": str(exc),
            "mutation_authority": MUTATION_AUTHORITY,
            "provider_mutation_performed": False,
            "writer_lease_acquired": False,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        if args.output:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
