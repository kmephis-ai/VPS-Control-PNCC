<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-017 state=ACTIVE conflict_domain=owner-runtime-bootstrap branch=agent/PIPE-WU-017-owner-bootstrap-a1 base=0e87befcd25164dda39cd1bc90c2774bc29a6d32 runtime_required=false -->

# PIPE-WU-017 — Owner Windows Bootstrap + Exact Artifact Acquisition

## Exact base

`0e87befcd25164dda39cd1bc90c2774bc29a6d32`

## Goal

Establish a reproducible owner-side bootstrap that acquires the exact governed RC14.39 provider artifact, verifies provider metadata and inner candidate identity, creates an isolated runtime-qualification workspace, and executes only the existing non-mutating WU-016 dry-run agent.

## Forbidden scope

- real runtime qualification;
- product/runtime source mutation;
- start/stop/restart/recover of any tunnel, watchdog or Proxifier process;
- any lifecycle operation against 1080 or 1081;
- V6.3.1 mutation;
- credential or host-key weakening;
- public self-hosted runner;
- Runtime Truth, promotion or Stable claim.

## Exit criteria

Hosted Windows CI must prove exact provider artifact acquisition, inner SHA-256/size verification, isolated workspace creation, dry-run agent handoff, and zero runtime authority/mutation.
