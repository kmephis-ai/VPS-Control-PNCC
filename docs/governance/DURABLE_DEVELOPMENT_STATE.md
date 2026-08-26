# PNCC Durable Development State v1

Status: implementation contract for `PIPE-WU-001`.

## Purpose

This layer makes PNCC development resumable across AI sessions without treating chat history as source of truth. It defines machine-readable contracts for a Work Unit, Session Checkpoint, Runtime Ledger and Evidence Index.

It does **not** copy ADWF Core into PNCC and it does not grant product/runtime mutation authority.

## Truth hierarchy

At session start, resolve truth in this order:

1. mandatory PNCC governance (`AGENTS.md`, `SECURITY.md`, accepted ADRs);
2. fresh GitHub/provider repository, branch, PR and check state;
3. trusted private runtime evidence when the Work Unit requires runtime qualification;
4. stored Work Unit/checkpoint/ledger records.

A stored checkpoint is a resume hint, not authority. If its recorded subject SHA, branch, PR state or checks disagree with fresh provider truth, resume blocks until the contradiction is classified.

## Self-reference rule

A tracked repository file cannot truthfully embed the SHA of the commit that contains that same file as its own canonical “current HEAD”; changing the file changes the commit SHA.

Therefore v1 contracts separate:

- exact `base_sha` and evaluated/historical `subject_sha` fields in records;
- current provider HEAD, PR and checks resolved at reconciliation time;
- repository schemas/examples, which define the contract but are not live provider truth.

This prevents a stale checkpoint from masquerading as current state.

## Contracts

### Current Work Unit

Carries goal, exact base, optional evaluated subject SHA, writer branch/PR identity, conflict domain, state, scope/forbidden scope, required checks, runtime requirement, failure classification, blockers, exit criteria, evidence references and next natural boundary.

`VERIFYING` and `DONE` require an exact `subject_sha`. `DONE` additionally requires evidence and forbids unresolved blockers/failure classification.

### Session Checkpoint

Records the exact subject it observed plus a provider snapshot. `reconcile_checkpoint()` compares it with fresh provider facts. Unknown/moved head, branch or PR mismatch, stale PR state, or changed check result fails closed.

### Runtime Ledger

GitHub-hosted engineering evidence may record `NOT_REQUIRED` or `NOT_VERIFIED`. `RUNTIME_VERIFIED` is accepted only from `PRIVATE_RUNTIME` and only with evidence references.

### Evidence Index

Every evidence entry binds to a Work Unit and exact subject SHA and carries a SHA-256 digest. A GitHub-hosted evidence entry is forbidden from supporting the claim `RUNTIME_VERIFIED`.

## Session start

```text
Read mandatory governance
→ fetch fresh main/branch/PR/check state
→ load Work Unit/checkpoint/ledgers if present
→ reconcile checkpoint against provider truth
→ BLOCK on stale/unknown/contradictory state
→ otherwise resume from next_natural_boundary
```

## Natural-boundary checkpoint

Persist only facts already supported by provider/runtime evidence: evaluated subject SHA, branch/PR, check snapshot, blockers, evidence references and the next executable boundary. On the next session, re-read provider truth before any mutation.

## Execution plane

All validation in this Work Unit is reproducible and runs in GitHub-hosted CI. The owner/private Windows machine is not ADWF CI and is not required here.

Physical PNCC behavior remains a separate runtime truth plane. `CI VERIFIED != RUNTIME VERIFIED`.
