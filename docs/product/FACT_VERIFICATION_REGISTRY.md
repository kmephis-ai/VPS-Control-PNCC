# PNCC Fact Verification Registry

**Status:** AUTHORITATIVE FACT/CLAIM REGISTRY  
**Reconciled:** 2026-08-26  
**Repository base used for reconciliation:** `e45603bdcecb48a0efd83f6a71a6458b25f959a8`  
**Historical external-verification snapshot:** 2026-08-24  
**Tracking:** Issue #9 (`DOC-001`)

## 1. Purpose

This registry prevents product ideas, old chat state, third-party marketing claims and target architecture from silently becoming facts.

It reconciles the owner-provided 2026-08-24 `FACT_VERIFICATION.md` with current repository truth. **External technology claims were not re-researched in DOC-001**; their 2026-08-24 status is preserved with its date. A later research work unit may refresh them independently.

## 2. Claim classes

- `VERIFIED_CURRENT_REPO` — supported by current repository/provider state at the reconciliation base.
- `VERIFIED_PROJECT_EVIDENCE` — supported by imported project capability/evidence records, but not necessarily by a new physical runtime run in this work unit.
- `VERIFIED_2026-08-24` — externally verified in the historical source snapshot; not refreshed here.
- `VERIFIED_WITH_LIMITS_2026-08-24` — source snapshot verified the core claim with material limits.
- `PARTIALLY_VERIFIED_2026-08-24` — only part of the source claim was verified.
- `UNVERIFIED` — insufficient evidence.
- `CORRECTED` — historical wording was wrong or over-broad.
- `SUPERSEDED` — once true project state replaced by a newer authoritative state.

A status never means automatic approval for implementation.

## 3. Authority rules

For **current PNCC state**:

```text
Fresh GitHub/provider/runtime evidence
    > current repository Capability Truth
    > reconciled Fact Registry
    > historical documents/chat claims
```

For **external technologies**, a dated verification status remains dated until a new verification pass updates it.

Mandatory security/runtime invariants in `AGENTS.md`, `SECURITY.md` and accepted ADRs are not weakened by any lower-level fact entry.

## 4. Current PNCC project facts

| Claim | Status | Evidence / boundary |
|---|---|---|
| Public GitHub is Product / Engineering Truth | `VERIFIED_CURRENT_REPO` | README, AGENTS, ADR-0001 |
| Local PNCC data is private Instance Configuration Truth | `VERIFIED_CURRENT_REPO` | README, AGENTS, ADR-0001 |
| Real Windows/Keenetic/VPS nodes are Runtime Truth | `VERIFIED_CURRENT_REPO` | README, AGENTS, ADR-0001 |
| CI success is not physical runtime qualification | `VERIFIED_CURRENT_REPO` | README/AGENTS and accepted pipeline architecture |
| Current public migration snapshot is sanitized `v7.0.0-rc14.38` | `VERIFIED_CURRENT_REPO` | `legacy/v7-rc14.38-sanitized/` |
| Exact private migration candidate SHA-256 is `6d81137519a363ebf3d8503f33a344d8fdc75848d517cf732cb6d6d02394d727` | `VERIFIED_CURRENT_REPO` | README/AGENTS migration state |
| RC14.38 is Stable/DONE | `CONTRADICTED` | repository explicitly forbids this claim without fresh Windows runtime evidence |
| V6.3.1 is immutable rollback baseline | `VERIFIED_CURRENT_REPO` | AGENTS/README |
| V6.3.1 expected SHA-256 is `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e` | `VERIFIED_CURRENT_REPO` | AGENTS/README |
| `127.0.0.1:1081 = PRIMARY_AUTO` | `VERIFIED_CURRENT_REPO` | AGENTS + RC14.38 architecture/capability truth |
| `127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY` | `VERIFIED_CURRENT_REPO` | AGENTS + RC14.38 architecture/capability truth |
| PNCC automation may automatically recover 1080 | `CONTRADICTED` | explicitly forbidden |
| Passwords are DPAPI-at-rest and PuTTY password transport uses `-pwfile` only | `VERIFIED_CURRENT_REPO` | AGENTS + RC14.38 capability truth |
| Host-key verification may be disabled for convenience | `CONTRADICTED` | fail-closed host-key policy is mandatory |
| PNCC is an ADWF consumer rather than part of ADWF | `VERIFIED_CURRENT_REPO` | AGENTS + ADR-0002/pipeline architecture |
| GitHub/Codex migration is still only a future decision | `SUPERSEDED` | public GitHub migration baseline and repository-native development model now exist |
| `PIPE-WU-001` is implemented | `CONTRADICTED` | Issue #8 is a separate ready work unit; DOC-001 does not implement it |

## 5. Current implemented-capability facts from sanitized RC14.38 truth

The statements below mean the implementation path exists in the imported candidate truth. They **do not** claim a fresh E2E PASS in DOC-001.

| Capability | Reconciled status | Boundary |
|---|---|---|
| Selective Windows routing | `VERIFIED_PROJECT_EVIDENCE` | implemented / guarded mutation; unmatched traffic remains DIRECT |
| Status Center | `VERIFIED_PROJECT_EVIDENCE` | implemented / read-only |
| Observability/events | `VERIFIED_PROJECT_EVIDENCE` | implemented / read-only |
| Diagnostics/support evidence | `VERIFIED_PROJECT_EVIDENCE` | implemented / read-only, secret-redacted |
| Functional consistency self-gates | `VERIFIED_PROJECT_EVIDENCE` | implemented / fail-closed |
| Strict browser mode | `VERIFIED_PROJECT_EVIDENCE` | guarded mutation; TCP/UDP/QUIC controls |
| Multi-VPS | `VERIFIED_PROJECT_EVIDENCE` | implemented / guarded mutation |
| Hyper-V selective gateway | `VERIFIED_PROJECT_EVIDENCE` | implemented / guarded mutation |
| Keenetic probe | `VERIFIED_PROJECT_EVIDENCE` | implemented / read-only |
| Entware inventory | `VERIFIED_PROJECT_EVIDENCE` | implemented / read-only |
| Entware `opkg update` / `upgrade` | `VERIFIED_PROJECT_EVIDENCE` | confirmed mutation behind evidence/confirmation gates |
| Full Entware install/remove | `VERIFIED_PROJECT_EVIDENCE` as `BLOCKED` | transaction/readiness planning exists; destructive action remains blocked |
| Portable V7 storage | `VERIFIED_PROJECT_EVIDENCE` | implemented |
| Safe backup | `VERIFIED_PROJECT_EVIDENCE` | excludes secret-like material |
| Demo mode | `VERIFIED_PROJECT_EVIDENCE` | no real mutation |
| Deep telemetry / forensic evidence split | `VERIFIED_PROJECT_EVIDENCE` | heavy evidence moved off UI path |
| Dual-tunnel registry | `VERIFIED_PROJECT_EVIDENCE` | permanent model; automatic lifecycle authority only for 1081 |

## 6. Historical project facts corrected during reconciliation

| Historical 2026-08-24 claim | Reconciled result |
|---|---|
| Current line is `v7.0.0-rc12` | `SUPERSEDED` by sanitized RC14.38 migration baseline |
| GitHub/Codex migration remains future architecture decision | `SUPERSEDED`; GitHub Product/Engineering Truth is established |
| ADWF relationship remains undecided | `SUPERSEDED`; PNCC is an ADWF consumer with upstream version-pinned contract boundary |
| Current tunnel model can be inferred from older 1080-only/1081-only snapshots | `SUPERSEDED`; RC14.29+ permanent dual-tunnel contract is authoritative |
| Product architecture document may describe current capability | `CORRECTED`; target architecture is not capability truth |

## 7. External technology verification snapshot — 2026-08-24

This section preserves the source verification result. It is **not** a claim that release/version/activity data remains current on 2026-08-26 unless separately reverified.

### Keenetic KN-1012 / KeeneticOS / Entware

- KN-1012 existence and official OPKG support — `VERIFIED_2026-08-24`.
- Regional marketing name may be Giga/Hero; use hardware/model identity instead of marketing name — `VERIFIED_WITH_LIMITS_2026-08-24`.
- Source snapshot recorded MT7981B 1.3 GHz dual-core, 512 MB DDR4, 256 MB flash, USB 2/3 and OPKG support — `VERIFIED_2026-08-24`.
- Hard-coding Entware architecture as `aarch64` only from model name — `CORRECTED`; runtime architecture discovery is required.
- Entware safe removal by blind `rm -rf /opt/*` — `CORRECTED`; use inventory/backup/owned-resource cleanup/read-back transaction.

### KeenDNS

- Works with private WAN IP for supported Cloud-mode web access — `VERIFIED_WITH_LIMITS_2026-08-24`.
- Universal arbitrary TCP/UDP tunnel via Cloud mode — `CORRECTED`.
- Cloud mode CLI access — `CORRECTED` / not supported by source snapshot.
- Remote LAN scenarios may use separately documented VPN paths — `VERIFIED_WITH_LIMITS_2026-08-24`.

### Keenetic RCI

- RCI/HTTP JSON interface exists in de-facto implementations — `VERIFIED_WITH_LIMITS_2026-08-24`.
- Single complete modern public official specification — `UNVERIFIED` in source snapshot.
- Challenge-response authentication and CLI-tree mirroring behavior — `VERIFIED_2026-08-24` by third-party live research, not official normative spec.
- HTTP 200 always means mutation success — `CORRECTED`; body/read-back must be parsed.
- Production mutation policy remains: capability check -> snapshot -> write -> parse status -> read-back -> compare -> save if required -> verify persistence.

### AmneziaVPN / AmneziaWG

- AWG 3.0 exists and was supported by AmneziaVPN 5.0.0.5+ in source snapshot — `VERIFIED_2026-08-24`.
- AWG3 backward compatibility with AWG2 — `CORRECTED`; source snapshot recorded incompatibility.
- AWG 3.1 as an established fact — `UNVERIFIED`.
- universal Jc/Jmin/Jmax/S1-S4 mobile/provider presets — `PARTIALLY_VERIFIED_2026-08-24`; parameter ecosystem exists, universal tuning claims do not.

### MasterDnsVPN

- Project existence/activity and Linux ARM64 artifacts — `VERIFIED_2026-08-24`.
- TOML configuration and SOCKS5/TCP modes — `VERIFIED_2026-08-24`.
- official upstream Android/iOS app — `CORRECTED`; source snapshot recorded no official mobile app and a community Android client.
- guaranteed superiority / guaranteed censorship resilience / exact universal overhead claims — `UNVERIFIED`.

### XKeen

- project/community fork existence and KeeneticOS 5+/Xray/Mihomo/user-policy/DNS-proxying claims in source README — `VERIFIED_WITH_LIMITS_2026-08-24`.
- exact sticky-channel counts, fingerprint diagnostics or universal bypass guarantees — `UNVERIFIED`.

### RouteBox

- project and Linux router/VPS panel mode — `VERIFIED_2026-08-24`.
- direct ready-to-install Keenetic/Entware plugin — `CORRECTED`; documented router mode expected conventional Linux/systemd/TUN/gateway environment.

### 3x-ui / LucX-UI

- 3x-ui active external panel/reference — `VERIFIED_WITH_LIMITS_2026-08-24`; source snapshot also recorded fresh bug reports and therefore no Control Plane core dependency recommendation.
- LucX-UI existence and AmneziaWG-related feature set — `VERIFIED_2026-08-24`.
- LucX-specific license boundary (PolyForm Noncommercial 1.0.0 versus inherited GPL-3.0 code) — `VERIFIED_2026-08-24`; legal/provenance review required before reuse.

### Windows routing alternatives

- ProxiFyre Windows TCP+UDP per-app/service/JSON capability — `VERIFIED_2026-08-24`; high-value A/B research candidate, not approved replacement.
- ProxyBridge Windows multi-platform TCP/UDP/per-process claims — `VERIFIED_WITH_LIMITS_2026-08-24`; maturity/security/performance still require qualification.
- Proximac as Windows alternative — `CORRECTED`; verified upstream was macOS/Xcode.
- original NekoRay upstream strategic dependency — `CORRECTED`; source snapshot recorded archived upstream.
- sing-box active transport/routing core candidate — `VERIFIED_2026-08-24`; research/plugin candidate, not automatic V6.3.1 replacement.

### Research queue not fully verified in source snapshot

The following remain `UNVERIFIED` or `PARTIALLY_VERIFIED` until exact-upstream research is performed:

- B4;
- SonicDPI;
- rjsxrd / whitelist-bypass projects;
- HydraRoute;
- 6to4tunnel;
- Bird4Static integration claims;
- TG WS Proxy;
- WDTT / FreeTURN / proxy-turn-vk-android;
- exact Zapret/NFQWS manager compatibility with target Keenetic model;
- SharX exact upstream/current capability.

## 8. Architecture facts that may be relied upon now

The following are safe as **architecture premises**, not claims of completed implementation:

1. Separate Product/Engineering Truth, private Instance Configuration Truth and Runtime Truth.
2. Local-first multi-node design.
3. Windows, VPS and Keenetic as separate bounded adapters/nodes.
4. Stable routing core wrapping before replacement.
5. Capability discovery instead of model/version assumptions.
6. Desired/Observed/Effective state separation as target design.
7. Transaction/read-back/rollback semantics for mutation.
8. Research Lab isolation.
9. External tools integrated through adapters/providers rather than copied blindly.
10. GitHub/ADWF development plane remains separate from product runtime plane.

## 9. Verification backlog preserved

### Before Keenetic mutation

- exact auth path;
- model/hardware ID/version/components;
- storage and architecture discovery;
- RCI read-back semantics;
- configuration backup/save semantics.

### Before Entware install/remove

- exact architecture/installer selection;
- storage identifiers/filesystem/free space;
- required Keenetic components;
- startup/reboot persistence;
- owned-resource uninstall transaction.

### Before transport promotion

- exact upstream/version/license/security model;
- Windows/VPS/Keenetic/mobile support;
- TCP/UDP/per-app/per-domain behavior;
- controlled benchmark and rollback.

### Before Proxifier replacement

- ProxiFyre/ProxyBridge/other provider A/B tests;
- driver provenance and privilege boundary;
- UDP/QUIC/DNS/LAN behavior;
- performance and recovery;
- exact rollback proof.

## 10. Update rule

A new third-party technology may move from Product Intent into Target Architecture only through:

```text
RAW IDEA
 -> FACT VERIFICATION
 -> SECURITY / LICENSE / MAINTENANCE REVIEW
 -> CONTROLLED RESEARCH IF NEEDED
 -> ARCHITECTURE DECISION
 -> BOUNDED WORK UNIT
 -> IMPLEMENTATION
 -> RUNTIME EVIDENCE
```

Never overwrite the previous conclusion without retaining provenance, date and reason for change.
