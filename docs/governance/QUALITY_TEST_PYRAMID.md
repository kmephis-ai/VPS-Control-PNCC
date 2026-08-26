# PNCC Quality and Test Pyramid

Status: Wave 2 implementation contract, foundation stage.

Tracking: #6, Work Unit #19 (`PIPE-WU-003`).

## Purpose

Wave 2 moves PNCC from static/public-safety checks toward executable behavioral engineering evidence without confusing hosted CI with physical runtime truth.

`CI VERIFIED != RUNTIME VERIFIED` remains mandatory.

## FAST quality baseline

The first behavioral layer is `quality-fast` on GitHub-hosted `windows-latest` using **Windows PowerShell 5.1**.

Dependencies are intentionally fail-closed and version-pinned to modules already present in the hosted runner image:

- Pester `5.9.0`;
- PSScriptAnalyzer `1.25.0`.

The workflow does not install packages or float to a newer module version. If the runner image no longer provides the pinned version, the gate blocks until an explicit reviewed dependency update is made.

## Failure classification contract

The pure engineering-control-plane module `.pncc-dev/quality/PNCC.FailureClassification.psm1` classifies only evidence supplied to it. It does not inspect or mutate runtime state and does not itself grant product mutation permission.

Classification precedence is fail-closed:

1. validator self-check failure -> `VALIDATOR_DEFECT` / `VALIDATOR_ONLY`;
2. harness orchestration failure after validator PASS -> `HARNESS_DEFECT` / `HARNESS_ONLY`;
3. environment/baseline failure after validator+harness PASS -> `ENVIRONMENT_OR_BASELINE_BLOCKER` / `ENVIRONMENT_OR_EVIDENCE_ONLY`;
4. product invariant failure may become `PRODUCT_DEFECT` / `PRODUCT_ONLY` only when all upstream evidence is PASS, product execution is proven to have started, and the product invariant failure is explicit;
5. contradictory, unknown or insufficient evidence -> `BLOCKED_UNCLASSIFIED` / `NONE`.

`PRODUCT_ONLY` means the classifier found evidence compatible with product-scope mutation. It does **not** override Work Unit scope, owner/governance authority, runtime requirements, security policy, exact-SHA identity, or candidate promotion rules.

## Initial regression set

The initial Pester suite proves:

- validator defect precedence;
- harness defect attribution;
- environment/baseline attribution;
- product-defect evidence threshold;
- no product defect when product execution never started;
- unknown validator state blocks downstream classification;
- contradictory evidence blocks classification;
- clean evidence produces `NO_DEFECT`;
- unknown product execution/invariant states cannot become product defect;
- extra or missing evidence fields are rejected rather than silently ignored.

Historical product/runtime regressions are intentionally deferred to later Wave 2 Work Units so this foundation remains small and independently reviewable.

## Execution-plane boundary

All tests in this foundation run on GitHub-hosted infrastructure. The private Windows runtime node is not a CI runner. Tests requiring real Proxifier, SSH tunnel, DPAPI, host-key, network exit identity or physical process lifecycle evidence remain runtime qualification work and cannot be inferred from this gate.

## Next maturity step

After this foundation is merged and post-merge verified, the next Wave 2 Work Unit should add historical contract regressions around the highest-risk previously observed failure classes, beginning with collection normalization / StrictMode / validator-vs-product attribution while preserving the no-product-mutation-without-`PRODUCT_DEFECT` rule.
