# PNCC Pipeline Roadmap

- Status: Active rolling-wave roadmap
- Tracking: #6 (`PIPE-001 — PNCC Autonomous Development Pipeline`)
- Target architecture: `docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md`

## Operating rule

This roadmap defines direction and exit criteria. It is not runtime evidence and must not be treated as proof of completion.

Only the nearest executable AI-sized Work Unit should be materialized in detail. Actual GitHub/CI/runtime truth overrides stale roadmap state.

## Wave 0 — Public migration and governance baseline

### Goal

Establish a secret-safe public engineering repository with explicit public/private/runtime boundaries, mandatory invariants and required hosted CI checks.

### Existing evidence/state

The repository contains the public bootstrap, migration safety contract, sanitized RC14.38 migration snapshot, hosted `public-safety` CI and active main ruleset.

Residual provider-admin and migration/provenance/licensing items remain tracked separately and must not be hidden by later pipeline maturity claims.

### State

`BASELINE_ESTABLISHED / RESIDUAL_ITEMS_TRACKED`

---

## Wave 1 — Durable Development State

### Goal

Make PNCC development independently resumable across ChatGPT/Codex/agent sessions without reconstructing state from conversation history.

### Delivered

- Current Work Unit schema;
- Session Checkpoint schema;
- Runtime Ledger schema;
- Evidence Index schema;
- Writer Lease contract;
- Provider Truth Snapshot contract;
- stale-state/provider-truth reconciliation rules;
- provider-visible Work Unit marker parsing;
- natural-boundary checkpoint/resume protocol;
- executable `BLOCK` / `WAITING_PROVIDER_CHECKS` / `WAITING_RUNTIME` / `RESUME_ALLOWED` decision model.

### Evidence

- #8 `PIPE-WU-001 — Durable Development State Foundation`;
- #17 `PIPE-WU-002 — Writer Lease + Resume Decision`;
- exact post-merge L2 baseline: `2014d84a621d19b9ea5fc82b4e254e238c735c2b`;
- `repo-integrity`, `powershell-static`, `truth-contract`, `adwf-binding`, `pipeline-state` all SUCCESS on that exact SHA;
- durable-state v2 tests: 23/23 PASS on the candidate that produced the L2 baseline.

### State

`COMPLETE / L2_DURABLE_STATE`

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

### Completed Work Units

- #19 — `PIPE-WU-003`: Pester foundation + fail-closed failure classification; protected merge `43bad8547631651d9fb0581f6f57d1d88da3feae`.
- #21 — `PIPE-WU-004`: PS5.1 StrictMode/collection normalization regressions; protected merge `b52be81e44ad8690c78ddb66cb58201442a3be0d`.
- #23 — `PIPE-WU-005`: tunnel/credential safety fixture regressions; protected merge `8af94a0d6432331e693f188925264ef605885fb7`; FAST suite 35/35 PASS and post-merge six-context hosted certification.

### Active Work Unit

#25 — `PIPE-WU-006 — DEEP CI + Sanitized Fixture Provenance`.

Exact base: `8af94a0d6432331e693f188925264ef605885fb7`.

Scope is engineering control plane only. It introduces a separate deterministic DEEP hosted layer and exact public-fixture provenance verification using the sanitized Git tree identity plus complete per-file sanitized-import SHA-256 inventory. It does not mutate `legacy/`, product/runtime code, the private candidate, V6.3.1, or physical runtime state.

### Current engineering evidence

- FAST layer: Windows PowerShell 5.1, Pester 5.9.0, PSScriptAnalyzer 1.25.0;
- FAST behavioral floor: 35 tests;
- PSScriptAnalyzer Error/Warning findings: 0 across `.pncc-dev/quality` on the main that entered `PIPE-WU-006`;
- exact sanitized public fixture Git tree: `2a6c0027a195e91640ec2a6e38220a9fac372368`;
- sanitized-import SHA-256 manifest expected inventory: 32 files excluding the manifest itself;
- manifest semantics: exact canonical Git blobs plus explicit reversible EOL reconciliation for exactly `VPS-Control-v7.cmd`, `VPS-Control-v7-demo.cmd`, and `modules/V7-Storage.ps1`, reflecting `.gitattributes` normalization that predated snapshot import;
- DEEP behavioral floor: 12 tests;
- sanitized identity remains explicitly non-runtime-qualified.

### Exit criteria

- product, validator, harness and environment failures are distinguishable by evidence;
- historical classes of validator/harness defects have dedicated regressions;
- ordinary code changes receive fast feedback while deep gates remain deterministic and separately attributable;
- DEEP fixture/provenance failures cannot silently contaminate FAST or runtime truth;
- safe concurrency semantics prevent stale DEEP executions from becoming authoritative;
- `PRODUCT_DEFECT` is the only failure class compatible with product-scope mutation;
- unknown/ambiguous evidence retains mutation authority `NONE`.

### State

`ACTIVE / FAST_ESTABLISHED / DEEP_IN_PROGRESS`

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
L1 Governed GitHub
 ↓
L2 Durable State               ← current verified maturity
 ↓
L3 Tested Engineering Pipeline ← Wave 2 target
 ↓
L4 Artifact + Runtime Truth    ← Waves 3–4
 ↓
L5 Autonomous Work Units       ← Wave 5
 ↓
L6 Human-by-Exception          ← Wave 6 target
```

## Roadmap guardrails

- Finish the current Work Unit before expanding scope.
- Do not create a new product RC for validator/harness/environment failures.
- Do not conflate roadmap completion with runtime evidence.
- Do not weaken fixed tunnel, credential, host-key or V6.3.1 contracts.
- Prefer generic capabilities upstream in ADWF and PNCC-specific policy/tests in this repository.
- Reassess the roadmap at natural boundaries using fresh provider/runtime truth.
