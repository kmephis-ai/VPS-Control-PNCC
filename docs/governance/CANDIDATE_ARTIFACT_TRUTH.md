# PNCC Candidate Artifact Truth

Status: Wave 3 active — contract foundation + build-input readiness boundary.

Tracking: #6 (`PIPE-001`), #29 (`PIPE-WU-008`) and #31 (`PIPE-WU-009`).

## Purpose

Candidate Artifact Truth binds one candidate artifact identity to one exact engineering source revision and one exact engineering evidence set before trusted runtime qualification begins.

It exists to prevent three classes of false continuity:

1. a rebuilt or replaced ZIP inheriting runtime evidence from an older artifact;
2. a source revision inheriting check evidence produced for another SHA;
3. a public sanitized regression fixture being mistaken for a private/runtime-qualified candidate.

This contract is engineering truth only.

`CI VERIFIED != RUNTIME VERIFIED`.

## Wave 2 boundary

Wave 2 established deterministic hosted evidence for:

- fail-closed validator/harness/environment/product failure classification;
- Windows PowerShell 5.1 collection and StrictMode regressions;
- 1080/1081 tunnel and credential safety contracts;
- exact sanitized fixture provenance with explicit EOL reconciliation;
- process identity, PID reuse and dirty-baseline cleanup authority.

The remaining watchdog stop/restart behavior, Proxifier descendant cleanup and resource-leak behavior depend on observing real Windows processes. They are intentionally deferred to trusted Runtime Qualification rather than simulated into a false hosted-CI PASS.

Wave 2 can therefore close at `L3_TESTED_ENGINEERING_PIPELINE`; physical lifecycle correctness remains a Wave 4 responsibility.

## Contract files

- schema: `.pncc-dev/schemas/candidate-manifest.schema.json`;
- fail-closed semantic validator: `.pncc-dev/scripts/validate_candidate_manifest.py`;
- synthetic example: `.pncc-dev/examples/candidate-manifest.synthetic.json`;
- deterministic regressions: `.pncc-dev/tests/test_candidate_manifest.py`;
- hosted gate: `.github/workflows/candidate-artifact-truth.yml`.

The validator and tests use Python standard library only. The workflow installs no package and has read-only repository permissions.

## Candidate identity model

A v1 manifest binds:

- `candidate_id`;
- `artifact_role`;
- exact repository and 40-character lowercase source commit SHA;
- source ref, path and identity semantic;
- artifact basename, SHA-256 and positive byte size;
- build workflow/run/attempt/job/timestamp/builder identity;
- explicit tool/runtime version map;
- engineering checks;
- artifact provenance;
- runtime qualification state.

Artifact SHA-256 and source commit SHA are independent identities. Neither may be substituted for the other.

## Engineering-check binding

The v1 contract requires at least the current engineering set:

- `repo-integrity`;
- `powershell-static`;
- `truth-contract`;
- `adwf-binding`;
- `pipeline-state`;
- `quality-fast`;
- `quality-deep`.

Every required check must:

- be present exactly once;
- have conclusion `SUCCESS`;
- identify the exact same `subject_sha` as `source.commit_sha`.

Missing, duplicated, failed, pending, unknown or cross-SHA check evidence fails closed.

The separate `candidate-artifact-truth` job validates the manifest contract itself. It is not retroactively inserted into the v1 manifest's required engineering set because that would make the contract self-referential. A later reviewed contract version may evolve the required set.

## Artifact roles

### `SYNTHETIC_TEST_FIXTURE`

A synthetic fixture exists only to exercise the contract.

It must use:

- `source.identity_semantic = SYNTHETIC_SOURCE`;
- a source path under `.pncc-dev/examples/`;
- `build.builder = SYNTHETIC_TEST`;
- `provenance.artifact_origin = SYNTHETIC_FIXTURE`;
- `provenance.sanitation_state = SYNTHETIC`;
- `provenance.attestation_state = NOT_ATTESTED`.

It has no product, runtime or promotion authority.

### `RUNTIME_CANDIDATE`

A future real candidate manifest must use:

- `source.identity_semantic = EXACT_SOURCE_COMMIT`;
- `build.builder = GITHUB_HOSTED` under the current public build architecture;
- `provenance.artifact_origin = BUILD_OUTPUT`;
- `provenance.sanitation_state = EXACT_BUILD_OUTPUT`.

The v1 foundation does not yet build such an artifact. It only defines and tests the contract that a later candidate builder must satisfy.

## Sanitized RC14.38 boundary

`legacy/v7-rc14.38-sanitized` is a public regression fixture with identity semantic `SANITIZED_NOT_BYTE_IDENTICAL_NOT_RUNTIME_QUALIFIED`.

It must never be promoted into `RUNTIME_CANDIDATE` authority.

The semantic validator rejects a runtime-candidate manifest when:

- source identity is `SANITIZED_PUBLIC_FIXTURE`;
- source path points into `legacy/v7-rc14.38-sanitized` even if a caller falsely labels it `EXACT_SOURCE_COMMIT`;
- provenance claims sanitized-public material as an exact build output.

The historical private RC14.38 ZIP SHA remains runtime-history evidence, not a public candidate produced by this contract.

## Runtime authority boundary

Candidate Artifact Truth v1 deliberately cannot claim trusted runtime success.

Every accepted v1 manifest must have:

```text
runtime.qualification_state = NOT_VERIFIED
runtime.evidence_ref = null
runtime.promotion_eligible = false
provenance.runtime_authority = false
```

A GitHub-hosted build or manifest validator cannot change these values into runtime truth.

Wave 4 must introduce a separately governed trusted Runtime Qualification result/evidence contract before runtime verification or promotion eligibility can exist.

## Fail-closed structural rules

The schema and semantic validator reject:

- unknown fields at contract object boundaries;
- wrong schema/contract version;
- malformed source SHA or artifact SHA-256;
- zero/negative artifact size;
- unsafe source paths or artifact path masquerading as a filename;
- missing/duplicate/non-success engineering checks;
- engineering check subject SHA mismatch;
- synthetic fixtures claiming runtime-candidate semantics;
- runtime candidates sourced from the sanitized RC14.38 fixture;
- runtime evidence while state is `NOT_VERIFIED`;
- promotion eligibility in the contract-foundation stage.

Unknown or contradictory evidence never becomes PASS by omission.

## WU-008 result

`PIPE-WU-008` established the contract foundation and was protected-squash merged as main `a39369f005086c5ef209c392032a435096265542` with fresh post-merge hosted verification.

It did not create RC14.39, build a deployable PNCC ZIP, mutate product/legacy source or claim runtime qualification.

## Build-input readiness boundary

Source-truth discovery after WU-008 proved that the public repository still has no governed non-legacy product source declaration and no admitted candidate build recipe. Product-like historical source remains only under `legacy/v7-rc14.38-sanitized/`, which is migration/regression material and is forbidden as candidate source authority.

`PIPE-WU-009` therefore introduces a separate fail-closed readiness layer before any future builder can run:

- policy: `.pncc-dev/contracts/candidate-build-input-policy.json`;
- evaluator: `.pncc-dev/scripts/evaluate_candidate_build_input.py`;
- regressions: `.pncc-dev/tests/test_candidate_build_input.py`;
- hosted gate: `.github/workflows/candidate-build-input-readiness.yml`.

The current exact repository is expected to classify as:

```text
CANDIDATE_BUILD_INPUT_STATE=BLOCKED_MISSING_SOURCE_DECLARATION
CAN_BUILD=false
RUNTIME_AUTHORITY=false
PROMOTION_AUTHORITY=false
```

A future `READY` state requires an explicit closed declaration using `EXACT_SOURCE_COMMIT`, Git-tracked product source under governed `src/` roots, a Git-tracked build recipe under `build/`, no forbidden `legacy/` input and no dirty/untracked declared build inputs.

The `--require-ready` guard exits nonzero for every blocked state. A green hosted readiness workflow means the classification/guard behaved correctly; it does **not** mean a candidate can currently be built.

Exact PR evidence must be tied to the PR head SHA rather than GitHub's temporary merge ref. This is enforced by explicit checkout of `${{ github.event.pull_request.head.sha || github.sha }}`.

## Next Wave 3 boundary

After WU-009 is protected-merge and post-merge verified, the next source-truth decision is whether exact governed non-sanitized product source and a build recipe can be admitted into the public Product / Engineering Truth plane.

Until that source-plane condition becomes `READY`, a candidate builder must remain absent/blocked. The pipeline must not manufacture a runtime candidate from the sanitized RC14.38 fixture or infer build readiness from CI success.
