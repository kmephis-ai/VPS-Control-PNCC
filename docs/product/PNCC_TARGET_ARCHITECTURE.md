# PNCC Target Product Architecture

**Status:** ACCEPTED PRODUCT TARGET BASELINE / RECONCILED  
**Reconciled:** 2026-08-26  
**Repository base used for reconciliation:** `e45603bdcecb48a0efd83f6a71a6458b25f959a8`  
**Historical source architecture:** owner `TARGET_ARCHITECTURE.md`, 2026-08-24  
**Tracking:** Issue #9 (`DOC-001`)

## 1. Scope

This document defines the **target architecture of the PNCC product**.

It is intentionally separate from:

- current implementation/capability truth in `legacy/v7-rc14.38-sanitized/`;
- the development-system architecture in `docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md`;
- the development maturity roadmap in `docs/roadmap/PNCC_PIPELINE_ROADMAP.md`;
- runtime qualification evidence from real Windows/Keenetic/VPS nodes.

A target architecture item is not implemented merely because it appears here.

## 2. Reconciliation summary

The 2026-08-24 architecture direction remains valid, but its project-state assumptions are updated:

- public GitHub migration is now established as the Product / Engineering Truth plane;
- a sanitized RC14.38 migration snapshot exists in the repository;
- V6.3.1 remains the immutable rollback baseline;
- the permanent tunnel model is dual-tunnel: 1081 `PRIMARY_AUTO`, 1080 `RESERVE_MANUAL / MANUAL_ONLY`;
- current WinForms/V7 remains a transitional product shell rather than the final architecture;
- Status Center, diagnostics, observability, multi-VPS foundations, Keenetic probing, Entware inventory and several guarded mutations already exist in the imported candidate truth;
- full Web Control Plane, explicit separated agents, RCI mutation, destructive Entware install/remove, plugin marketplace, mobile endpoints and broad transport ecosystem remain target/research capabilities;
- PNCC is an ADWF consumer. ADWF belongs to the Development Plane, not the PNCC runtime product.

## 3. Top-level architectural decision

PNCC evolves into a **local-first distributed network control platform**:

```text
+---------------------------------------------------------------+
|                      CONTROL EXPERIENCE                       |
| Web UI (target) | Transitional Desktop | CLI | API            |
+-----------------------------+---------------------------------+
                              |
                              v
+---------------------------------------------------------------+
|                         CONTROL PLANE                         |
| State Coordinator | Policy Engine | Scenario Engine           |
| Transaction Manager | Event/Audit | Backup | Plugin Registry  |
| Secrets Abstraction | Capability Registry                    |
+-----------+----------------+----------------+------------------+
            |                |                |
            v                v                v
+------------------+ +----------------+ +------------------------+
| WINDOWS AGENT    | | VPS AGENT(S)   | | KEENETIC ADAPTER       |
| routing/provider | | SSH/API        | | KeeneticOS / RCI       |
| Proxifier        | | services       | | CLI / SSH              |
| browser/firewall | | metrics        | | Entware / storage      |
| Hyper-V          | | containers     | | policy / modules       |
+------------------+ +----------------+ +------------------------+
            \                |                /
             \_______________|_______________/
                             |
                   +---------------------+
                   |  OPERATIONAL PLANE  |
                   +---------------------+
                             |
                   +---------------------+
                   |  RESEARCH LAB       |
                   | isolated experiments|
                   +---------------------+
```

The Control Plane orchestrates **intent, policy, plans, transactions, verification and evidence**. Networking implementations remain replaceable providers/capabilities.

## 4. Architecture principles

### AP-01 Local First

Local networking must continue when the panel or optional remote Control Plane is unavailable.

### AP-02 Independent Nodes / Last Known Good

Windows, VPS and Keenetic nodes preserve safe operational state when disconnected from orchestration.

### AP-03 Fail Closed

Unknown state is not success. Mutation stops when preconditions, identity or read-back cannot be proven.

### AP-04 Read-back Verification

```text
WRITE != SUCCESS
HTTP 200 != SUCCESS
exit code 0 != full success
```

Desired and actual state are compared after mutation.

### AP-05 Stable Core Wrapping

V6.3.1 is wrapped behind contracts before replacement is considered. Migration is not a rewrite-first program.

### AP-06 Capability Discovery

Do not hard-code assumptions from marketing model names, guessed CPU architecture, guessed firmware or guessed installed packages.

### AP-07 Provider/Plugin Boundaries

New technologies enter through explicit provider contracts rather than scattered special-case buttons.

### AP-08 Research Isolation

Experimental network transports and packet-manipulation research cannot affect Operational Plane automatically.

### AP-09 Secrets Out of Source

Secrets are references to a secure provider, never ordinary config/documentation/evidence values.

### AP-10 Human-readable Explainability

Every important status/warning answers: what happened, why, impact, current effective behavior and recovery action.

### AP-11 Runtime Truth Is External

GitHub/CI prove engineering properties; physical network behavior requires trusted runtime evidence.

## 5. Sources of truth inside the product architecture

```text
Desired State      = what the owner/policy wants
Observed State     = what probes actually see
Effective State    = what is active now
Reason             = why Effective differs from Desired
```

Example:

```yaml
desired: VPS_MAIN
observed: VPS_MAIN_UNREACHABLE
effective: DIRECT
reason: fallback_policy
```

These states must never collapse into a single ambiguous field.

## 6. Current-to-target map

### 6.1 Current imported candidate foundations

The sanitized RC14.38 truth provides transition foundations for:

- selective routing;
- Status Center;
- observability and evidence;
- diagnostics and support bundles;
- functional self-consistency gates;
- multi-VPS;
- strict browser mode;
- Hyper-V gateway;
- Keenetic read-only probing;
- Entware read-only inventory and guarded package refresh/upgrade;
- portable storage and safe backup;
- dual-tunnel control;
- deep telemetry split from UI-thread work.

### 6.2 Not yet equivalent to target architecture

The current candidate is not evidence that the following target pieces are complete:

- standalone Control Plane service/API;
- Web-first UI;
- formal Windows/VPS/Keenetic agent protocol;
- complete Desired/Observed/Effective persistence model;
- generic transaction engine across domains;
- production RCI mutation layer;
- safe automatic Entware install/remove;
- generic plugin/marketplace trust lifecycle;
- mobile endpoint lifecycle;
- remote-home provider abstraction;
- broad transport/plugin catalog;
- autonomous product release/runtime qualification.

## 7. Control Experience

### 7.1 Web-first target

Long-term UI target:

- SPA or equivalent modern frontend;
- local Control Plane HTTP API;
- SSE/WebSocket or equivalent event/status streaming;
- localhost binding by default;
- LAN/remote exposure only by explicit policy.

The framework is intentionally not selected by this architecture document.

### 7.2 Transitional desktop

Current WinForms remains supported as a migration shell.

Direction:

```text
WinForms business logic
    -> extracted domain contracts
    -> shared Control Plane/API
    -> WinForms becomes client/shell
```

A future desktop shell may embed/reuse the Web UI, but this is not a current requirement.

### 7.3 CLI

CLI is a first-class interface using the same domain layer:

```text
pncc status
pncc routes show
pncc vps health
pncc keenetic status
pncc entware status
pncc scenario plan <name>
pncc scenario run <name>
```

No separate hidden CLI business logic.

## 8. Control Plane

Target responsibilities:

- Node/Capability Registry;
- State Coordinator;
- Policy Engine;
- Scenario Engine;
- Transaction Manager;
- Event/Audit Service;
- Backup Coordinator;
- Secrets Provider abstraction;
- Plugin/External Panel Registry;
- health aggregation;
- support/evidence export.

The Control Plane may initially run locally on Windows. Later deployment may include a dedicated home Linux VM or optional VPS instance, but **no single location becomes mandatory for basic local network operation**.

## 9. Windows Agent

### 9.1 Responsibilities

- selective routing;
- V6.3.1 adapter;
- Proxifier provider;
- process/browser discovery;
- strict browser controls;
- firewall-scoped operations;
- Hyper-V selective gateway;
- diagnostics/telemetry;
- local runtime evidence.

### 9.2 Stable routing adapter contract

```text
GetRoutingStatus()
GetRoutingConfig()
PlanRoutingChange()
ApplyRoutingChange()
VerifyRouting()
RollbackToLKG()
GetTelemetry()
```

Initial implementation may wrap legacy PowerShell internals.

### 9.3 Proxy-routing provider boundary

```text
ProxyRoutingProvider
  - Proxifier        [current baseline]
  - ProxiFyre        [research]
  - ProxyBridge      [research]
  - future TUN/core  [research]
```

Replacement requires A/B runtime qualification and rollback proof.

## 10. Tunnel architecture

Permanent contract:

```text
PRIMARY_AUTO    127.0.0.1:1081   lifecycle=AUTO
RESERVE_MANUAL  127.0.0.1:1080   lifecycle=MANUAL_ONLY
```

Rules:

- both may be visible, diagnosable and selectable when healthy;
- automation owns lifecycle only for 1081;
- automation never start/stops/restarts/recovers 1080;
- automatic failover to manually reserved 1080 is forbidden unless a future explicit architecture decision changes the contract;
- expected endpoint/VPS identity is read back before route trust;
- password transport follows DPAPI-at-rest + PuTTY `-pwfile` only;
- host-key verification remains fail-closed.

## 11. VPS Agent

### Phase V1 — managed SSH provider

- identity and reachability;
- CPU/RAM/disk/load/network;
- listening ports / failed services;
- package status;
- safe service operations;
- backups;
- logs and terminal;
- transport-host inventory.

### Phase V2 — optional native lightweight agent

Potential advantages:

- structured responses;
- explicit transaction IDs;
- streaming metrics;
- reduced shell-parsing ambiguity;
- versioned contract.

Native agent adoption is optional and evidence-driven.

### Docker provider

Optional capability for inventory/start/stop/logs/health/backup/update. Arbitrary untrusted container deployment is out of scope.

## 12. Keenetic bounded context

```text
Keenetic Adapter
  +-- KeeneticOS Provider (RCI target)
  +-- CLI Provider
  +-- Entware Provider (SSH/OPKG)
  +-- Policy Provider
  +-- Storage Provider
  +-- KeenDNS Provider
  +-- Module/External Panel Providers
```

Keenetic remains a managed critical network node, not the preferred central application server.

## 13. KeeneticOS / RCI provider

### K0 — discovery/read-only

Target inventory:

- auth/capability discovery;
- version/model/hardware ID;
- components;
- interfaces;
- devices;
- DNS;
- policies/routes;
- storage;
- relevant VPN/KeenDNS state.

### K1 — safe known mutations

Every supported mutation:

```text
CAPABILITY CHECK
 -> SNAPSHOT/BACKUP
 -> PLAN
 -> WRITE
 -> PARSE BODY/STATUS
 -> READ BACK
 -> COMPARE DESIRED/ACTUAL
 -> SAVE IF REQUIRED
 -> VERIFY PERSISTENCE
```

No generic arbitrary RCI JSON mutation button in normal UI.

## 14. Keenetic CLI provider

CLI/SSH is used for:

- diagnostics;
- allowlisted operations where API abstraction is insufficient;
- recovery/compatibility discovery.

Arbitrary terminal access remains an explicitly advanced tool, separate from automated allowlisted mutations.

## 15. Entware provider

Target state machine:

```text
UNKNOWN
NOT_INSTALLED
PRECHECK
READY
INSTALLING
VERIFYING
HEALTHY
UPDATE_AVAILABLE
DEGRADED
PARTIAL
RECOVERY_REQUIRED
```

### Current boundary

Inventory and guarded update/upgrade exist in candidate truth; full install/remove remains blocked.

### Target install transaction

```text
router snapshot
 -> storage validation
 -> component validation
 -> architecture discovery
 -> qualified source/version
 -> checksum/signature policy
 -> install
 -> verify /opt + opkg + init
 -> reboot persistence test
 -> evidence
```

### Target remove transaction

```text
inventory
 -> backup
 -> stop PNCC-owned services
 -> detach managed OPKG environment
 -> remove only owned artifacts
 -> verify base router networking
 -> retain recovery bundle
```

Blind recursive deletion is forbidden.

## 16. Node / Capability / Policy / Transport / Scenario model

### Node

```yaml
id:
type: windows|vps|keenetic|vm|mobile
name:
capabilities: []
health:
last_seen:
software_version:
```

### Capability

```yaml
id:
provider:
operations:
  read: []
  mutate: []
  destructive: []
health_probe:
version:
trust_level:
```

### Policy

```yaml
id:
scope:
  apps: []
  domains: []
  devices: []
preferred_route:
fallbacks: []
health_requirements:
dns_policy:
failure_mode:
```

### Transport

```yaml
id:
plugin:
node:
tcp:
udp:
config_schema:
health_probe:
install_contract:
rollback_contract:
```

### Scenario

```yaml
id:
desired_state:
preconditions:
steps:
validation:
rollback:
```

## 17. Transaction Manager

Every mutation receives `operation_id`.

Lifecycle:

```text
CREATED
PRECHECK
PLANNED
CONFIRMED
EXECUTING
VERIFYING
COMMITTED
or
ROLLING_BACK
ROLLED_BACK
FAILED
```

Dangerous operations include affected resources, backup ID and rollback path before execution.

## 18. Event and health architecture

Append-only event shape:

```yaml
timestamp:
severity:
domain:
node:
operation_id:
action:
result:
reason:
```

Domains include System, Routing, Windows, VPS, Keenetic, Entware, Security and Research.

Health is explainable, not just a score. UI must retain contributing reasons and freshness.

## 19. Backup and secrets

### Backup classes

- safe configuration backup;
- node backup;
- encrypted secret backup;
- research evidence bundle.

Research evidence is never treated as operational backup.

### Secret provider

```text
SecretProvider
  - DPAPI CurrentUser [current Windows baseline]
  - future Windows Credential Manager / encrypted vault
```

References use identifiers such as:

```yaml
credential_ref: secret://vps/main
```

Secret values never enter ordinary config, Git or support bundles.

## 20. External panel integration

PNCC is an orchestrator, not a clone of every external panel.

Integration modes:

```text
LINK
STATUS_ADAPTER
API_ADAPTER
MANAGED_SERVICE
```

Potential references include RouteBox, 3x-ui, LucX-UI, XKeen Dashboard, Entware UI/Manager, Netdata and other verified projects.

Every managed external component requires provenance, version, license, dependencies, health, update and rollback contracts.

## 21. Plugin architecture

Categories:

```text
TransportPlugin
NodeAdapter
MonitoringPlugin
ExternalPanelAdapter
InstallerPlugin
ResearchPlugin
```

Lifecycle:

```text
DISCOVERED
QUALIFIED
INSTALLED
ENABLED
HEALTHY
DEGRADED
DISABLED
UPDATE_AVAILABLE
QUARANTINED
REMOVED
```

Trust levels:

```text
CORE
VERIFIED_UPSTREAM
COMMUNITY_VERIFIED
LAB_ONLY
UNTRUSTED
```

No marketplace implementation is authorized by this document alone.

## 22. Research Lab architecture

Research state is physically/logically separated from operational configuration.

Experiment contract:

```yaml
experiment_id:
hypothesis:
scenario:
baseline:
transports: []
metrics: []
safety_boundary:
cleanup:
```

Evidence includes config hash, exact software versions, node state, timestamps, metrics, logs and conclusion.

Operational promotion requires separate fact/security/license review plus controlled runtime evidence.

## 23. Remote and mobile target

Mobile is initially an endpoint, not the primary Control Plane.

Potential future capabilities:

- device registration;
- profile/QR delivery;
- last-seen/health;
- active route/transport;
- home return path;
- per-app/policy integration where platform support allows.

Remote home access is a provider abstraction, not synonymous with KeenDNS:

```text
RemoteAccessProvider
  KeenDNSWeb
  KeeneticVPN
  VPSRelay
  AWG
  Xray
  MasterDnsVPN
  WDTT / future verified providers
```

Each remains subject to fact verification and runtime qualification.

## 24. Monitoring architecture

Three levels:

1. native lightweight probes;
2. optional node collectors;
3. optional external observability (Netdata/Prometheus/Grafana).

The Control Center consumes normalized metrics and does not couple core product semantics to one monitoring stack.

## 25. Web security baseline

Phase 1:

- localhost by default;
- LAN exposure disabled unless configured.

Remote mode requires at minimum:

- HTTPS;
- authenticated sessions;
- CSRF protection where applicable;
- rate limiting;
- audit trail;
- secret redaction;
- explicit trust/network boundary.

A public unauthenticated or weakly authenticated management endpoint is not an accepted default.

## 26. Failure semantics

- Panel offline -> agents retain safe/LKG state.
- Control Plane offline -> active routing continues.
- VPS offline -> affected policy becomes degraded/fallback according to explicit policy; local networking remains.
- Keenetic API offline -> no destructive blind retries.
- Entware degraded -> base Keenetic networking remains isolated from Entware failure.
- Unknown third-party module -> quarantine/no automatic start.
- Version drift -> capability rediscovery; incompatible mutation blocks fail-closed.

## 27. Product deployment evolution

### Phase P0 — current transition baseline

```text
Windows 10
  WinForms V7 / RC14.x candidate
  modular PowerShell
  V6.3.1 external immutable rollback
  Proxifier
  PuTTY/Plink
  VPS via SSH
  Keenetic read-only/Entware foundations
```

### Phase P1 — explicit internal contracts

Extract stable interfaces for routing, state, events, transactions, VPS and Keenetic without rewriting working data plane.

### Phase P2 — local Control Plane API

Expose shared domain services through a local API while keeping current UI compatible.

### Phase P3 — Web UI in parallel

Build Web UI as another client of the same API. No routing-engine rewrite is required for UI migration.

### Phase P4 — agent separation

Move Windows/VPS/Keenetic execution behind explicit versioned contracts.

### Phase P5 — broader plugin/research ecosystem

Only after core contracts, transactions, evidence and runtime qualification are mature.

## 28. Development plane boundary

```text
GitHub / ADWF / coding agents
           |
      engineering changes
           |
        repository
           |
      exact candidate
           |
trusted local Runtime Evidence Plane
           |
Windows / VPS / Keenetic
```

Development tooling never becomes runtime truth by itself.

`PIPE-WU-001` is a development-state foundation and is not part of this product architecture reconciliation.

## 29. Architecture acceptance criteria for major product migration

Major migration beyond the transitional V7 shell should require evidence that:

1. current routing baseline remains recoverable through immutable V6.3.1;
2. dual-tunnel lifecycle invariants remain enforced;
3. Control Plane can stop without destroying active networking;
4. Desired/Observed/Effective state exists as explicit contracts;
5. mutation transactions have operation IDs and read-back verification;
6. support bundles remain secret-safe;
7. Keenetic exact capability discovery works before mutation;
8. Entware failure cannot break base router networking;
9. VPS loss cannot silently break unrelated DIRECT behavior;
10. Research Lab cannot mutate Operational Plane by default;
11. Web/CLI clients can be added without rewriting routing contracts;
12. runtime qualification uses exact candidate identity and trusted node evidence.

## 30. Final target shape

```text
                    USER / AUTOMATION
                          |
                +---------+---------+
                |                   |
              Web UI               CLI
                |                   |
                +---------+---------+
                          |
                    CONTROL PLANE
                          |
        +-----------------+-------------------+
        |                 |                   |
   Windows Agent      VPS Agent(s)       Keenetic Adapter
        |                 |                   |
 V6.3.1/Provider     Linux/Services      RCI/CLI/Entware
        |                 |                   |
        +-----------------+-------------------+
                          |
             Policy / State / Transactions
                          |
                 Events / Metrics / Backup
                          |
              +-----------+-----------+
              |                       |
       Operational Plane        Research Lab
                                      |
                            qualified experiments
                                      |
                                   Evidence
```

**Core rule:** PNCC manages intent, policy, plans, verification and evidence; concrete network mechanisms remain replaceable, capability-discovered and evidence-qualified.
