# VPS Control Center v7.0.0 — Capability Truth

## RC14.39 delta — governed build-input activation

- source version aligned after the proven VPS/Keenetic `-pwfile` remediation;
- deterministic candidate-build inputs may be READY in hosted engineering truth;
- no RC14.39 ZIP exists in this transaction;
- runtime and promotion authority remain false;
- `1081=PRIMARY_AUTO`, `1080=RESERVE_MANUAL/MANUAL_ONLY`, V6.3.1 immutable.

# VPS Control Center v7.0.0-rc14.38 — Capability Truth

## RC14.38 delta — Windows PowerShell 5.1 script-encoding correction

Fresh Windows validation of exact RC14.37 proved a packaging defect, not a tunnel/runtime-policy change: the three modified PowerShell files lost their UTF-8 BOM and were mis-decoded by Windows PowerShell 5.1, causing AST parser failures.

RC14.38 restores the package-wide PowerShell encoding invariant: all `.ps1` files are UTF-8 with BOM. RC14.37 functional changes are otherwise preserved exactly. `1081=PRIMARY_AUTO`, `1080=RESERVE_MANUAL/MANUAL_ONLY`, V6.3.1 remains immutable, DPAPI-at-rest and PuTTY `-pwfile` remain unchanged, and host-key verification remains fail-closed.

Stable/DONE remains forbidden without fresh Windows runtime evidence.

# VPS Control Center v7.0.0-rc14.38 — Capability Truth

## RC14.38 delta — fail-closed consistency self-gate correction

Fresh Windows runtime evidence for exact RC14.36 proved `PRODUCT_DEFECT`: `PUTTY_PWFILE_ACL_AT_CREATION` falsely failed because `$env:LOCALAPPDATA` was expanded inside a double-quoted source marker before `.Contains()` compared it with the implementation text. The secure credential implementation itself was not changed by this correction.

RC14.38:
- treats `$env:LOCALAPPDATA` as a literal source marker in the two mandatory pwfile policy checks;
- makes the consistency-marker safety check inspect `modules\V7-Consistency.ps1` itself;
- keeps `1081=PRIMARY_AUTO`, `1080=RESERVE_MANUAL/MANUAL_ONLY`, V6.3.1 immutable, DPAPI at rest, PuTTY `-pwfile` only, and host-key verification fail-closed.

Stable/DONE remains forbidden without fresh Windows runtime evidence.

# VPS Control Center v7.0.0-rc14.36 — Capability Truth

## RC14.36 delta — PSScriptAnalyzer warning-budget remediation

Exact RC14.35 was classified `PRODUCT_DEFECT` by fresh Windows Validation Lab v1.0.3 evidence because warning count was 510 while the RC14.34 ratchet budget is 508. RC14.36 changes only the warning-producing implementation form of the SecureString staging helper introduced in RC14.35: approved `ConvertTo-*` verb plus non-empty debug-only disposal catches.

No runtime capability is added or removed. The permanent contract remains:
- `127.0.0.1:1081` = `PRIMARY_AUTO`;
- `127.0.0.1:1080` = `RESERVE_MANUAL` / `MANUAL_ONLY`;
- VCC must never automatically start/stop/recover 1080;
- V6.3.1 is immutable;
- password remains DPAPI-at-rest and PuTTY transport remains `-pwfile`;
- host-key verification is fail-closed and may not be disabled.

Stable/DONE remains forbidden without fresh Windows runtime evidence.

# VPS Control Center v7.0.0-rc14.35 — Capability Truth

## RC14.35 delta — PSScriptAnalyzer Error remediation

Validation Lab isolated four blocking analyzer errors in RC14.34.

RC14.35:
- renames evidence-worker parameter `$Error` to `$ErrorText`, avoiding collision with PowerShell's automatic `$Error` variable;
- removes `ConvertTo-SecureString -AsPlainText -Force` from VPS and Keenetic secret persistence;
- constructs `SecureString` explicitly with `SecureString.AppendChar()` + `MakeReadOnly()`;
- retains `ConvertFrom-SecureString` without an explicit key, preserving Windows DPAPI encrypted-at-rest compatibility;
- changes `Save-KeeneticConfig` to receive a `SecureString` secret rather than a plain password parameter;
- disposes temporary `SecureString` instances after persistence.

No stored password reset or migration is required.

## RC14.34 delta — privilege-free secure `-pwfile` creation

Post-failure evidence from the first runtime-valid RC14.33 run proved:
- host-key trust bridge PASS (`imported` then `existing-identical`);
- three recovery Apply attempts failed before PuTTY launch;
- exact failure: `Set-Acl ...\temp\credentials` → `PrivilegeNotHeldException / SeSecurityPrivilege`.

RC14.34 removes that dependency:
- credential temp storage moves to `%LOCALAPPDATA%\VPS-Control-v6.3\secure-credentials`;
- no password file is created under YandexDisk/portable DataRoot;
- `FileSecurity` is supplied to the .NET Framework `FileStream` constructor at `CreateNew` time;
- DACL contains only current-user and SYSTEM allow rules, with inheritance disabled;
- post-create `Set-Acl` and `SetOwner` are forbidden;
- ACL is read back and verified before the path is returned to PuTTY;
- file deletion semantics after the tunnel identity gate remain unchanged.

No VPS password change is required.

## RC14.33 delta — exact Windows PowerShell 5.1 parser fix

Read-only AST forensic on RC14.32 located the only parse failure at `VPS-Control-v7-tunnel-manager.ps1`, line 498, column 143: the manual-reserve host-key trust call was missing one closing parenthesis.

RC14.33 removes the fragile nested cast/call form entirely:
- `$remoteHost` and `$remotePort` are assigned explicitly;
- `Ensure-V7OfficialPuttyHostKeyTrust` is invoked as a normal multi-line command;
- its Boolean result is stored in `$hostKeyTrustOk`;
- `if(-not $hostKeyTrustOk)` performs the fail-closed decision.

Host-key trust policy, dual-tunnel lifecycle policy, routing policy and credential policy are unchanged.

## RC14.32 delta — PowerShell 5.1 parser-safe host-key bridge

RC14.31 was rejected before mutation by the candidate AST gate because the new tunnel-manager host-key helper used an overly compact expression form that Windows PowerShell 5.1 did not parse.

RC14.32 keeps the same trust model and behavior but rewrites the host-key helper in explicit parser-safe form:
- separate validation branches for root/host/port;
- explicit `$valueNames` collection before `-contains`;
- explicit `$verifyKey` object before `GetValue`;
- no compact multi-operator conditions in the new trust bridge.

No trust policy is weakened and no runtime behavior is intentionally changed.

## RC14.31 delta — official PuTTY host-key trust bridge

Fresh read-only Windows evidence proved `HOSTKEY_STORE_SPLIT_CONFIRMED`: the active VPS `203.0.113.10:22` has an identical trusted `ssh-ed25519` key in both portable `SshHostKeys` stores, while official PuTTY HKCU `SshHostKeys` contains no target key.

RC14.31 therefore bridges **only pre-existing portable trust** into official PuTTY:
- source: portable `SshHostKeys` beside the active VCC PuTTY launcher;
- target: `HKCU\Software\SimonTatham\PuTTY\SshHostKeys`;
- scope: active VPS host + SSH port only;
- identical Registry value → PASS;
- missing portable trust → FAIL CLOSED;
- conflicting Registry value → FAIL CLOSED, never overwrite;
- unknown host key acceptance and host-key verification disabling remain forbidden.

This bridge is used for VCC-managed PRIMARY_AUTO/1081 and for explicit manual VCC creation of RESERVE_MANUAL/1080. An already user-started/adopted 1080 process is not restarted or rewritten.


## RC14.30 delta — externally-started manual reserve adoption

`RESERVE_MANUAL` remains strictly `MANUAL_ONLY`, but an already-running user-started PuTTY-family listener on 1080 is now a first-class reserve object.

Ownership modes:
- `VCC_MANUAL_EXPLICIT` — explicit `-D 127.0.0.1:1080` started manually from VCC.
- `USER_MANUAL_SAVEDSESSION` — user-started PuTTY `-load <SavedSession>` matching the active VPS profile.
- `USER_MANUAL_EXTERNAL_VERIFIED` — PuTTY-family listener on 1080 whose exit identity matches the expected active VPS.

Adoption never grants automatic start/stop/recovery authority. Route selection to 1080 remains fail-closed unless expected VPS identity is healthy. Manual Stop from the UI may stop the exact adopted reserve listener because it is an explicit owner action.


## RC14.29 delta — dual-tunnel contract + credential transport hardening

`DUAL_TUNNEL_CONTROL` — IMPLEMENTED / RUNTIME_PENDING.

- `PRIMARY_AUTO` = `127.0.0.1:1081`: visible, diagnosed, manually controllable and automatically start/recovery-managed.
- `RESERVE_MANUAL` = `127.0.0.1:1080`: equally visible/diagnosed/telemetered and manually start/stop/test controllable, but **never automatically started, stopped or recovered**.
- Current/future capabilities default to both tunnel records unless the capability is lifecycle automation, where `1080` is explicitly excluded.
- Generated Proxifier profile contains both proxy records (`100 → 1081`, `101 → 1080`). All VPS rules use the tunnel selected manually in `runtime/tunnel-routing.json`; selecting 1080 is fail-closed unless its expected VPS identity is healthy. No automatic tunnel-selection failover is allowed.
- DPAPI password transport no longer permits PuTTY `-pw`; PuTTY 0.77+ `-pwfile` with an ACL-protected temporary file is required and the file is removed after tunnel establishment.

Stable eligibility remains false until RC14.29 passes Windows runtime evidence.

## RC14.28 delta — serialized recovery mutation

VCC SOCKS 1081 automatic recovery is runtime-proven on RC14.27, but RC14.28 adds cross-process mutation serialization and fixes the `$PID` collision discovered in that evidence. Stable eligibility remains pending a clean repeated recovery with one surviving VCC-owned D1081 process and no STOP_VCC_SOCKS failures.


## RC14.27 delta — portable SavedSession metadata

Portable SavedSession endpoint extraction supports native `Name\value\` file storage as well as registry/INI forms. Historical RC14.27 used an isolated 1081-only contract; RC14.29 supersedes it with DUAL_TUNNEL_CONTROL.


## RC14.26 delta — capability taxonomy correction

Build/integrity check `GENERATED_ENGINE_VARIABLE_COLON_SAFE` remains required and fail-closed in `V7-Consistency.ps1`, but is no longer declared using runtime-capability syntax. Runtime Capability Truth is reserved for user/runtime capabilities represented in `Get-V7CapabilityRegistry`.


## RC14.25 delta — generated-engine interpolation safety

Build integrity gate GENERATED_ENGINE_VARIABLE_COLON_SAFE — IMPLEMENTED / FAIL_CLOSED: generated V6.5 templates reject bare `$Variable:` forms that would fail Windows PowerShell parsing; colon-adjacent interpolation uses `${Variable}:`. No routing or recovery semantics changed.


## RC14.24 delta — consistency contract alignment

`FUNCTIONAL_CONSISTENCY` — IMPLEMENTED / FAIL_CLOSED: PowerShell automatic-variable collision checks now pass with `$remoteHost`; GUI PuTTY trace explicitly proves `guiPuttyBatch=false`; `PUTTY_BINARY` and structured `PUTTY_START` provide machine-verifiable SSH transport/binary/source evidence. No routing/recovery semantics changed.


## RC14.23 delta — consistency initialization integrity

`FUNCTIONAL_CONSISTENCY` remains FAIL_CLOSED. Observability source text is initialized before exclusive-endpoint evaluation, and build-time regression validation rejects consistency text variables used before assignment. No network behavior changed.


## RC14.22 delta — StrictMode-safe marker checks

`FUNCTIONAL_CONSISTENCY` remains FAIL_CLOSED. Marker checks for generated engine content no longer expand `$PuttySession` or related runtime variables during candidate preflight under Windows PowerShell 5.1. No routing/recovery behavior changed.


## RC14.21 delta — VCC SOCKS 1081-only

HISTORICAL / SUPERSEDED: RC14.21–RC14.28 temporarily used an isolated 1081-only boundary. RC14.29 supersedes that design: 1080 is a first-class RESERVE_MANUAL tunnel while automatic lifecycle remains exclusive to 1081.


## RC14.19 delta — literal quote application grammar

`PROXIFIER_APPLICATION_LIST_GRAMMAR` = IMPLEMENTED / RUNTIME_PENDING. Whitespace-containing application filenames are serialized with literal double quotes in XML element text, not `&quot;`. The runtime gate must reject entity-quoted application tokens, whitespace tokens without literal quotes, and whitespace around semicolon separators. RC14.18 helper lifecycle remains implemented and requires regression confirmation.


## RC14.18 delta — bounded Proxifier silent-load helper lifecycle

`PROXIFIER_PROFILE_LOAD_LIFECYCLE` = IMPLEMENTED / RUNTIME_PENDING. The generated V6.5 loader tracks the exact spawned helper PID, bounds wait time, preserves cold-start behavior, and permits cleanup only when a pre-existing primary Standard Proxifier remains alive and the helper's parent/path/command identity is proven. RC14.17 evidence is the trigger for this work unit; RC14.18 itself is not considered PASS until fresh Windows runtime evidence reports zero persistent silent-load helpers.


## RC14.17 delta — PS5.1 StrictMode-safe consistency

`FUNCTIONAL_CONSISTENCY` remains IMPLEMENTED / FAIL_CLOSED. The literal marker `$replacements['Ensure-SocksTunnel']` is now tested without variable expansion, so Windows PowerShell 5.1 `Set-StrictMode` cannot fail on an unset `$replacements` variable during candidate preflight. No routing/runtime behavior changes.


## RC14.16 delta — dynamic version consistency

`FUNCTIONAL_CONSISTENCY` остаётся IMPLEMENTED / FAIL_CLOSED, но version contract исправлен: проверки current release используют переданный `$UiVersion`, а README/Architecture/Capability Truth проверяются по первой непустой строке. Launcher содержит explicit `$LauncherVersion`, который должен совпадать с UI version. Это integrity-plane-only изменение; RC14.15 Proxifier application-list grammar fix сохранён, V6.3.1 не изменяется.


`DEEP_TELEMETRY` — IMPLEMENTED: 30-second LIGHT telemetry на UI thread + asynchronous `VPS-Control-v7-evidence-worker.ps1` для тяжёлого forensic evidence. Heavy CIM/socket/hash/EventLog collection не выполняется из WinForms timer.

`SELECTIVE_ROUTING` — STABILIZED: GUI PuTTY/portable PuTTY никогда не получает Plink-only `-batch`; portable SavedSession auto-start разрешён только при известном DPAPI/legacy password, `.ppk` или Pageant. Без credential — explicit `CREDENTIAL_REQUIRED`, без popup/stall.

# VPS Control Center v7.0.0-rc14.15 — Capability Truth

## RC14.15 Proxifier profile grammar

Runtime screenshot RC14.14 proved a modal Proxifier parser failure: `Error in application list: Unexpected blank space found`. RC14.15 is rebuilt from exact RC14.13 and changes only generated V6.5 `New-ProxifierProfile` application-list serialization: separators are `;` without surrounding blanks, and whitespace-containing application tokens are double-quoted before XML escaping. RC14.14 transient-helper lifecycle experiment is intentionally not carried forward. Status remains RC until fresh Windows 10 / PowerShell 5.1 evidence proves profile load, watchdog, process lifecycle and routing.


## RC14.12 delta

`FUNCTIONAL_CONSISTENCY` — `IMPLEMENTED / READ_ONLY`: fail-closed startup self-check приведён в соответствие с фактическим portable SavedSession contract RC14.11+ и теперь читает capability IDs как из canonical table, так и из explicit current-RC delta declarations. RC14.12 не ослабляет проверки и не добавляет network mutation.

RC14.11 Windows evidence: AST/SHA/WinForms preflight прошли, но startup был остановлен двумя ложными consistency errors (`PORTABLE_PUTTY_SAVED_SESSION_COMPAT` и `TRUTH_CAP_DEEP_TELEMETRY`). Эти два drift-дефекта исправлены в RC14.12.

## RC14.11 delta

`DEEP_TELEMETRY` — `IMPLEMENTED / READ_ONLY`: continuous sanitized runtime metrics, state-transition trace, per-operation evidence (Engine/VPS/Keenetic), environment snapshots, host/network counters, colocated PuTTY artifact metadata, rate-limited automatic incident capture and full debug export.

`SELECTIVE_ROUTING` / `MULTI_VPS` runtime truth strengthened: colocated `PuTTY PORTABLE\putty_portable.exe` has discovery priority; portable SavedSession metadata may be parsed read-only; RC14.11 historical note: opaque credentials were tested with `-batch`; RC14.13 supersedes this because GUI PuTTY does not support Plink-only `-batch`. This is not yet an E2E PASS until Windows evidence confirms `127.0.0.1:1080` and expected VPS exit.

No secrets are intentionally written to telemetry. Entware install/remove remains blocked as before.

---

# Историческая база RC14.10 — Capability Truth

Ниже сохранена историческая таблица RC14.10; актуальный delta RC14.11 находится выше. Таблица фиксировала **фактическое состояние возможностей RC14.10**. Он не является roadmap и не должен описывать будущую функцию как уже доступную.

Статусы:

- `IMPLEMENTED` — код и пользовательский путь присутствуют в RC14.10; реальная работоспособность всё равно требует Windows runtime evidence.
- `READ_ONLY` — реализовано только чтение/диагностика, без изменения целевой системы.
- `GUARDED_MUTATION` / `CONFIRMED_MUTATION` — изменение существует, но проходит через явные проверки/подтверждение.
- `BLOCKED` — mutation намеренно отсутствует или заблокирована; наличие UI-плана не означает наличие операции.

| ID | Возможность | Текущее состояние | UI | Фактическая граница |
|---|---|---|---|---|
| `SELECTIVE_ROUTING` | Выборочная маршрутизация Windows | `IMPLEMENTED / GUARDED_MUTATION` | Статус | V6.5 генерируется из внешнего V6.3.1; unmatched Windows traffic остаётся DIRECT. При сохранённых AUTO/VPS V7 восстанавливает отсутствующий SOCKS/watchdog через Apply с backoff 30/60/120/300 секунд; tight loop и отдельный Scheduled Task не создаются. |
| `STATUS_CENTER` | Единый Status Center | `IMPLEMENTED / READ_ONLY` | Статус | Агрегирует runtime/evidence и не выполняет network mutation. |
| `OBSERVABILITY` | Telemetry, AUTO history, events | `IMPLEMENTED / READ_ONLY` | Наблюдение / События | Читает evidence движка и V7 event log. |
| `DIAGNOSTICS` | Self-test, readiness, snapshot, SOCKS debug report | `IMPLEMENTED / READ_ONLY` | Диагностика | Snapshot и `SOCKS-debug-*.txt` очищены от паролей, DPAPI blobs, private key contents и `-pw` values. SOCKS report объединяет V7 recovery trace, V6.5 tunnel trace и legacy controller/watchdog logs. |
| `FUNCTIONAL_CONSISTENCY` | Проверка «заявлено ↔ реализовано» | `IMPLEMENTED / READ_ONLY` | Диагностика | Сверяет version/docs/manifest/module wiring/GUI helper actions; package root передаётся явно и отделён от modules/data roots; ошибки startup-level блокируют запуск. |
| `STRICT_BROWSER` | Строгий режим Yandex/Edge | `IMPLEMENTED / GUARDED_MUTATION` | Дополнительно | Process-scoped TCP через Proxifier + UDP firewall block + `--disable-quic`; требует UAC для firewall. |
| `MULTI_VPS` | Несколько VPS / health / switch | `IMPLEMENTED / GUARDED_MUTATION` | VPS-серверы | Переключение требует свежего health preflight; при failed Apply метаданные active VPS откатываются. Standard HKCU SavedSession проверяет metadata/credential/forwarding. Portable SavedSession не считается отсутствующей только из-за пустого SimonTatham HKCU: legacy-compatible `-load` допускается при подтверждённом password source, а окончательная truth — фактический SOCKS/VPS identity. |
| `VM_GATEWAY` | Выборочный SOCKS gateway для Hyper-V | `IMPLEMENTED / GUARDED_MUTATION` | Дополнительно | Только конкретный vEthernet IPv4; `0.0.0.0`, loopback и full/default-route VPN не используются. Install/remove требуют явного подтверждения перед UAC. |
| `KEENETIC_PROBE` | Probe роутера | `IMPLEMENTED / READ_ONLY` | Keenetic | ICMP/TCP/HTTP evidence накапливается отдельно; merge использует snapshot ключей и не должен падать при обновлении OrderedDictionary. |
| `ENTWARE_STATUS` | Inventory Entware | `IMPLEMENTED / READ_ONLY` | Keenetic | SSH read-only; password-mode требует сохранённый DPAPI secret. `NOT_DETECTED` — валидное состояние `NOT_INSTALLED`, а не failure. Host key привязывается без интерактивного password prompt: read-only plink probe получает SHA256 fingerprint, UI требует явного подтверждения, затем batch использует pinned `-hostkey` + DPAPI secret. |
| `ENTWARE_REFRESH` | `opkg update` | `IMPLEMENTED / CONFIRMED_MUTATION` | Keenetic | Разрешается только после свежего evidence `EntwareState=INSTALLED`, DPAPI secret и подтверждения. |
| `ENTWARE_UPGRADE` | `opkg update + opkg upgrade` | `IMPLEMENTED / CONFIRMED_MUTATION` | Keenetic | Разрешается только после свежего evidence `EntwareState=INSTALLED`, DPAPI secret и подтверждения. |
| `ENTWARE_INSTALL_REMOVE` | Полная установка/удаление Entware | `BLOCKED` | Keenetic / План установки / удаления | В RC14.10 есть только readiness/transaction plan. `MUTATION=BLOCKED_RUNTIME_EVIDENCE_REQUIRED`. Install/remove action отсутствует. |
| `PORTABLE_STORAGE` | Portable V7 storage | `IMPLEMENTED / GUARDED_MUTATION` | Настройки | Смена каталога применяется после перезапуска; старые данные не удаляются автоматически. |
| `SAFE_BACKUP` | Safe backup | `IMPLEMENTED` | Настройки | DPAPI secrets/password/private-key-like files исключаются. |
| `DEMO` | Изолированный demo mode | `IMPLEMENTED / NO_REAL_MUTATION` | `VPS-Control-v7-demo.cmd` | Synthetic runtime/evidence; VPS/Keenetic/firewall/VM mutations заблокированы. |

## Подтверждённое Windows startup evidence

Серия последовательных реальных запусков на Windows 10 / Windows PowerShell 5.1 дала ступенчатое runtime evidence: parser/package-root/consistency/WinForms дефекты ранних RC исправлены; RC14.5 открыл основной GUI; RC14.6–RC14.8 квалифицировали runtime/SSH/Keenetic границы; RC14.9 deep trace показал конкретный SOCKS blocker — ложное требование standard HKCU session для configured portable PuTTY — и overlapping recovery race. RC14.10 исправляет именно эти observed defects. Полный E2E PASS всех возможностей ещё не подтверждён.


## RC14.10 runtime qualification delta

RC14.10 усиливает truth существующих `SELECTIVE_ROUTING` и `MULTI_VPS`, не создавая новую capability:
- `SavedSession` имеет два различимых provider paths: `HKCU` и `PORTABLE_OPAQUE`;
- absence of standard registry session больше не равна absence of portable session;
- legacy portable path сохраняет доказанные V6.3.1 launch arguments и требует реальный password source;
- `SOCKS/VPS identity` является read-back verification после запуска;
- recovery имеет single in-flight/completion lease;
- явный engine `[FAIL]` перекрывает ошибочный native `rc=0`.

RC14.10 остаётся Release Candidate до повторного Windows runtime evidence с фактическим поднятием `127.0.0.1:1080` и expected VPS exit.

## RC14.8 runtime qualification delta

RC14.8 не добавляет новые capability. Он усиливает truth существующих `SELECTIVE_ROUTING`, `MULTI_VPS` и `ENTWARE_STATUS`: повторяемый runtime recovery с backoff, явная credential truth SavedSession, гарантированный SOCKS forwarding и pinned SHA256 host key для Keenetic без повторного password prompt.

## Что RC14.8 НЕ утверждает

RC14.8 **подтверждает запуск основного WinForms GUI** на Windows 10 / Windows PowerShell 5.1 по runtime evidence RC14.5. Это не равно полному E2E PASS всех функций: Keenetic/VPS/VM/strict-browser цепочки продолжают проверяться отдельно, поэтому релиз остаётся Release Candidate.

RC14.8 **не содержит** стабильный `VPS-Control-v6.3.1.ps1`: он должен оставаться внешней неизменяемой rollback-базой рядом с V7 при рабочем запуске.

RC14.8 **не реализует** полную установку или удаление Entware, RCI mutation Keenetic, новые VPN/transports, Web Control Plane или полный VPN всей Windows.


## RC14.8 runtime evidence rule

`runtime-state.json` старше 300 секунд считается устаревшим evidence. RC14.8 не показывает его `Effective/Health` как текущее «Сейчас» и не должен превращать старый `FAILED` в новый route failure. При этом текущие локальные зависимости (watchdog/SOCKS/Proxifier/storage) оцениваются отдельно и fail-closed не ослабляются.


## RC14.10 runtime observability boundary

Оставшийся SOCKS failure считается **не квалифицированным**, пока нет `socks-runtime.log` + `socks-engine.log` либо единого `SOCKS-debug-*.txt`. RC14.10 автоматически собирает correlation evidence без секретов; подробный trace является диагностикой, а не новой network mutation.
