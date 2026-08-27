# PNCC Quality and Test Pyramid

Status: Wave 2 implementation contract.

Tracking: #6. Completed units: #19 (`PIPE-WU-003`), #21 (`PIPE-WU-004`), #23 (`PIPE-WU-005`). Active unit: #25 (`PIPE-WU-006`).

## Purpose

Wave 2 moves PNCC from static/public-safety checks toward executable behavioral engineering evidence without confusing hosted CI with physical runtime truth.

`CI VERIFIED != RUNTIME VERIFIED` remains mandatory.

## FAST quality baseline

The behavioral FAST layer is `quality-fast` on GitHub-hosted `windows-latest` using **Windows PowerShell 5.1**.

Dependencies are intentionally fail-closed and version-pinned to modules already present in the hosted runner image:

- Pester `5.9.0`;
- PSScriptAnalyzer `1.25.0`.

The workflow does not install packages or float to a newer module version. If the runner image no longer provides the pinned version, the gate blocks until an explicit reviewed dependency update is made.

`quality-fast` analyzes all `.pncc-dev/quality` modules for PSScriptAnalyzer Error/Warning findings and runs the complete `.pncc-dev/pester` suite with a monotonic floor of **35 tests**.

FAST is for low-latency behavioral feedback. Tests requiring a complete fixture inventory/provenance walk belong in DEEP rather than being silently added to the FAST count.

## DEEP quality baseline

`PIPE-WU-006` introduces an isolated `quality-deep` workflow on GitHub-hosted Windows infrastructure. DEEP uses Windows PowerShell 5.1 and pinned Pester 5.9.0, but executes only `.pncc-dev/pester-deep` plus the explicit sanitized-fixture provenance verification.

The DEEP layer is deterministic and secret-free. It does not execute a live SSH tunnel, Proxifier, DPAPI store, host-key store, VPS, Keenetic or owner Windows node.

Concurrency is scoped per pull request/ref with `cancel-in-progress: true`, so stale DEEP executions for the same change do not accumulate authority or obscure the latest exact-head result.

### Sanitized fixture provenance contract

The machine-readable contract is `.pncc-dev/contracts/sanitized-fixture-provenance.json`.

It distinguishes three identities that must never be conflated:

1. public sanitized fixture Git tree: `2a6c0027a195e91640ec2a6e38220a9fac372368`;
2. public sanitized per-file SHA-256 inventory: `legacy/v7-rc14.38-sanitized/SANITIZED-SHA256.txt`, expected entry count `32`;
3. original private candidate reference: `v7.0.0-rc14.38`, ZIP SHA-256 `6d81137519a363ebf3d8503f33a344d8fdc75848d517cf732cb6d6d02394d727`.

The identity semantic is explicitly `SANITIZED_NOT_BYTE_IDENTICAL_NOT_RUNTIME_QUALIFIED`.

The SHA-256 manifest semantic is explicitly `GIT_BLOB_BYTES_SHA256`: hashes are computed from the canonical bytes stored in the pinned Git tree, before `.gitattributes` checkout transformations. Platform-specific LF/CRLF working-tree materialization therefore cannot change or redefine public fixture provenance.

`.pncc-dev/quality/PNCC.SanitizedFixtureProvenance.psm1` verifies fail-closed that:

- the fixture Git tree matches the pinned public tree identity;
- the SHA-256 manifest has strict syntax and no duplicate/self/unsafe entries;
- manifest paths are relative and cannot traverse outside the fixture root;
- the manifest inventory exactly equals all Git blobs in the fixture tree except the manifest itself;
- every listed canonical Git blob hashes to the published SHA-256;
- the sanitation record retains the original private-candidate reference and explicit non-runtime-qualified semantics.

The DEEP Pester floor is **10 tests**. Synthetic regressions prove that hash mismatch, missing files, unlisted extra files, malformed lines, duplicate paths, traversal, absolute paths and manifest self-entry all fail closed. A dedicated Git-blob regression proves that a post-commit working-tree CRLF transformation cannot change a valid committed-blob provenance result.

A passing DEEP fixture gate proves only that the public regression fixture is the exact public fixture described by its provenance contract. It does **not** prove that the private runtime candidate is byte-identical, deployable, Stable, or runtime-qualified.

## Failure classification contract

The pure engineering-control-plane module `.pncc-dev/quality/PNCC.FailureClassification.psm1` classifies only evidence supplied to it. It does not inspect or mutate runtime state and does not itself grant product mutation permission.

Classification precedence is fail-closed:

1. validator self-check failure -> `VALIDATOR_DEFECT` / `VALIDATOR_ONLY`;
2. harness orchestration failure after validator PASS -> `HARNESS_DEFECT` / `HARNESS_ONLY`;
3. environment/baseline failure after validator+harness PASS -> `ENVIRONMENT_OR_BASELINE_BLOCKER` / `ENVIRONMENT_OR_EVIDENCE_ONLY`;
4. product invariant failure may become `PRODUCT_DEFECT` / `PRODUCT_ONLY` only when all upstream evidence is PASS, product execution is proven to have started, and the product invariant failure is explicit;
5. contradictory, unknown or insufficient evidence -> `BLOCKED_UNCLASSIFIED` / `NONE`.

`PRODUCT_ONLY` does not override Work Unit scope, owner/governance authority, runtime requirements, security policy, exact-SHA identity, or candidate promotion rules.

## PowerShell 5.1 collection contract

PowerShell command/pipeline results do not have stable caller cardinality by default: zero results commonly become `$null`, one result commonly becomes a scalar, and multiple results become an array. Validator code that assumes a stable array can therefore fail differently for 0/1/N results, particularly under StrictMode.

`.pncc-dev/quality/PNCC.PowerShellCollections.psm1` returns one stable collection-view object with explicit `Items:Object[]`, `Count:Int32`, `IsEmpty:Boolean` and `SchemaVersion` fields. The wrapper object prevents a returned raw array from being re-enumerated and collapsed at the caller boundary.

The Pester regressions cover null, explicit empty arrays, scalar, one-element and multi-item arrays, strings, PSCustomObject values and simulated `Where-Object` pipelines yielding 0/1/N results.

The private historical Validation Lab function that exhibited a collection-cardinality defect is not present in the sanitized public product tree. The repository therefore records the generic failure class and reusable contract rather than fabricating a direct regression against unavailable private code.

## Tunnel and credential safety fixture regressions

`PIPE-WU-005` treats the public `legacy/v7-rc14.38-sanitized` snapshot as a **read-only regression fixture**, not as runtime-qualified product evidence.

The executable FAST regression suite checks that the fixture continues to encode:

- `PRIMARY_AUTO` on `127.0.0.1:1081` with automatic start/recovery authority;
- `RESERVE_MANUAL` on `127.0.0.1:1080` with `MANUAL_ONLY` lifecycle and every automatic reserve lifecycle action forbidden;
- no automatic failover to reserve;
- reserve adoption does not transfer automatic lifecycle authority;
- missing portable host-key trust and registry conflicts fail closed;
- unknown host-key acceptance and host-key verification disable remain forbidden;
- credential at rest is DPAPI;
- PuTTY password transport is `-pwfile`, while plaintext password argument fallback remains forbidden;
- temporary credential material is local, creation-time ACL protected, inheritance-disabled and restricted to current user plus SYSTEM.

The suite also checks source ordering in the sanitized tunnel manager: trusted host-key setup must occur in the manual reserve start path before password decryption and launch-argument preparation.

These are engineering regression claims only. They do not prove that a real tunnel, host key, DPAPI store, process ACL or network identity behaves correctly on a physical Windows node.

## Execution-plane boundary

FAST and DEEP both run on GitHub-hosted infrastructure. The private Windows runtime node is not a CI runner. Tests requiring real Proxifier, SSH tunnel, DPAPI, host-key, network exit identity or physical process lifecycle evidence remain runtime qualification work and cannot be inferred from either hosted quality layer.

## Next maturity steps

After `PIPE-WU-006` is protected-merge and post-merge verified, reassess whether Wave 2 has enough deterministic coverage to close the remaining process-ownership/dirty-baseline/watchdog/cleanup regression domains or whether the next smallest unit should prepare the Wave 3 candidate-manifest boundary. Provider and runtime truth decide; roadmap text alone does not.
