# PNCC Pipeline Roadmap

- Status: Active rolling-wave roadmap
- Tracking: #6 (`PIPE-001 — PNCC Autonomous Development Pipeline`)
- Target architecture: `docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md`
- Provider-truth reconciliation: 2026-08-29 after Stable v7.0.0 promotion

## Operating rule

This roadmap defines direction and exit criteria. It is not Runtime Truth by itself.

Actual GitHub provider state, machine-readable attestations and trusted physical runtime evidence override stale roadmap text. Only the nearest executable AI-sized Work Unit should be materialized in detail.

## Current verified maturity

**L4 — Artifact + Runtime Truth achieved.**

Stable v7.0.0 completed the first full governed lifecycle:

`canonical source → deterministic artifact → exact artifact identity → physical nine-scope qualification → Runtime Authority → explicit Owner promotion authorization → tag/release → verified release asset`

Authoritative Stable identity:

- state: `STABLE_COMPLETE`;
- tag: `v7.0.0`;
- tag target: `d889b52879fd21612f639cb2441fbd1ff8bc3f02`;
- release: `VPS Control PNCC v7.0.0`;
- artifact: `VPS-Control-v7.0.0.zip`;
- SHA-256: `1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599`;
- size: `700897` bytes;
- fresh Stable nine-scope reconcile: `PASS`;
- Runtime Authority: `true`;
- release asset verified: `true`.

Machine-readable authority: `.pncc-dev/attestations/stable-v7.0.0-completion.json`.

Residual public-migration provenance/licensing work and provider-admin ruleset work remain separate and must not be hidden by L4 maturity.

---

## Wave 0 — Public migration and governance baseline

### Goal
Establish a secret-safe public engineering repository with explicit public/private/runtime boundaries and hosted CI governance.

### State
`BASELINE_ESTABLISHED / RESIDUAL_ITEMS_TRACKED`

Completed: public repository bootstrap, sanitation boundary, hosted CI, protected-branch governance, canonical source admission and public/private/runtime truth separation.

Residuals remain separately tracked, especially provenance/license review and provider-admin-only ruleset improvements.

---

## Wave 1 — Durable Development State

### Goal
Make PNCC development resumable across ChatGPT/Codex/agent sessions without reconstructing state from conversation history.

### Delivered
- Work Unit and Session Checkpoint schemas;
- Runtime Ledger and Evidence Index;
- Writer Lease contract;
- Provider Truth Snapshot;
- stale-state/provider-truth reconciliation;
- natural-boundary checkpoint/resume semantics;
- executable blocked/waiting/resume decision model.

### State
`COMPLETE / L2_DURABLE_STATE`

---

## Wave 2 — Quality and Test Pyramid

### Goal
Move from static checks to executable behavioral quality gates.

### Delivered
- Pester foundation;
- fail-closed failure classifier;
- PS5.1 StrictMode and collection regressions;
- tunnel/credential safety tests;
- FAST and DEEP hosted CI;
- provenance/EOL reconciliation;
- process identity/PID-reuse/dirty-baseline contracts.

### State
`COMPLETE / L3_TESTED_ENGINEERING_PIPELINE`

---

## Wave 3 — Candidate Artifact Truth

### Goal
Bind every runtime-qualified candidate to exact governed source and deterministic artifact identity before physical qualification.

### Delivered
- canonical non-legacy Windows source under `src/windows-v7/`;
- governed candidate-source declaration and deterministic build recipe;
- Candidate Build Input readiness policy;
- deterministic candidate builder;
- Candidate Artifact Truth contract;
- exact source SHA / artifact SHA-256 / size / build identity binding;
- fail-closed prevention of sanitized legacy fixtures becoming runtime authority;
- stable artifact preservation through qualification and promotion.

### Exit evidence
Stable v7.0.0 artifact remained byte-fixed through final qualification and promotion:

`VPS-Control-v7.0.0.zip` / `1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599` / `700897` bytes.

### State
`COMPLETE / ARTIFACT_TRUTH_PROVEN`

---

## Wave 4 — Runtime Qualification Automation

### Goal
Turn trusted Windows/network qualification into a deterministic, machine-verifiable lifecycle separate from public PR execution.

### Delivered for Stable v7.0.0
- typed runtime qualification contracts and private evidence flow;
- physical Windows baseline;
- process ownership baseline;
- Watchdog lifecycle qualification;
- Proxifier descendant cleanup qualification;
- PRIMARY_AUTO 1081 qualification;
- RESERVE_MANUAL 1080 non-mutation qualification;
- credential/host-key fail-closed qualification;
- fresh network qualification;
- immutable V6.3.1 rollback identity qualification;
- final fresh nine-scope Stable reconcile;
- separate Runtime Authority grant boundary;
- separate explicit Owner release/tag promotion boundary;
- verified published release asset.

### Stable scope result
All nine Stable scopes: `PASS`.

### State
`COMPLETE / L4_ARTIFACT_RUNTIME_TRUTH`

This proves the architecture can reach trusted Stable Runtime Truth without conflating hosted CI with physical evidence. Future releases must repeat the applicable qualification lifecycle against their own exact identities; v7.0.0 evidence cannot be inherited by rebuilt/replaced artifacts.

---

## Wave 5 — ADWF Autonomous Execution

### Goal
Allow ADWF to manage bounded PNCC engineering Work Units end-to-end using exact provider truth and a version-pinned Consumer Project Pack.

### Current position
`ACTIVE / NEXT_FRONTIER`

L4 prerequisites now exist: durable state, behavioral tests, deterministic artifact identity, trusted physical Runtime Qualification, explicit authority boundaries and Stable promotion history.

### Near-term deliverables
- reconcile/update the PNCC Consumer Project Pack against post-Stable provider truth;
- Work Unit planner/selector integration;
- durable writer-lease enforcement across autonomous sessions;
- automatic exact-head CI inspection/classification/recovery loops;
- durable `WAITING_RUNTIME` semantics when the physical node is unavailable;
- automatic session handoff/resume from provider truth;
- bounded parallel read-only discovery and later non-overlapping writers;
- explicit owner escalation only at policy/security/runtime/promotion boundaries.

### Exit criteria
- ADWF can select the nearest valid PNCC Work Unit from fresh provider truth;
- routine hosted engineering work proceeds without owner micro-management;
- CI/harness defects are classified and repaired without product mutation;
- unavailable runtime nodes yield durable waiting state rather than lost progress;
- a new session can resume without reconstructing project state from chat history.

---

## Wave 6 — Human-by-Exception

### Goal
Minimize owner involvement in routine engineering while retaining explicit authority at high-risk boundaries.

### Candidate capabilities
- low-risk auto-merge only after all required exact-head gates;
- automatic next-Work-Unit continuation;
- periodic pipeline health/drift checks;
- bounded unattended development windows;
- owner escalation only for governed exceptions;
- release/runtime authority remains explicit and fail-closed where required.

### State
`PLANNED / TARGET_L6`

---

## Maturity mapping

```text
L0 Chat-driven
 ↓
L1 Governed GitHub
 ↓
L2 Durable State                 COMPLETE
 ↓
L3 Tested Engineering Pipeline   COMPLETE
 ↓
L4 Artifact + Runtime Truth       COMPLETE ← current verified maturity
 ↓
L5 Autonomous Work Units          NEXT FRONTIER / Wave 5
 ↓
L6 Human-by-Exception             TARGET
```

## Persistent guardrails

- `127.0.0.1:1081 = PRIMARY_AUTO`.
- `127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY`; PNCC never owns its automated lifecycle.
- V6.3.1 rollback SHA-256 `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e` remains immutable under the current contract.
- DPAPI at rest; PuTTY credential transport uses `-pwfile`; plaintext `-pw` is forbidden.
- Host-key verification remains fail-closed.
- `CI VERIFIED != RUNTIME VERIFIED`.
- Do not create a new product version for validator/harness/environment defects.
- Rebuilt/substituted artifacts never inherit prior Runtime Authority.
- Do not manufacture Runtime Truth from hosted simulation.
- Public repository content must remain secret/private-instance safe.
- Project-wide license selection remains deferred until provenance/dependency review is complete.
- Reassess this roadmap at each natural boundary using fresh provider/runtime truth.
