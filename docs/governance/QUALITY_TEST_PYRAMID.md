# PNCC Quality and Test Pyramid

Status: Wave 2 implementation contract.

Tracking: #6. Completed units: #19 (`PIPE-WU-003`), #21 (`PIPE-WU-004`). Active regression unit: #23 (`PIPE-WU-005`).

## Purpose

Wave 2 moves PNCC from static/public-safety checks toward executable behavioral engineering evidence without confusing hosted CI with physical runtime truth.

`CI VERIFIED != RUNTIME VERIFIED` remains mandatory.

## FAST quality baseline

The behavioral FAST layer is `quality-fast` on GitHub-hosted `windows-latest` using **Windows PowerShell 5.1**.

Dependencies are intentionally fail-closed and version-pinned to modules already present in the hosted runner image:

- Pester `5.9.0`;
- PSScriptAnalyzer `1.25.0`.

The workflow does not install packages or float to a newer module version. If the runner image no longer provides the pinned version, the gate blocks until an explicit reviewed dependency update is made.

`quality-fast` analyzes all `.pncc-dev/quality` modules for PSScriptAnalyzer Error/Warning findings and runs the complete `.pncc-dev/pester` suite with a monotonic test-count floor.

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

The executable regression suite checks that the fixture's explicit tunnel contract continues to encode:

- `PRIMARY_AUTO` on `127.0.0.1:1081` with automatic start/recovery authority;
- `RESERVE_MANUAL` on `127.0.0.1:1080` with `MANUAL_ONLY` lifecycle and every automatic reserve lifecycle action forbidden;
- no automatic failover to reserve;
- reserve adoption does not transfer automatic lifecycle authority;
- missing portable host-key trust and registry conflicts fail closed;
- unknown host-key acceptance and host-key verification disable remain forbidden;
- credential at rest is DPAPI;
- PuTTY password transport is `-pwfile`, while literal plaintext `-pw` fallback remains forbidden;
- temporary credential material is local, creation-time ACL protected, inheritance-disabled and restricted to current user plus SYSTEM.

The suite also checks source ordering in the sanitized tunnel manager: trusted host-key setup must occur in the manual reserve start path before password decryption and launch-argument preparation, and the launch path must construct `-pwfile` rather than a literal `-pw` argument.

These are engineering regression claims only. They do not prove that a real tunnel, host key, DPAPI store, process ACL or network identity behaves correctly on a physical Windows node.

## Execution-plane boundary

All tests in this layer run on GitHub-hosted infrastructure. The private Windows runtime node is not a CI runner. Tests requiring real Proxifier, SSH tunnel, DPAPI, host-key, network exit identity or physical process lifecycle evidence remain runtime qualification work and cannot be inferred from this gate.

## Next maturity steps

After tunnel/credential fixture regressions are post-merge verified, reassess the next smallest deterministic contract domain from fresh repository truth. Candidates include immutable rollback/source identity and a separate DEEP CI layer before any expansion into physical runtime-only behavior.
