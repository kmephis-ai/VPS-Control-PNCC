# PNCC Target Development Pipeline

- Status: Target architecture
- Tracking: #6 (`PIPE-001 — PNCC Autonomous Development Pipeline`)
- Decision authority: `docs/adr/0002-durable-ai-managed-development-pipeline.md`

## 1. Purpose

Define the target engineering system for developing PNCC with higher quality, longer effective continuity across AI sessions, deterministic evidence and progressively greater autonomy without weakening security, runtime truth or owner authority.

The target is not a single long-running chat. The target is a **durable development control loop** that can survive session termination, model changes, agent handoff and temporary execution-node unavailability.

## 2. Non-goals

This architecture does not:

- weaken `1080 = RESERVE_MANUAL / MANUAL_ONLY`;
- mutate or rewrite immutable V6.3.1;
- treat GitHub-hosted CI as proof of physical network behavior;
- place secrets, DPAPI blobs, private topology or unsanitized runtime evidence in public Git;
- attach an untrusted public self-hosted runner to the home/LAN environment;
- authorize product mutation from validator/harness/environment failures;
- require all roadmap items to exist as Issues in advance.

## 3. Sources of truth

1. **Public GitHub — Product / Engineering Truth**
   - source, schemas, tests, workflows, ADRs, sanitized examples, release metadata.
2. **Local PNCC Data — Instance Configuration Truth**
   - private profiles, DPAPI material, owner-specific values, local runtime state.
3. **Real Windows / Keenetic / VPS nodes — Runtime Truth**
   - authoritative physical behavior and runtime qualification.

`CI VERIFIED != RUNTIME VERIFIED`.

## 4. Authority hierarchy

Mandatory constraints:

1. `AGENTS.md`
2. `SECURITY.md`
3. accepted ADRs

Planning/execution state:

4. target architecture
5. roadmap
6. Current Work Unit
7. Runtime / Evidence / Session ledgers

Factual state:

8. GitHub provider state
9. CI/provider results
10. trusted runtime evidence

Fresh factual state overrides stale planning/checkpoint state. Nothing overrides mandatory security/runtime invariants without an explicit accepted governance change.

## 5. Target control loop

```text
Human Intent
    ↓
ADWF Consumer Project Pack
    ↓
Planner / Policy Resolution
    ↓
AI-sized Work Unit
    ↓
Writer Lease
    ↓
Implementation
    ↓
FAST CI
    ↓
DEEP CI
    ↓
Candidate Artifact + Manifest + Provenance
    ↓
Trusted Runtime Qualification
    ↓
Failure Classification / Promotion Decision
    ↓
Runtime + Evidence Ledger
    ↓
Session Checkpoint
    ↓
Next Work Unit
```

## 6. Work Unit model

Every mutating development action belongs to one active Work Unit.

Minimum fields:

```yaml
schema_version: 1
work_unit_id: PIPE-WU-001
goal: Durable Development State Foundation
base_sha: <exact git sha>
head_sha: <exact git sha or null before mutation>
branch: <writer branch>
pr: <number or null>
conflict_domain: governance-pipeline
state: READY|ACTIVE|BLOCKED|VERIFYING|DONE|SUPERSEDED
scope: []
forbidden_scope: []
required_checks: []
runtime_required: false
failure_class: null
blockers: []
exit_criteria: []
evidence_refs: []
next_natural_boundary: <machine-readable action/state>
```

Rules:

- exact SHA identity is mandatory after mutation;
- scope expansion requires an explicit Work Unit update/reclassification;
- `DONE` requires evidence satisfying the Work Unit contract;
- planning text alone cannot produce `DONE`;
- stale Work Units must fail closed during resume/reconciliation.

## 7. Writer lease

One writer is allowed per overlapping conflict domain.

A writer lease records at minimum:

```text
lease_id
work_unit_id
conflict_domain
holder
base_sha
branch
acquired_at
expires_or_heartbeat
state
```

Read-only discovery may run concurrently. Mutations in non-overlapping domains may later run concurrently after durable lease enforcement is proven.

## 8. Session continuity

### 8.1 Session start

```text
Discover repository/provider truth
→ load Consumer Project Pack
→ load Current Work Unit
→ load latest checkpoint/ledgers
→ fetch exact branch/PR/CI state
→ reconcile stored state with provider truth
→ detect stale or contradictory state
→ resume from next valid natural boundary
```

### 8.2 Session checkpoint

At every natural boundary, persist enough state for an independent next session:

- repository/base/head SHA;
- branch and PR identity;
- active Work Unit and lease;
- CI run/check status;
- failure classification;
- blockers;
- evidence references and hashes;
- decisions made during the Work Unit;
- exact next executable action or waiting condition.

A checkpoint is not truth by itself. Resume always reconciles it against fresh provider/runtime evidence.

## 9. Development state machine

```text
PLANNED
  ↓
READY
  ↓
ACTIVE
  ↓
ENGINEERING_VERIFYING
  ↓
ENGINEERING_VERIFIED
  ↓
CANDIDATE_BUILT          (when artifact/runtime work is required)
  ↓
RUNTIME_PENDING
  ↓
RUNTIME_VERIFYING
  ↓
RUNTIME_VERIFIED
  ↓
PROMOTION_ELIGIBLE
  ↓
DONE
```

Failure paths enter classified blocked/repair states rather than automatically creating a new product candidate.

## 10. Failure classification gate

Recognized top-level classes:

- `VALIDATOR_DEFECT`
- `HARNESS_DEFECT`
- `ENVIRONMENT_OR_BASELINE_BLOCKER`
- `PRODUCT_DEFECT`

Mutation authority:

```text
VALIDATOR_DEFECT                 → validator scope only
HARNESS_DEFECT                   → harness scope only
ENVIRONMENT_OR_BASELINE_BLOCKER  → environment/evidence/baseline only
PRODUCT_DEFECT                   → product mutation may be authorized
```

The classifier must preserve evidence for why the class was selected. Retry without classification is not the default recovery mechanism.

## 11. CI architecture

### 11.1 FAST CI

Target duration: short feedback loop.

Includes:

- repository/public integrity;
- syntax/AST/encoding;
- fixed contracts;
- unit tests;
- schema validation;
- narrow static/security checks.

### 11.2 DEEP CI

Includes:

- full Pester suite;
- component tests;
- integration simulation with controlled mocks/fixtures;
- packaging checks;
- expanded security/supply-chain checks;
- regression suites for historical PNCC failure modes.

### 11.3 Concurrency semantics

- ordinary PR engineering checks: latest relevant head wins where safe;
- candidate/runtime qualification: serialize; never qualify overlapping candidates against one physical runtime baseline;
- no arbitrary contributor code on trusted home infrastructure.

## 12. Test pyramid

```text
L0  Repository integrity
L1  Syntax / static analysis
L2  Unit tests
L3  Contract tests
L4  Component tests
L5  Integration simulation
L6  Windows Runtime Qualification
L7  Network Runtime Qualification
L8  Promotion gate
```

Priority regression coverage includes:

- PowerShell StrictMode hazards;
- empty/single/multiple collection normalization;
- null handling;
- process ownership and PID reuse;
- dirty process baseline detection/cleanup;
- watchdog identity/lifecycle;
- PuTTY host-key fail-closed behavior;
- `-pwfile` transport contract;
- DPAPI persistence boundaries;
- `1080` MANUAL_ONLY invariant;
- `1081` PRIMARY_AUTO lifecycle;
- Proxifier cleanup/resource leak behavior;
- immutable V6.3.1 rollback identity.

## 13. Candidate Artifact Truth

Runtime qualification must operate on a deterministic candidate produced from an exact engineering revision.

Target candidate bundle:

```text
PNCC-Candidate.zip
├── candidate-manifest.json
├── sha256sums.txt
├── source-commit.txt
├── test-summary.json
└── provenance.json
```

The manifest identifies at minimum:

- source commit SHA;
- artifact SHA-256;
- build workflow/run identity;
- tool/runtime versions relevant to reproducibility;
- required engineering checks and their state.

Where GitHub capabilities and repository policy permit, artifact attestation/provenance should be added without making it a substitute for trusted runtime evidence.

## 14. Runtime Qualification

Runtime qualification is a separate trusted execution plane.

Expected progression:

```text
ENGINEERING_VERIFIED
→ CANDIDATE_BUILT
→ RUNTIME_PENDING
→ WINDOWS_VERIFIED
→ NETWORK_VERIFIED
→ ROLLBACK_VERIFIED (when required)
→ RUNTIME_VERIFIED
→ PROMOTION_ELIGIBLE
```

Runtime evidence must identify:

```text
candidate_sha256
source_commit_sha
windows_version
powershell_version
validation_lab_version
runtime_agent_version
qualification_timestamp
exit_codes
failure_classification
evidence_bundle_sha256
```

Private/raw evidence remains outside public Git unless explicitly sanitized.

## 15. Evidence model

Evidence is indexed, immutable-by-reference and attributable to an exact Work Unit/candidate.

Minimum evidence index entry:

```yaml
evidence_id: <stable id>
work_unit_id: <id>
kind: CI|STATIC|UNIT|COMPONENT|RUNTIME|NETWORK|ROLLBACK|DECISION
subject_sha: <source/candidate identity>
producer: <workflow/agent/runtime tool>
created_at: <timestamp>
result: PASS|FAIL|BLOCKED
artifact_hash: <hash when applicable>
private_location_ref: <non-secret opaque reference when applicable>
sanitation_state: PRIVATE|SANITIZED_PUBLIC
```

Human paraphrase is not authoritative evidence when machine-verifiable evidence exists.

## 16. ADWF integration

PNCC is an ADWF consumer.

ADWF may provide, through a version-pinned Consumer Project Pack:

- Work Unit schema/policy;
- writer lease semantics;
- resume/reconciliation protocol;
- generic CI/evidence contracts;
- autonomy/risk boundaries;
- orchestration and Human-by-Exception rules.

PNCC owns:

- product-specific contracts;
- network/runtime invariants;
- PNCC test suites;
- candidate/runtime qualification semantics;
- PNCC-specific adapters and evidence interpretation.

Do not copy the ADWF implementation into PNCC.

## 17. Human-by-Exception boundary

The target is not unrestricted autonomy.

Automation may continue without owner interruption when all of the following hold:

- active Work Unit and writer lease are valid;
- changes remain in allowed scope;
- required checks/evidence are machine-verifiable;
- no security/runtime invariant is weakened;
- no new sensitive credential/topology exposure is introduced;
- no decision crosses an owner-required risk/authority boundary.

Owner involvement remains required for explicitly governed high-risk decisions, policy weakening, sensitive infrastructure changes or other boundaries defined by ADWF/PNCC governance.

## 18. Maturity levels

| Level | Name | Definition |
|---|---|---|
| L0 | Chat-driven | State primarily lives in conversation/manual artifacts. |
| L1 | Governed GitHub | PR/ruleset/CI/invariants exist; continuity remains mostly manual. |
| L2 | Durable State | Work Unit, checkpoint, ledger and reconciliation are machine-readable. |
| L3 | Tested Engineering Pipeline | Behavioral test pyramid and classified recovery are routine. |
| L4 | Artifact + Runtime Truth | Exact candidate/provenance/runtime evidence lifecycle is enforced. |
| L5 | Autonomous Work Units | Agents can plan/execute/repair/resume bounded Work Units with minimal owner input. |
| L6 | Human-by-Exception | Routine engineering lifecycle continues autonomously; owner participates at defined exception boundaries. |

Current estimated maturity: **L1**.

Target maturity: **L6**.

## 19. First implementation boundary

After this architecture is accepted on `main`, the next pipeline implementation Work Unit is:

`PIPE-WU-001 — Durable Development State Foundation`

Its scope is limited to:

- Current Work Unit schema;
- Session Checkpoint schema;
- Runtime Ledger schema;
- Evidence Index schema;
- provider-truth reconciliation/stale-state rules.

It must not simultaneously introduce auto-merge, merge queue, large product features or unrelated runtime subsystems.
