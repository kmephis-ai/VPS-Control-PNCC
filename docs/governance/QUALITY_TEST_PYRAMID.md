# PNCC Quality and Test Pyramid

Status: Wave 2 implementation contract.

Tracking: #6. Completed foundation: #19 (`PIPE-WU-003`). Active regression unit: #21 (`PIPE-WU-004`).

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

`PRODUCT_ONLY` means the classifier found evidence compatible with product-scope mutation. It does **not** override Work Unit scope, owner/governance authority, runtime requirements, security policy, exact-SHA identity, or candidate promotion rules.

## PowerShell 5.1 collection contract

PowerShell command/pipeline results do not have stable caller cardinality by default: zero results commonly become `$null`, one result commonly becomes a scalar, and multiple results become an array. Validator code that assumes a stable array can therefore fail differently for 0/1/N results, particularly under StrictMode.

`.pncc-dev/quality/PNCC.PowerShellCollections.psm1` addresses this at engineering-control-plane boundaries with `ConvertTo-PnccCollectionView`.

The function returns one PSCustomObject containing:

- `Items` — an explicit `System.Object[]`;
- `Count` — an explicit `Int32`;
- `IsEmpty` — an explicit Boolean;
- `SchemaVersion` — contract identity.

The wrapper object is intentional. Returning a raw array from a PowerShell function would itself be subject to pipeline enumeration and could recreate the same 0/1/N collapse at the caller boundary.

### Collection regressions

The Pester suite verifies under StrictMode and Windows PowerShell 5.1:

- `$null` -> zero items;
- explicit empty array -> zero items;
- scalar -> exactly one item;
- one-element array -> exactly one item without scalar collapse inside the view;
- multi-item arrays preserve count and order;
- strings remain one logical item rather than character enumeration;
- PSCustomObject remains one logical item;
- simulated `Where-Object` pipelines yielding 0, 1 and N items all produce stable `Count` and `Items` semantics.

The private historical Validation Lab function that exhibited a collection-cardinality defect is not present in the sanitized public product tree. This repository therefore records the generic failure class and reusable contract rather than fabricating a direct regression against unavailable private code.

## Execution-plane boundary

All tests in this layer run on GitHub-hosted infrastructure. The private Windows runtime node is not a CI runner. Tests requiring real Proxifier, SSH tunnel, DPAPI, host-key, network exit identity or physical process lifecycle evidence remain runtime qualification work and cannot be inferred from this gate.

## Next maturity steps

After collection/StrictMode regressions are post-merge verified, continue Wave 2 with the next smallest historical contract domain. Prefer deterministic product-adjacent invariants that can be validated without physical network behavior, then introduce a separate DEEP CI layer before expanding into runtime-only scenarios.
