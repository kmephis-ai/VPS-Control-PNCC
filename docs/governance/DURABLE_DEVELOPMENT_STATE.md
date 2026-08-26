# PNCC Durable Development State v2

Status: implementation contract for `PIPE-WU-001` + `PIPE-WU-002`.

## Purpose

This layer makes PNCC development resumable across independent AI sessions without treating chat history as source of truth. It defines machine-readable contracts for Current Work Unit, Session Checkpoint, Writer Lease, Provider Truth Snapshot, Runtime Ledger and Evidence Index, plus an executable fail-closed resume decision.

It does **not** copy ADWF Core into PNCC and grants no product/runtime mutation authority.

## Truth hierarchy

At every session start:

1. read mandatory PNCC governance (`AGENTS.md`, `SECURITY.md`, accepted ADRs);
2. discover the provider-visible active Work Unit marker;
3. fetch fresh GitHub repository/branch/PR/check state;
4. load durable Work Unit, Writer Lease and Session Checkpoint records;
5. reconcile stored state against fresh provider truth;
6. consult trusted private runtime evidence only when `runtime_required=true`;
7. select exactly one permitted next boundary or fail closed.

Fresh provider/runtime facts override stale planning/checkpoint state. A checkpoint is a resume hint, never authority.

## Self-reference rule

A tracked file cannot truthfully embed the SHA of the commit that contains that same file as its canonical “current HEAD”; changing the file changes the commit SHA.

Therefore durable records distinguish:

- immutable/historical `base_sha` and evaluated `subject_sha`;
- provider-visible Work Unit identity and writer branch;
- fresh branch HEAD / PR / check truth resolved from GitHub at reconciliation time;
- schemas/examples that define the contract but are not live provider truth.

## Provider-visible Work Unit marker

An active Issue may expose one parseable marker:

```text
<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-002 state=ACTIVE conflict_domain=pipeline-durable-state branch=agent/example base=<40hex> runtime_required=false -->
```

Exactly one marker is accepted. It identifies the active planning/writer domain without pretending to know the future commit SHA.

## Contracts

### Current Work Unit

Carries goal, exact base, optional evaluated subject SHA, branch/PR, conflict domain, state, scope/forbidden scope, required checks, runtime requirement, failure classification, blockers, exit criteria, evidence references and next natural boundary.

`VERIFYING` and `DONE` require exact `subject_sha`. `DONE` additionally requires evidence and forbids unresolved blockers/failure classification.

### Writer Lease

Binds one writer to one Work Unit and conflict domain using:

- UUID lease identity;
- Work Unit ID;
- conflict domain;
- holder identity;
- exact base SHA;
- writer branch;
- monotonically positive generation;
- `ACTIVE|RELEASED|EXPIRED` state;
- acquired/heartbeat/expiry timestamps with timezone.

For resume, the lease must be ACTIVE, unexpired, not future-heartbeated, and match Work Unit ID, conflict domain, exact base and branch. The executing session must also match `holder`. A foreign, expired or conflicting lease blocks; it is never silently stolen.

### Provider Truth Snapshot

Represents fresh GitHub facts for a specific observation:

- repository/default branch and default-branch HEAD;
- writer branch existence and exact branch HEAD;
- PR identity/state;
- check states;
- observation timestamp.

The snapshot is input evidence to reconciliation, not a long-lived replacement for GitHub.

### Session Checkpoint

Records the exact subject previously observed plus a provider snapshot, runtime status, blockers, evidence references and next boundary. `reconcile_checkpoint()` compares it with fresh provider truth. Unknown/moved head, branch/PR mismatch, stale PR state or changed stored check result blocks resume.

### Runtime Ledger

GitHub-hosted engineering evidence may record `NOT_REQUIRED` or `NOT_VERIFIED`. `RUNTIME_VERIFIED` is accepted only from `PRIVATE_RUNTIME` and only with evidence references.

### Evidence Index

Every evidence entry binds to a Work Unit and exact subject SHA and carries a SHA-256 digest. GitHub-hosted evidence is forbidden from supporting `RUNTIME_VERIFIED`.

## Executable resume decision

`resume_decision.py` accepts Work Unit, Checkpoint, Writer Lease, fresh Provider Truth, current holder identity and current time.

Decision order:

```text
invalid contract / non-resumable Work Unit / blockers
    → BLOCK
foreign / expired / conflicting lease
    → BLOCK
unknown or moved provider branch/head
    → BLOCK
stale checkpoint vs fresh provider truth
    → BLOCK
required check FAILURE
    → BLOCK
required check PENDING or MISSING
    → WAITING_PROVIDER_CHECKS
runtime_required=true without RUNTIME_VERIFIED private evidence
    → WAITING_RUNTIME
all identities/checks/lease/provider facts consistent
    → RESUME_ALLOWED + exact next_natural_boundary
```

Waiting is not PASS. `WAITING_PROVIDER_CHECKS` and `WAITING_RUNTIME` preserve the Work Unit without fabricating completion.

## Natural-boundary checkpoint protocol

At each natural boundary, persist only already-supported facts:

- evaluated subject SHA;
- writer branch and PR;
- provider check snapshot;
- lease identity/state/heartbeat;
- failure classification/blockers;
- evidence references;
- runtime status when applicable;
- exact next executable action or waiting condition.

On the next session, fetch provider truth again before any mutation. Never resume solely because the stored checkpoint says PASS.

## Execution plane

All validation in Wave 1 is reproducible and runs in GitHub-hosted CI. The owner/private Windows machine is not ADWF CI and is not required for these Work Units.

Physical PNCC behavior remains a separate Runtime Truth plane. `CI VERIFIED != RUNTIME VERIFIED`.
