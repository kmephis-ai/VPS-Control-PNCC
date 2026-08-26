# PNCC ↔ ADWF External Thin Consumer Binding

Status: implementation candidate for `ADWF_BIND-001`.

## Purpose

PNCC consumes ADWF Core as an **external/thin consumer**. The framework is not copied into the PNCC repository. The consumer-owned binding is proof/configuration only and grants no product, deployment, runtime, credential, network or filesystem mutation authority.

## Exact framework identity

- repository: `kmephis-ai/AI-Development-Framework`
- source SHA: `730cab912f779bec1f3208c66eda1889f69d6f4c`
- Project Pack: `powershell`
- Project Pack digest: `fbe69c4e93ff8b07e7d0dc6f0cbd1f9ceb80617f472f1fbe5a1ce181279a0c8c`

The explicit `.adwf-powershell.json` marker is required for deterministic Project Pack detection. The sealed `.adwf-consumer/external-binding.json` binds PNCC to the exact ADWF revision and native GitHub checks.

## Execution-plane boundary

Reproducible engineering evidence is produced by GitHub-hosted CI. The owner/private Windows machine is not a CI runner, build server, required correctness gate or source of canonical static/unit/framework PASS.

The private Windows node may be used only for environment-bound runtime facts that GitHub-hosted runners cannot reproduce faithfully, such as actual Proxifier/PuTTY/DPAPI/WinForms behavior, the private VPS path, local network state and real `127.0.0.1:1081` integration.

Absence of required private runtime evidence means `NOT_VERIFIED`; GitHub CI must never synthesize `RUNTIME VERIFIED`.

## Native CI gates

The binding declares these GitHub Actions checks for PR and main evidence:

- `repo-integrity`
- `powershell-static`
- `truth-contract`

The separate `adwf-binding` workflow validates the sealed binding against the exact ADWF Core SHA on a GitHub-hosted `ubuntu-24.04` runner. After this work unit is post-merge verified, a separate governance transaction may add `adwf-binding` to the required status checks ruleset.

## Fixed PNCC invariants

- `127.0.0.1:1081 = PRIMARY_AUTO`.
- `127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY`; automated lifecycle remains forbidden.
- V6.3.1 remains immutable.
- new PNCC product runtime must not use plaintext PuTTY `-pw`.
- host-key verification remains fail-closed.
- `CI VERIFIED != RUNTIME VERIFIED`.

This binding does not modify PNCC product/runtime behavior and does not create or qualify a release candidate.
