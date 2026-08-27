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
- required durable-state hosted checks all SUCCESS on that exact boundary;
- durable-state v2 tests: 23/23 PASS on the candidate that produced the L2 baseline.

### State

`COMPLETE / L2_DURABLE_STATE`

---

## Wave 2 — Quality and Test Pyramid

### Goal

Move from mostly static/public-safety validation to executable behavioral quality gates.

### Delivered

- Pester foundation and test conventions;
- executable fail-closed failure classifier;
- PowerShell 5.1 StrictMode and 0/1/N collection regressions;
- tunnel and credential safety fixture regressions;
- deterministic FAST CI;
- isolated deterministic DEEP CI;
- exact sanitized-fixture provenance with Git-object/EOL reconciliation semantics;
- safe DEEP concurrency semantics;
- process identity/PID-reuse/dirty-baseline evidence and cleanup-authority model.

### Completed Work Units

- #19 — `PIPE-WU-003`: Pester foundation + fail-closed failure classification; protected merge `43bad8547631651d9fb0581f6f57d1d88da3feae`.
- #21 — `PIPE-WU-004`: PS5.1 StrictMode/collection normalization regressions; protected merge `b52be81e44ad8690c78ddb66cb58201442a3be0d`.
- #23 — `PIPE-WU-005`: tunnel/credential safety regressions; protected merge `8af94a0d6432331e693f188925264ef605885fb7`.
- #25 — `PIPE-WU-006`: DEEP CI + sanitized fixture provenance; protected merge `327b46730b77a9742f1179b4c02e03238619e38f`.
- #27 — `PIPE-WU-007`: process identity + dirty baseline evidence; protected merge `90a95b812eecdd72a4f1bbd9b638414e90baf6df`.

### Exit evidence

Exact Wave 2 exit main `90a95b812eecdd72a4f1bbd9b638414e90baf6df`:

- `repo-integrity` SUCCESS;
- `powershell-static` SUCCESS;
- `truth-contract` SUCCESS;
- `adwf-binding` SUCCESS;
- `pipeline-state` SUCCESS;
- `quality-fast` SUCCESS;
- `quality-deep` SUCCESS;
- PSScriptAnalyzer Error/Warning findings: 0 across `.pncc-dev/quality`;
- FAST Pester: 54/54 PASS;
- DEEP sanitized fixture provenance: exact tree `2a6c0027a195e91640ec2a6e38220a9fac372368`, 32/32/32 verified, exactly 3 explicit EOL reconciliations;
- DEEP Pester: 12/12 PASS;
- process identity rule: PID alone is never ownership proof;
- dirty baselines containing foreign/ambiguous managed processes retain cleanup authority `NONE`.

### Physical-runtime deferral

Watchdog stop/restart correctness, lingering Proxifier descendants and real process/resource leak behavior require observing physical Windows process state. Hosted synthetic tests cannot prove those effects without conflating simulation with runtime truth.

Those domains are therefore deliberately deferred to Wave 4 trusted Runtime Qualification, where the existing failure-classification and process-identity contracts can be consumed against real evidence.

This deferral is not a PASS claim for physical lifecycle behavior.

### State

`COMPLETE / L3_TESTED_ENGINEERING_PIPELINE`

---

## Wave 3 — Candidate Artifact Truth

### Goal

Bind every future runtime-qualified candidate to an exact source revision and deterministic artifact identity before trusted runtime qualification begins.

### Active Work Unit

#29 — `PIPE-WU-008 — Candidate Artifact Truth Contract Foundation`.

Exact base: `90a95b812eecdd72a4f1bbd9b638414e90baf6df`.

The Work Unit establishes the manifest/schema/validator/evidence contract only. It does not build RC14.39, does not create a deployable artifact and does not treat the public sanitized RC14.38 fixture as a runtime candidate.

### Contract foundation

The v1 Candidate Artifact Truth contract binds:

- exact source commit SHA;
- artifact filename, SHA-256 and byte size;
- build workflow/run/attempt/job/timestamp identity;
- tool/runtime versions relevant to reproducibility;
- required engineering checks, each terminal SUCCESS on the exact same source SHA;
- provenance/source identity semantics;
- runtime qualification state.

Hosted contract output must remain:

```text
runtime.qualification_state = NOT_VERIFIED
runtime.evidence_ref = null
runtime.promotion_eligible = false
provenance.runtime_authority = false
```

The synthetic example is explicitly `SYNTHETIC_TEST_FIXTURE`. A future `RUNTIME_CANDIDATE` must use exact source/build-output semantics; sanitized RC14.38 source identity/path is rejected.

### Current core evidence

On executable-core HEAD `f2ed1bd0179544cf4bffe92a002422406a7007a9`:

- new `candidate-artifact-truth` hosted gate SUCCESS;
- validator regression suite: 21/21 PASS;
- synthetic manifest validates with `RUNTIME=NOT_VERIFIED` and `PROMOTION_ELIGIBLE=false`;
- all pre-existing hosted quality/truth/pipeline contexts remain SUCCESS.

This core evidence is not the final Work Unit evidence; protected merge and exact post-merge certification remain required.

### Deliverables across Wave 3

- candidate-manifest contract and semantic validator;
- candidate builder once exact governed non-sanitized build inputs exist;
- deterministic artifact SHA-256 and size capture;
- exact source commit identity;
- engineering test summary bound to source SHA;
- provenance metadata;
- retained GitHub Actions artifact where appropriate;
- artifact attestation/provenance where supported and reviewed.

### Exit criteria

- no runtime qualification can start without exact candidate SHA-256;
- candidate references exact source SHA and CI/build identity;
- rebuilt/replaced artifacts cannot silently inherit prior runtime evidence;
- public sanitized fixture cannot be elevated into runtime candidate authority;
- promotion decisions are traceable to exact candidate identity;
- hosted candidate creation cannot claim runtime verification.

### State

`ACTIVE / CONTRACT_FOUNDATION`

---

## Wave 4 — Runtime Qualification Automation

### Goal

Turn trusted Windows/network qualification into a deterministic, machine-verifiable lifecycle separate from public PR execution.

### Deliverables

- typed Runtime Qualification request/result contract;
- trusted Windows Runtime Test Agent integration;
- environment/baseline preflight;
- physical process ownership/dirty-baseline verification;
- watchdog lifecycle verification;
- Proxifier descendant/cleanup/resource-leak verification;
- Windows qualification;
- network qualification;
- rollback qualification where required;
- private evidence bundle with hash/index;
- sanitized-public evidence export path when needed.

### Exit criteria

- `ENGINEERING_VERIFIED` cannot be confused with `RUNTIME_VERIFIED`;
- qualification always identifies exact candidate/source/runtime versions;
- dirty baseline and environment blockers are classified without mutating product;
- real lifecycle cleanup is authorized only for positively owned processes;
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
L2 Durable State
 ↓
L3 Tested Engineering Pipeline ← current verified maturity / Wave 2 complete
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
- Do not manufacture runtime evidence from hosted simulation.
- Do not build a runtime candidate from the sanitized RC14.38 fixture.
- Do not conflate candidate identity with runtime qualification.
- Do not weaken fixed tunnel, credential, host-key or V6.3.1 contracts.
- Prefer generic capabilities upstream in ADWF and PNCC-specific policy/tests in this repository.
- Reassess the roadmap at natural boundaries using fresh provider/runtime truth.
