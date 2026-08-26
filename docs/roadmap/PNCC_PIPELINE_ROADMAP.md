# PNCC Pipeline Roadmap

- Status: Active rolling-wave roadmap
- Tracking: #6 (`PIPE-001 — PNCC Autonomous Development Pipeline`)
- Target architecture: `docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md`

## Operating rule

This roadmap defines direction and exit criteria. It is not the runtime state of development and must not be treated as evidence of completion.

Only the nearest executable AI-sized Work Unit should be materialized in detail. Do not pre-create a large backlog of speculative Issues. Actual GitHub/CI/runtime truth overrides stale roadmap state.

## Wave 0 — Public migration and governance baseline

### Goal

Establish a secret-safe public engineering repository with explicit public/private/runtime boundaries, mandatory invariants and required hosted CI checks.

### Existing evidence/state

The repository already contains the public bootstrap, migration safety contract, sanitized RC14.38 migration snapshot, hosted `public-safety` CI and active `main` ruleset.

### Exit criteria

- public source boundary is enforced;
- required check names exist and are protected by ruleset;
- sanitized source import is established;
- product/runtime truth separation is explicit;
- remaining migration/provenance/licensing blockers are tracked rather than hidden.

### State

`IN_PROGRESS / VERIFY_EXIT_CRITERIA`

No claim is made here that all migration work is complete.

---

## Wave 1 — Durable Development State

### Goal

Make PNCC development independently resumable across ChatGPT/Codex/agent sessions without reconstructing state from conversation history.

### Deliverables

- Current Work Unit schema;
- Session Checkpoint schema;
- Runtime Ledger schema;
- Evidence Index schema;
- Writer Lease contract;
- stale-state/provider-truth reconciliation rules;
- natural-boundary checkpoint/resume protocol.

### Exit criteria

A fresh authorized AI session can, from repository/provider state and durable records:

1. identify the active Work Unit;
2. verify exact BASE/HEAD SHA, branch and PR;
3. determine current CI/blocker/failure state;
4. detect stale or contradictory checkpoint data;
5. select the exact next permitted action or waiting condition;
6. resume without requiring the previous chat transcript.

### First Work Unit

`PIPE-WU-001 — Durable Development State Foundation`

This is the next intended implementation boundary after the target architecture is accepted.

---

## Wave 2 — Quality and Test Pyramid

### Goal

Move from mostly static/public-safety validation to executable behavioral quality gates.

### Deliverables

- Pester foundation and test conventions;
- unit/contract/component layers;
- deterministic mocks/fixtures for infrastructure boundaries;
- historical regression suite;
- executable failure classifier;
- FAST CI / DEEP CI separation;
- safe CI concurrency semantics.

### Priority regression domains

- StrictMode;
- collection normalization (empty/single/multiple);
- null handling;
- process ownership/PID reuse;
- dirty baseline;
- watchdog lifecycle;
- PuTTY host-key and `-pwfile` contracts;
- DPAPI boundaries;
- 1080/1081 lifecycle invariants;
- Proxifier cleanup/resource leaks;
- V6.3.1 rollback identity.

### Exit criteria

- product, validator, harness and environment failures are distinguishable by evidence;
- historical classes of validator/harness defects have dedicated regressions;
- ordinary code changes receive fast feedback while deep gates remain deterministic;
- `PRODUCT_DEFECT` is the only failure class that may authorize product mutation.

---

## Wave 3 — Candidate Artifact Truth

### Goal

Bind every runtime-qualified candidate to an exact source revision and deterministic artifact identity.

### Deliverables

- candidate builder;
- `candidate-manifest.json`;
- SHA-256 manifest;
- source commit identity;
- engineering test summary;
- provenance metadata;
- retained GitHub Actions artifact;
- artifact attestation/provenance where supported and appropriate.

### Exit criteria

- no runtime qualification can start without exact candidate SHA-256;
- candidate references exact source SHA and CI/build identity;
- rebuilt/replaced artifacts cannot silently inherit prior runtime evidence;
- promotion decisions are traceable to exact candidate identity.

---

## Wave 4 — Runtime Qualification Automation

### Goal

Turn trusted Windows/network qualification into a deterministic, machine-verifiable lifecycle separate from public PR execution.

### Deliverables

- typed Runtime Qualification request/result contract;
- trusted Windows Runtime Test Agent integration;
- environment/baseline preflight;
- Windows qualification;
- network qualification;
- rollback qualification where required;
- private evidence bundle with hash/index;
- sanitized-public evidence export path when needed.

### Exit criteria

- `ENGINEERING_VERIFIED` cannot be confused with `RUNTIME_VERIFIED`;
- qualification always identifies exact candidate/source/runtime versions;
- dirty baseline and environment blockers are classified without mutating product;
- runtime result is machine-readable and resumable after interruption.

---

## Wave 5 — ADWF Autonomous Execution

### Goal

Allow ADWF to manage bounded PNCC engineering Work Units end-to-end using a version-pinned Consumer Project Pack.

### Deliverables

- PNCC Consumer Project Pack;
- Work Unit planner/selector integration;
- durable writer lease enforcement;
- CI inspection/classification/recovery loop;
- WAITING/blocked semantics for unavailable runtime nodes;
- automatic session handoff/resume;
- bounded parallel read-only discovery and later non-overlapping writers.

### Exit criteria

- ADWF can select and execute the nearest valid Work Unit;
- routine CI defects can be inspected/repaired/re-run without owner micro-management;
- runtime-node unavailability produces durable waiting state rather than lost progress;
- a new agent/session can resume from provider truth without manual reconstruction.

---

## Wave 6 — Human-by-Exception

### Goal

Minimize owner involvement in routine engineering while retaining explicit authority at security/runtime/policy risk boundaries.

### Candidate capabilities

- low-risk auto-merge after all required gates;
- update-branch/merge-queue strategy if parallel writers justify it;
- automatic next-Work-Unit continuation;
- periodic pipeline health/drift checks;
- bounded unattended development windows;
- owner escalation only for governed exceptions.

### Preconditions

Do not enable unattended merge/promotion merely to increase autonomy. Preconditions include mature durable state, behavioral tests, candidate artifact truth, runtime qualification and trustworthy risk classification.

### Exit criteria

Routine engineering can progress from intent to verified evidence and next Work Unit without owner intervention, while high-risk boundaries fail closed and require explicit authority.

---

## Maturity mapping

```text
L0 Chat-driven
 ↓
L1 Governed GitHub            ← current estimated state
 ↓
L2 Durable State              ← Wave 1
 ↓
L3 Tested Engineering Pipeline← Wave 2
 ↓
L4 Artifact + Runtime Truth   ← Waves 3–4
 ↓
L5 Autonomous Work Units      ← Wave 5
 ↓
L6 Human-by-Exception         ← Wave 6 target
```

## Roadmap guardrails

- Finish the current Work Unit before expanding scope.
- Do not create a new product RC for validator/harness/environment failures.
- Do not conflate roadmap completion with runtime evidence.
- Do not weaken fixed tunnel, credential, host-key or V6.3.1 contracts.
- Prefer generic capabilities upstream in ADWF and PNCC-specific policy/tests in this repository.
- Reassess the roadmap at natural boundaries using fresh provider/runtime truth.
