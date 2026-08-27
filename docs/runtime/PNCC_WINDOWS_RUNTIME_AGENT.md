# PNCC Windows Runtime Qualification Agent

## Purpose

The Windows Runtime Qualification Agent is the future trusted `PRIVATE_RUNTIME` executor for PNCC runtime qualification requests. Public GitHub remains Product / Engineering Truth; the physical Windows node remains Runtime Truth.

`CI VERIFIED != RUNTIME VERIFIED`.

## Current WU-016 capability

WU-016 intentionally enables **dry-run only**. The public repository ships an entrypoint that:

1. reads the governed runtime qualification request;
2. verifies exact RC14.39 candidate identity and fixed invariants;
3. creates a nine-scope execution plan;
4. stages separate `private-evidence/` and `public-safe/` boundaries;
5. emits a blocked result skeleton that cannot claim runtime verification;
6. refuses real execution unless a later Work Unit explicitly implements it.

No tunnel/process/network lifecycle mutation is permitted in this mode.

## Fixed runtime invariants

- `127.0.0.1:1081 = PRIMARY_AUTO`.
- `127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY`.
- Automation must never start, stop, restart or recover 1080.
- V6.3.1 is immutable with SHA-256 `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e`.
- PuTTY password transport is `-pwfile` only.
- Host-key verification remains fail-closed.

## Public/private evidence boundary

`private-evidence/` is reserved for raw Runtime Truth and may contain machine-local identifiers, process topology, diagnostic details or other owner-private evidence. It must never be committed to the public repository as-is.

`public-safe/` is a separate projection boundary. A later Work Unit must define sanitation and publication rules before any runtime result can be admitted to public Product / Engineering Truth.

The two locations are deliberately distinct so a raw private bundle cannot be mistaken for publishable evidence.

## Dry-run invocation

From PowerShell 7 or Windows PowerShell 5.1:

```powershell
pwsh -NoProfile -File .\tools\runtime-agent\Invoke-PnccRuntimeQualificationAgent.ps1 -RequestPath .\.pncc-dev\requests\runtime-qualification-rc14.39.json -OutputDirectory .\runtime-agent-output -DryRun
```

For Windows PowerShell 5.1 use `powershell.exe` instead of `pwsh`.

Expected result: an execution plan and a non-authoritative blocked result skeleton. Dry-run does not constitute runtime evidence.

## Real execution

Real execution is intentionally disabled in WU-016. A later Work Unit must add trusted owner-side bootstrap, exact governed-artifact acquisition, preflight, controlled runtime execution, evidence hashing/sanitation and result transport without registering the owner's machine as a self-hosted runner on this public repository.
