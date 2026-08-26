# PNCC Product Intent Registry

**Status:** AUTHORITATIVE PRODUCT INTENT REGISTRY  
**Reconciled:** 2026-08-26  
**Repository base used for reconciliation:** `e45603bdcecb48a0efd83f6a71a6458b25f959a8`  
**Historical source:** owner Master Ideas Registry consolidated 2026-08-24  
**Tracking:** Issue #9 (`DOC-001`)

## 1. Purpose

This file preserves product intent without converting ideas into implementation truth.

It is the durable successor of the 2026-08-24 Master Ideas Registry. The source registry intentionally contained current capabilities, requirements, hypotheses, external technologies, research directions and unverified claims in one place. This reconciliation preserves that breadth while separating **intent** from **fact**, **target architecture**, **roadmap**, **implementation** and **runtime evidence**.

Nothing becomes an approved implementation merely because it appears here.

## 2. Authority and promotion flow

```text
PRODUCT_INTENT_REGISTRY
        |
        v
FACT_VERIFICATION_REGISTRY
        |
        v
PNCC_TARGET_ARCHITECTURE
        |
        v
Product Roadmap / bounded Work Unit
        |
        v
Implementation / CI
        |
        v
Exact Candidate Artifact
        |
        v
Trusted Runtime Evidence
```

Mandatory security/runtime invariants in `AGENTS.md`, `SECURITY.md` and accepted ADRs override product intent.

Fresh provider/runtime evidence overrides stale historical state claims. Historical intent is not deleted when facts change; its status is changed and the reason is retained.

## 3. Reconciliation delta from 2026-08-24

The following historical assumptions are now corrected:

- `v7.0.0-rc12` is no longer the current migration reference. The public repository contains a **sanitized RC14.38 migration snapshot** under `legacy/v7-rc14.38-sanitized/`.
- Exact private migration candidate tracked by repository policy is `v7.0.0-rc14.38`, SHA-256 `6d81137519a363ebf3d8503f33a344d8fdc75848d517cf732cb6d6d02394d727`.
- V6.3.1 remains the immutable stable rollback baseline, SHA-256 `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e`.
- GitHub migration is no longer merely `DECISION_NEEDED`: public GitHub is the accepted Product / Engineering Truth plane.
- PNCC is explicitly an **ADWF consumer**, not part of ADWF. Development-pipeline integration is governed upstream through version-pinned consumer contracts/project packs.
- `127.0.0.1:1081 = PRIMARY_AUTO`; `127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY`. Both may be visible/diagnosable/routable, but automation must never autonomously start/stop/restart/recover 1080.
- Stable/DONE remains forbidden without fresh Windows runtime evidence.

## 4. Intent status vocabulary

- `CURRENT_EVIDENCED` — present in repository capability truth; runtime quality may still be pending.
- `STABILIZE` — existing capability that should be hardened before expansion.
- `TARGET` — accepted direction for product architecture, not necessarily implemented.
- `HIGH_VALUE` — high-value product direction requiring prioritization.
- `RESEARCH` — requires verification/experiment before architecture promotion.
- `LAB_ONLY` — isolated research capability; no automatic Operational Plane promotion.
- `DEFERRED` — intentionally postponed.
- `REJECTED` — not selected; rationale must be retained.
- `UNVERIFIED_CLAIM` — source claim without sufficient evidence.
- `BLOCKED_RUNTIME` — cannot be promoted without real node/runtime qualification.

## 5. Product identity and top-level intent

PNCC evolves from VPS Control Center into a **local-first distributed network control platform**.

Core intent:

```text
Panel / CLI / API
        |
        v
Control Plane
        |
        +--> Windows Agent
        +--> VPS Agent(s)
        +--> Keenetic Adapter
        +--> VM Agent(s)
        +--> future Mobile Endpoints
        |
        +--> Operational Plane
        +--> isolated Research Lab
```

The product manages **intent, policy, plan, verification and evidence**. Concrete networking mechanisms are replaceable capabilities/providers.

## 6. Non-negotiable product invariants

1. Loss of Control Panel must not equal loss of networking.
2. Loss of VPS must not destroy local control or unmatched DIRECT traffic.
3. Loss of Internet must not destroy LAN-local management capability.
4. Unknown mutation state is not success.
5. Mutation follows `precheck -> plan -> execute -> read-back -> verify -> commit/rollback`.
6. Dangerous/destructive operations require backup/recovery path.
7. Experimental transports remain isolated from Operational Plane until promoted by evidence.
8. Secrets stay outside source, support bundles and public evidence.
9. V6.3.1 is wrapped by explicit contracts before any replacement/rewrite is considered.
10. Capability discovery is preferred over guessed model/version/architecture.
11. Product UI must explain what is happening, why, impact and recovery.
12. Product architecture must remain compatible with real Windows 10 / Windows PowerShell 5.1 runtime qualification while tooling may evolve independently.

## 7. Current evidenced product capability baseline

The sanitized RC14.38 Capability Truth currently records the following implemented boundaries. `IMPLEMENTED` here is not equivalent to full product/runtime qualification.

- selective Windows routing with guarded mutation;
- Status Center read-only aggregation;
- observability/events/telemetry;
- diagnostics, snapshot and sanitized debug bundles;
- functional-consistency self-gates;
- strict Yandex/Edge browser mode with process-scoped TCP plus guarded UDP/QUIC controls;
- multi-VPS inventory/health/switch with guarded mutation;
- selective Hyper-V SOCKS gateway with guarded mutation;
- Keenetic probe read-only;
- Entware inventory read-only;
- guarded/confirmed `opkg update` and `opkg upgrade` when evidence permits;
- full Entware install/remove intentionally blocked pending stronger runtime evidence;
- portable V7 storage;
- safe backups excluding secrets;
- isolated demo mode;
- deep telemetry / forensic evidence split;
- permanent dual-tunnel registry with automated lifecycle authority only for 1081.

## 8. Product domains to preserve

### 8.1 Windows

`STABILIZE / TARGET`

- selective routing by service/app/browser/domain/IP;
- Proxifier profile lifecycle, visualization, backup/restore and drift detection;
- browser policies and strict mode;
- local diagnostics and support bundle;
- Hyper-V selective gateway;
- future proxy-routing provider abstraction;
- no mandatory full-VPN model for all Windows traffic.

### 8.2 VPS

`HIGH_VALUE / TARGET`

- multi-VPS inventory, health, comparison and explicit selection;
- CPU/RAM/disk/load/network/service status;
- managed service lifecycle;
- backup/restore;
- optional Docker provider;
- terminal/SSH tooling;
- optional lightweight native VPS agent later;
- VPS must not become a mandatory single point of failure.

### 8.3 Keenetic

`HIGH_VALUE / TARGET`

Keenetic remains a large bounded context, not a small settings page.

Preserve intent for:

- exact model/version/component discovery;
- KeeneticOS read-only state;
- RCI provider with read-back verification;
- allowlisted CLI provider;
- Entware inventory/install/update/remove transaction lifecycle;
- storage provider;
- policy/scenario provider;
- KeenDNS status provider;
- module/external-panel adapters;
- backup/recovery and diagnostics.

Keenetic is a managed node, not the preferred heavy central Control Plane host.

### 8.4 Control Panel / API / CLI

`TARGET`

- Web-first Control Center remains the long-term direction;
- current WinForms remains a transitional shell until backend/API contracts are mature;
- CLI is a first-class interface using the same domain/API layer;
- WebSocket/SSE or equivalent event delivery may be used for live status;
- local-only binding is the default; remote access requires explicit security architecture.

### 8.5 State / policy / scenario model

`HIGH_VALUE / TARGET`

Preserve explicit separation:

```text
Desired State
Observed State
Effective State
Reason
```

Policies evolve beyond hard-coded `DIRECT / VPS` into scope + preferred route/transport + fallbacks + health criteria + DNS policy + failure mode.

Scenario execution preserves transaction semantics and rollback.

### 8.6 Events / monitoring / supportability

`HIGH_VALUE / TARGET`

- append-only normalized event model;
- explainable health tree;
- operation/correlation IDs;
- sanitized support bundles;
- optional external observability (Netdata/Prometheus/Grafana) behind an abstraction, not a core dependency.

### 8.7 Research Lab

`DO_NOT_DROP / HIGH_VALUE / LAB_ONLY`

Maintain a separate Network Research Lab for reproducible transport/security experiments with:

- hypothesis;
- scenario;
- baseline;
- transport under test;
- safety boundary;
- metrics;
- cleanup/rollback;
- evidence bundle;
- promotion decision.

Technology lifecycle:

```text
DISCOVERED -> LAB_ONLY -> TESTED -> VALIDATED -> APPROVED_FOR_OPERATIONAL
                                                \-> DEPRECATED / REJECTED
```

## 9. Research technology registry

Presence below means **preserve for evaluation**, not approval.

### Mainstream / transport cores

WireGuard, AmneziaWG, Shadowsocks, SSTP, L2TP, Tor, Xray-core, VLESS, REALITY, Trojan, VMess, sing-box, mihomo.

### DPI / packet manipulation research

zapret, nfqws, keenetic-zapret2-manager, Zapret2 Manager, zapret4rocket, GoodbyeDPI, NoDPI, ByeDPI, RIPDPI, SonicDPI, B4.

### Keenetic ecosystem

XKeen, XKeen-Dashboard, bypass_keenetic_dev, HydraRoute, 6to4tunnel, Entware Manager, Entware GUI, KeenDNS.

### DNS tunneling / constrained transport research

MasterDnsVPN, MasterDnsWeb, DNSTT, SlipStream.

### Relay / whitelist / unusual transport research

WDTT, freeturn/wdtt, proxy-turn-vk-android, rjsxrd, whitelist-bypass projects, TG WS Proxy, CDN-based concepts, Yandex-CDN concepts, WARP-related chains, ENTRY/EXIT architectures, Bird4Static-related routing concepts.

### Windows routing alternatives

ProxiFyre, ProxyBridge, tun2proxy, tun2socks, Wintun-based routing, sing-box/Xray provider experiments. Proxifier remains the current baseline until A/B qualification proves a replacement.

### External panels / integration references

RouteBox, 3x-ui, LucX-UI, XKeen Dashboard, Entware UI/Manager, Netdata, MasterDnsWeb, future verified panels.

## 10. Explicit preserved corrections/rejections

- `Proximac` — `REJECTED_FOR_WINDOWS` because the verified upstream is macOS/Xcode; retain only as historical reference.
- original `NekoRay` upstream — `DEPRECATED_REFERENCE`; archived upstream must not become a new strategic backend.
- direct RouteBox-on-Keenetic — not an accepted fact; requires a separate porting feasibility test.
- official MasterDnsVPN Android/iOS client — corrected: upstream did not provide official mobile apps in the 2026-08-24 verification snapshot.
- AWG 3.1 — remains unverified in the source snapshot; do not encode as product assumption.
- universal mobile/provider AWG presets — remain research hypotheses, not defaults.
- arbitrary KeenDNS Cloud TCP/UDP tunneling — contradicted by the source verification; treat KeenDNS Cloud primarily as constrained web reachability plus separately documented VPN scenarios.
- destructive Entware cleanup by blind `rm -rf /opt` — rejected.

## 11. Product ideas intentionally deferred from immediate implementation

- replacing Proxifier before comparative runtime qualification;
- public remote Web UI by default;
- heavy Control Plane on Keenetic;
- mandatory VPS-hosted Control Plane;
- destructive automatic Entware install/remove before transaction evidence;
- large transport/plugin marketplace before plugin trust/lifecycle contracts;
- mobile endpoint implementation before stable agent/control contracts;
- automatic promotion from research to operational state;
- Kubernetes/enterprise-cluster complexity without demonstrated need.

## 12. Relationship to development pipeline

This registry describes **what the product may become**. It does not schedule work.

The accepted development pipeline in `docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md` and `docs/roadmap/PNCC_PIPELINE_ROADMAP.md` describes **how PNCC is developed safely and durably**.

`PIPE-WU-001` / Issue #8 is a development-state work unit and is intentionally outside this documentation reconciliation.

## 13. Preservation rule

Ideas are never silently dropped.

When an item leaves active consideration, record:

```text
status: REJECTED | DEFERRED | SUPERSEDED | DEPRECATED
reason:
evidence:
decision_date:
revisit_conditions:
```

The registry is a **Source of Intent**, not an implementation backlog.
