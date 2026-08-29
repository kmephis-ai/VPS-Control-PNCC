# Provider-Truth Work Unit Selection

## Purpose

Wave 5 begins with a deliberately narrow capability: PNCC may **read fresh GitHub provider truth and deterministically identify the nearest hosted-executable governed Work Unit**.

Selection is not ownership. Selection does not acquire a writer lease and grants no mutation authority.

## Existing durable state remains authoritative

WU-079 does not replace the Wave 1 durable-development-state model:

- `CURRENT_WORK_UNIT` remains the materialized work contract;
- `PROVIDER_TRUTH_SNAPSHOT` remains the provider-state contract used by resume/reconciliation;
- `WRITER_LEASE` remains the exclusive writer-ownership contract;
- fresh provider truth still overrides stored/checkpoint state;
- private Runtime Truth still cannot be manufactured by GitHub-hosted CI.

## Two-phase Work Unit lifecycle

### Phase A — Issue intake marker

A governed Issue can exist before a branch is materialized. Its canonical marker is:

```text
<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-NNN state=READY|ACTIVE conflict_domain=<domain> base=<40-hex-main-sha> runtime_required=true|false -->
```

`branch=<branch>` is optional at intake and remains accepted for legacy/already-materialized markers.

The marker is only a compact provider-discovery identity. It is not a substitute for the full `CURRENT_WORK_UNIT` contract.

### Phase B — Materialized Work Unit

After a separately authorized claim/materialization boundary, the full Work Unit must carry branch, subject SHA, checks, scope, blockers, evidence and next-boundary data according to the existing durable-state contract. Writer ownership is then governed separately by `WRITER_LEASE`.

WU-079 does not implement Phase B mutation.

## Read-only selection rules

The selector:

1. reads the current default-branch head from GitHub;
2. reads all currently open Issues using GET-only provider access;
3. ignores Pull Requests returned by the GitHub Issues endpoint;
4. ignores open Issues without the canonical `PNCC-WORK-UNIT` marker (for example umbrella trackers, provenance residuals and provider-admin boundaries);
5. fails closed on malformed or duplicate open Work Unit markers;
6. prevents concurrent selection of duplicate conflict domains;
7. classifies `runtime_required=true` as waiting for private runtime rather than hosted-executable;
8. rejects a Work Unit whose marker base no longer equals fresh default-branch head;
9. treats only `READY` or `ACTIVE`, non-runtime, exact-base Work Units as candidates;
10. deterministically chooses the lowest GitHub Issue number when multiple eligible candidates exist.

A lack of eligible candidates is a valid result: `NO_EXECUTABLE_WORK_UNIT`. The selector must never invent work from an umbrella or residual Issue.

## Mandatory default deny

The selector has no authority to:

- create/update/delete branches;
- acquire/heartbeat/release writer leases;
- edit/comment/close/label/assign Issues or PRs;
- create or merge PRs;
- execute runtime/tunnel actions;
- grant Runtime Authority;
- create promotion/tag/release state;
- mutate rulesets/policies;
- adopt the ADWF managed `.adwf` surface.

The external binding remains:

```text
mutation_authority=NONE_BINDING_IS_PROOF_ONLY
```

## Provider permissions

The live hosted selector requires only:

```yaml
permissions:
  contents: read
  issues: read
```

Its GitHub API path is GET-only.

## Next boundary

After read-only selection is proven, a separate Work Unit may design a default-deny writer-lease/claim transaction. That transaction is the first point where provider mutation/ownership authority becomes relevant and must not be inferred from WU-079 success.
