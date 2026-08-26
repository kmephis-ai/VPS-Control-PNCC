# AGENTS.md — PNCC mandatory engineering rules

Human-facing communication is Russian by default. Machine-facing identifiers, paths, schemas and code remain English where appropriate.

## Sources of truth

1. Public GitHub = Product / Engineering Truth.
2. Local PNCC data = private Instance Configuration Truth.
3. Real Windows / Keenetic / VPS nodes = Runtime Truth.

Never turn CI success into a claim of physical runtime success.

## Fixed legacy/runtime contract

- `127.0.0.1:1081 = PRIMARY_AUTO`.
- `127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY`.
- Automation must never start/stop/restart/recover 1080.
- V6.3.1 is immutable; expected SHA-256: `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e`.
- Do not rewrite V6.3.1 while migrating architecture.
- Stable/DONE requires fresh Windows runtime evidence.

## Credential contract

- Never place a real password/token/private key/DPAPI blob in prompt, source, Issue, PR, CI log, evidence, fixture or documentation.
- New product runtime uses DPAPI at rest.
- PuTTY credential transport uses `-pwfile` only; plaintext `-pw` is forbidden.
- Host-key verification is fail-closed; no bypass or trust-on-any-key shortcut.

## Failure classification

Product mutation is permitted only for a proven product defect.

Classify failures before retrying:
- `VALIDATOR_DEFECT` → fix validator only.
- `HARNESS_DEFECT` → fix harness only.
- `ENVIRONMENT_OR_BASELINE_BLOCKER` / dirty process baseline → fix evidence/baseline only.
- `PRODUCT_DEFECT` / proven runtime product defect → a product change/new candidate is permitted.

Do not create a new RC merely because a test harness failed.

## Writer discipline

One writer per overlapping conflict domain. Read-only discovery can run in parallel. Before runtime mutation, prove process ownership and a clean baseline. Do not trust stale PID files as the sole process authority; live process identity and machine-verifiable evidence are required.

## Public CI

- GitHub-hosted runners only.
- No home/LAN self-hosted runner on this public repository.
- Default workflow permissions should remain read-only unless a narrowly scoped trusted workflow requires more.
- No production secrets for pull requests.
- Never execute arbitrary contributor code on trusted home infrastructure.

## Repository migration state

During public bootstrap, do not copy the existing local working directory or its Git history wholesale. Import only a sanitized, inventoried tree. Runtime state, private configuration and evidence remain outside Git.

Current migration candidate is tracked as exact `v7.0.0-rc14.38` with SHA-256 `6d81137519a363ebf3d8503f33a344d8fdc75848d517cf732cb6d6d02394d727`; repository migration alone must not mutate that candidate.

## ADWF relationship

PNCC is an ADWF consumer, not part of ADWF. ADWF policy/runtime must remain upstream and version-pinned through a consumer contract/project pack. Do not copy the ADWF implementation into this repository.
