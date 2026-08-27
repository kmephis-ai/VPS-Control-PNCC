# PNCC Runtime Qualification Boundary

## Purpose

Runtime Qualification is a trusted execution-plane transaction that begins only after a governed candidate artifact exists. Public GitHub defines the request and validates result semantics; it does not execute or manufacture physical runtime truth.

## Current candidate handoff

The current request binds candidate `PNCC-RC14.39-90C9E8698C64`, protected-main source `90c9e8698c6468d576aecbc60d940be9d5c6baab`, inner ZIP SHA-256 `8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3`, and provider artifact ID `9661221985`.

Until a valid result is produced by the trusted `PRIVATE_RUNTIME` plane, the only valid state is:

```text
RUNTIME_QUALIFICATION_STATE=WAITING_RUNTIME_EVIDENCE
RUNTIME_AUTHORITY=false
PROMOTION_ELIGIBLE=false
```

## Public/private boundary

Public Git may contain request identity, schemas, policy, validators, synthetic tests and sanitized summaries. Raw runtime evidence, DPAPI material, credentials, private topology, process dumps and owner-specific machine state remain outside public Git.

A private result must reference an evidence bundle by SHA-256 and opaque private location reference. Public CI may validate the shape/logic of synthetic results, but a `GITHUB_HOSTED` producer can never satisfy trusted Runtime Qualification.

## Required physical scopes

- Windows and PowerShell/runtime-agent baseline;
- process ownership and dirty-baseline classification;
- watchdog lifecycle;
- Proxifier descendant cleanup/resource-leak behavior;
- 1081 PRIMARY_AUTO lifecycle;
- 1080 RESERVE_MANUAL/MANUAL_ONLY invariant;
- credential transport and host-key fail-closed behavior;
- network qualification;
- immutable V6.3.1 rollback identity.

## Failure authority

`VALIDATOR_DEFECT` permits validator-scope repair only. `HARNESS_DEFECT` permits harness-scope repair only. `ENVIRONMENT_OR_BASELINE_BLOCKER` permits environment/evidence cleanup only. `PRODUCT_DEFECT` is the only class that may justify a later product mutation Work Unit.

Blocked runtime is not a product failure. Missing runtime evidence is not a failure at all; it is a durable waiting state.

## Promotion boundary

Even a complete trusted `RUNTIME_VERIFIED` result does not itself make the candidate Stable or automatically promotable. Promotion remains a separate governed decision/gate.

`CI VERIFIED != RUNTIME VERIFIED`.
