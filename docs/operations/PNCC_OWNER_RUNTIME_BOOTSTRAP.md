# PNCC Owner Runtime Workspace Bootstrap

## Purpose

This bootstrap prepares an isolated owner-side workspace for the exact governed RC14.39 candidate without performing runtime mutation or claiming Runtime Truth.

It verifies the GitHub Actions provider artifact identity, downloads the exact governed artifact, verifies the inner candidate SHA-256 and byte size, copies the governed runtime qualification request and runtime-agent entrypoint into an isolated workspace, and executes only the WU-016 dry-run plan.

`CI VERIFIED != RUNTIME VERIFIED`.

## Exact candidate

- source SHA: `90c9e8698c6468d576aecbc60d940be9d5c6baab`
- provider artifact ID: `9661221985`
- provider build run ID: `33107824902`
- provider artifact digest: `sha256:eaf9844e8901cce7b1ebc866550e37cfd72393afc67075c27cba6703a415b68e`
- inner artifact: `VPS-Control-v7.0.0-rc14.39.zip`
- inner SHA-256: `8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3`
- inner size: `700961` bytes

## Owner-side prerequisites

- Windows PowerShell 5.1 or PowerShell 7;
- GitHub CLI `gh` authenticated to the repository;
- repository checkout containing the governed WU-015 request and WU-016 runtime agent.

No VPS password, DPAPI data, private host keys or runtime logs are read or transmitted by the bootstrap.

## Invocation

From the repository root:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File ".\tools\runtime-agent\Initialize-PnccRuntimeQualificationWorkspace.ps1" -OutputRoot "E:\!Chrome_Downloads\PNCC-RuntimeQualification"
```

The command creates a timestamped workspace with separate `provider-artifact`, `request`, `agent`, `private-evidence`, `public-safe`, and `agent-dry-run` locations.

## Safety boundary

The bootstrap does not start, stop, restart or recover PNCC, Proxifier, SSH tunnels or watchdog processes. It does not touch port 1080 or 1081. It grants no runtime authority and no promotion eligibility.

A later Work Unit must explicitly implement controlled PRIVATE_RUNTIME execution before any runtime qualification can occur.
