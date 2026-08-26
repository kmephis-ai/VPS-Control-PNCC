# ADR-0001: Public GitHub product truth and private runtime boundary

- Status: Accepted
- Date: 2026-08-26

## Context

PNCC is moving from chat-produced RC ZIPs and manual replacement toward repository-native engineering, hosted CI, immutable source revisions and a separate trusted runtime execution plane.

The project controls networking and may interact with credentials, Proxifier, PuTTY, VPS nodes and a home router. A public repository therefore must not become a deployment-state or secret store.

## Decision

Three distinct truths are maintained:

1. **Public GitHub — Product / Engineering Truth**
   - source code;
   - schemas/templates;
   - tests;
   - documentation/ADRs;
   - CI and packaging definitions;
   - sanitized examples;
   - release metadata.

2. **Local PNCC Data — Instance Configuration Truth**
   - real node profiles;
   - secret references/DPAPI data;
   - runtime state;
   - logs/backups/telemetry;
   - owner-specific infrastructure values.

3. **Real Nodes — Runtime Truth**
   - Windows, VPS and Keenetic are authoritative for physical/runtime behavior.
   - CI PASS never means networking runtime PASS.

Public CI uses GitHub-hosted runners only. Home/LAN runtime verification is performed by a separate typed PNCC Runtime Test Agent / ADWF Execution Node that does not execute arbitrary public PR workflow code.

## Legacy migration

Migration is incremental, not a big-bang rewrite.

- V6.3.1 remains an immutable rollback baseline.
- Current V7 stabilization remains available as a legacy adapter/source baseline while the new architecture is introduced.
- PowerShell is gradually wrapped by explicit agent/adapter contracts rather than discarded first.

## Fixed tunnel policy

- `127.0.0.1:1081`: `PRIMARY_AUTO`.
- `127.0.0.1:1080`: `RESERVE_MANUAL / MANUAL_ONLY` and never lifecycle-managed by PNCC automation.

## Consequences

- Initial public history is intentionally clean; no import of unknown local Git history.
- Repository sanitation precedes product-source import.
- Runtime evidence is local/private by default and only sanitized evidence may be published.
- ADWF integration is an upstream consumer contract, not code duplication.
