# VPS Control Center v7.0.0-rc14.39 — Candidate build-input activation

RC14.39 is the first governed candidate-source identity derived from the admitted post-RC14.38 credential-remediation baseline. The deterministic build recipe is declared separately; no candidate artifact is created by this source-identity transaction. Runtime/promotion authority remains false.

# VPS Control Center v7.0.0-rc14.38 — Windows PowerShell 5.1 encoding correction

Fresh Windows Validation Lab v1.0.4 evidence for exact RC14.37 classified the candidate as `PRODUCT_DEFECT`: the three RC14.37-modified PowerShell files were written as UTF-8 without BOM. Windows PowerShell 5.1 therefore decoded their Cyrillic source text through the legacy ANSI path, producing parser failures before runtime.

RC14.38 is intentionally narrow:
- restore UTF-8 BOM on every `.ps1` package file, matching the proven RC14.36 packaging convention;
- retain the RC14.37 consistency self-gate interpolation fix unchanged;
- no routing, tunnel lifecycle, credential, DPAPI, PuTTY `-pwfile`, host-key, generated-engine, or V6.3.1 behavior is changed.

Stable/DONE still requires fresh Windows validation and controlled runtime evidence.

# VPS Control Center v7.0.0-rc14.38 — runtime self-gate interpolation correction

Fresh Windows runtime-gate evidence for exact RC14.36 proved a product startup defect in `PUTTY_PWFILE_ACL_AT_CREATION`: the implementation already used `%LOCALAPPDATA%`, creation-time `FileSecurity`, `FileStream CreateNew`, no post-create `Set-Acl`, and no `SetOwner`, but `V7-Consistency.ps1` embedded `$env:LOCALAPPDATA` inside an unescaped double-quoted `.Contains()` marker. PowerShell expanded the environment variable before source comparison, so the mandatory self-gate falsely reported a declaration/implementation gap and stopped startup before generated V6.5 creation.

RC14.38 is intentionally narrow:
- escape the literal `$env:LOCALAPPDATA` marker in both engine-upgrade and tunnel-manager self-checks;
- make `CONSISTENCY_MARKER_STRICTMODE_SAFE` inspect `V7-Consistency.ps1` itself rather than the unrelated strict-browser helper, so this regression class is fail-closed;
- no credential implementation, tunnel lifecycle, routing, host-key, DPAPI, `-pwfile`, generated-engine, or immutable V6.3.1 semantics are changed.

Stable/DONE still requires fresh Windows validation and controlled runtime evidence.

# VPS Control Center v7.0.0-rc14.36 — warning-budget remediation delta

RC14.36 is intentionally narrow. Windows Validation Lab v1.0.3 classified exact RC14.35 as `PRODUCT_DEFECT` only because PSScriptAnalyzer warning count was 510 against the ratchet budget of 508.

The RC14.35 SecureString staging helper introduced three warnings: one `PSUseShouldProcessForStateChangingFunctions` warning from the `New-*` verb and two `PSAvoidUsingEmptyCatchBlock` warnings in disposal cleanup. RC14.35 simultaneously removed one pre-existing automatic-variable warning by renaming `$Error` to `$ErrorText`, producing the observed net +2.

RC14.36 renames the pure conversion helper to `ConvertTo-V7SecureStringFromText` and makes both disposal catches non-empty with generic debug-only diagnostics. Routing, dual-tunnel lifecycle, DPAPI-at-rest, `-pwfile` transport, host-key verification, generated engine semantics and immutable V6.3.1 remain unchanged.

> Runtime/stable claims still require fresh Windows evidence.

# VPS Control Center v7.0.0-rc14.35 — analyzer-clean secret staging

RC14.35 is an evidence-driven PSScriptAnalyzer remediation. Plain UI text is staged into a short-lived `SecureString` with `AppendChar()` / `MakeReadOnly()`, then persisted through the existing Windows DPAPI-compatible `ConvertFrom-SecureString` format. The evidence worker no longer declares an `$Error` parameter.

# VPS Control Center v7.0.0-rc14.34 — privilege-free credential transport

RC14.34 replaces post-create `Set-Acl` on the cloud-synced portable DataRoot with creation-time Windows `FileSecurity` on a local `%LOCALAPPDATA%` temporary password file. This preserves `-pwfile` secrecy without requiring `SeSecurityPrivilege` and without changing the user's VPS password.

# VPS Control Center v7.0.0-rc14.33 — exact parser-forensic correction

RC14.33 is the evidence-driven syntax correction of RC14.32. Windows PowerShell 5.1 forensic evidence identified one missing closing parenthesis in the manual 1080 host-key bridge call. The call is now rewritten using explicit host/port variables and a stored Boolean result, eliminating nested parser ambiguity without changing architecture or trust policy.

# VPS Control Center v7.0.0-rc14.32 — parser-safe trusted host-key bridge

RC14.32 is a syntax-correctness revision of RC14.31. The portable-trust → official-PuTTY Registry bridge remains fail-closed and unchanged semantically; only the PowerShell 5.1 implementation form has been expanded to avoid parser ambiguity.

# VPS Control Center v7.0.0-rc14.31 — trusted host-key bridge

RC14.31 resolves the proven storage split between Russian PuTTY Portable and official PuTTY. The active VPS host key already trusted by the owner in portable `SshHostKeys` is copied into official PuTTY's HKCU host-key cache before managed SSH launch. No trust-on-first-use bypass is introduced: absent portable trust or any Registry conflict blocks the tunnel.

# VPS Control Center v7.0.0-rc14.30 — manual reserve adoption architecture

RC14.30 extends the dual-tunnel model so `RESERVE_MANUAL/1080` can be started either from the VCC UI or externally by the owner. A user-started PuTTY SavedSession remains manual-only but can be adopted for visibility, diagnostics, routing selection and explicit manual stop.

Adoption proof is bounded to PuTTY-family listener ownership plus one of: explicit `D1080`, matching active SavedSession, or expected VPS exit identity. Automatic lifecycle authority is never inferred from adoption.

# VPS Control Center v7.0.0-rc14.29 — dual-tunnel control architecture

RC14.29 introduces the permanent tunnel registry:

```text
PRIMARY_AUTO    127.0.0.1:1081   lifecycle=AUTO
RESERVE_MANUAL  127.0.0.1:1080   lifecycle=MANUAL_ONLY
```

Both records are first-class UI/diagnostic/telemetry/evidence/routing-capability objects. Only lifecycle automation is asymmetric: runtime recovery/watchdog may mutate `1081`, but must never autonomously start/stop/recover `1080`.

The active Proxifier profile contains both proxy endpoints. All VPS rules use the manually selected tunnel: `PRIMARY_AUTO` maps to proxy id `100`/1081 and `RESERVE_MANUAL` maps to proxy id `101`/1080. Selecting reserve is allowed only after its ownership and expected VPS identity are healthy. Automatic failover to reserve is forbidden; loss of 1080 never triggers automatic start/recovery.

Credential hardening: password values remain DPAPI-at-rest. At process launch they are written only to a short-lived current-user ACL-protected temporary password file and passed with PuTTY `-pwfile`; plaintext `-pw` is forbidden. The temporary file is removed after the tunnel identity gate completes.

# VPS Control Center v7.0.0-rc14.28 — serialized 1081 mutation plane

RC14.28 serializes VCC SOCKS `1081` stop/recovery operations across the UI host and background watchdog with a named Windows mutex. Identity is re-checked after lock acquisition, preventing a waiting recovery actor from launching a second tunnel after another actor has already restored service. Listener ownership uses `$listenerPid`, avoiding collision with PowerShell's read-only `$PID`.

# VPS Control Center v7.0.0-rc14.27 — portable SavedSession parser delta

RC14.27 adds explicit support for the portable PuTTY/KiTTY-family file backend where session properties are persisted as `Name\value\`. SavedSession remains metadata-only: VCC extracts SSH endpoint/auth metadata and creates its own explicit `-D 127.0.0.1:1081` tunnel without `-load`.

# VPS Control Center v7.0.0-rc14.26 — capability taxonomy correction

RC14.26 separates runtime capabilities from build/integrity gates. `GENERATED_ENGINE_VARIABLE_COLON_SAFE` remains a required fail-closed consistency check but is not a runtime capability and therefore is not represented in `Get-V7CapabilityRegistry`. The VCC 1081-only runtime boundary is unchanged.

# VPS Control Center v7.0.0-rc14.25 — generated-engine interpolation safety delta

RC14.25 fixes PowerShell interpolation in generated V6.5 templates where a colon immediately follows a variable. `${SocksPort}:` is used instead of invalid `$SocksPort:`. A required consistency gate rejects future bare variable-colon forms in generated-engine templates. The VCC 1081-only runtime boundary is unchanged.

# VPS Control Center v7.0.0-rc14.24 — consistency contract alignment delta

RC14.24 removes the PowerShell `$Host` collision and aligns consistency checks with the current structured PuTTY trace contract (`SSH_ENDPOINT`, `PUTTY_BINARY`, `PUTTY_START`). `PUTTY_BINARY` explicitly records executable/source and `guiPuttyBatch=false`; `PUTTY_START` records transport/source/VCC endpoint. The 1081-only VCC SOCKS boundary is unchanged.

# VPS Control Center v7.0.0-rc14.23 — consistency initialization delta

RC14.23 initializes the Observability source text before the exclusive 1081 endpoint consistency rule executes. Build-time regression validation rejects any `*Text` consistency variable used before assignment. The VCC 1081-only runtime boundary is unchanged.

# VPS Control Center v7.0.0-rc14.22 — StrictMode-safe consistency delta

RC14.22 is an integrity-plane-only delta over RC14.21. Generated-engine marker checks use literal strings that cannot expand runtime variables under Windows PowerShell 5.1 `Set-StrictMode`. The 1081-only VCC SOCKS architecture is unchanged.

# VPS Control Center v7.0.0-rc14.21 — VCC-managed SOCKS 1081-only boundary

The VCC development/control plane has exactly one SOCKS endpoint: `127.0.0.1:1081`. Port 1080 is external to VCC and has no runtime, monitoring, telemetry, validation, routing-profile or mutation role in this release. SavedSession supplies SSH endpoint/auth metadata only; VCC creates an explicit isolated `-D 127.0.0.1:1081` connection.

# VPS Control Center v7.0.0-rc14.19 — Proxifier application-token XML serialization delta

RC14.19 changes only the generated V6.5 Proxifier application-token serializer. Filenames containing whitespace remain quoted per Proxifier grammar, but the quote characters are preserved literally in XML element text instead of being converted to `&quot;`. XML-sensitive text characters `&`, `<`, `>` remain escaped. RC14.18 bounded helper lifecycle and all routing semantics remain unchanged.

# VPS Control Center v7.0.0-rc14.18 — Proxifier helper lifecycle delta

RC14.18 adds a bounded ownership-verified lifecycle for `Proxifier.exe <profile> silent-load` in the generated V6.5 layer. Existing primary Standard Proxifier is snapshotted before load; only a newly spawned exact child helper may be terminated, and only when the old primary remains alive. Cold-start processes are never terminated by this contract. Routing semantics and immutable V6.3.1 are unchanged.

# VPS Control Center v7.0.0-rc14.17 — PS5.1 StrictMode consistency delta

RC14.17 is an integrity-plane-only delta. The consistency engine now checks the literal engine-upgrade marker `$replacements['Ensure-SocksTunnel']` using a single-quoted PowerShell literal, preventing StrictMode expansion of an unset `$replacements` variable. Routing/runtime behavior is unchanged; RC14.15 Proxifier grammar fix and RC14.16 dynamic version contract remain.

# VPS Control Center v7.0.0-rc14.16 — integrity/version contract delta

RC14.16 не меняет transport/routing architecture. Изменён только consistency contract: version checks больше не привязаны к историческому RC14.13 и валидируют фактический `$UiVersion` через first-non-empty-line declarations README/Architecture/Capability Truth и explicit launcher version marker. RC14.15 Proxifier profile application-list grammar fix сохранён без изменений.

# RC14.13 delta — responsive telemetry + PuTTY/Plink CLI boundary

RC14.13 разделяет Live Operational Telemetry и Forensic Evidence. WinForms timer сохраняет только lightweight state/health/process-count record раз в 30 секунд; recursive filesystem hashing, CIM process enrichment, full socket inventory, adapter statistics и Windows EventLog выполняются только отдельным background worker. Это устраняет UI-thread I/O/CPU stalls, обнаруженные по RC14.12 runtime evidence. GUI `putty.exe`/`putty_portable.exe` использует только доказанный V6.3.1 `-load/-l/-pw` contract; `-batch` разрешён только Plink helpers. Opaque SavedSession без доступного password/key/Pageant больше не запускается интерактивно из background recovery.

# VPS Control Center V7 — архитектурный срез RC14.12


## RC14.12: consistency self-check contract repair

RC14.12 не меняет data plane или network execution. По фактическому Windows startup evidence RC14.11 fail-closed integrity plane остановил запуск на двух ложных расхождениях: static marker `PORTABLE_PUTTY_SAVED_SESSION_COMPAT` продолжал искать удалённую строку старого contract, а Capability Truth parser извлекал capability IDs только из исторической Markdown-таблицы и поэтому не видел текущую delta declaration `DEEP_TELEMETRY`. RC14.12 синхронизирует self-check с фактически реализованным contract и разрешает explicit current-RC truth declarations вместе с canonical table, сохраняя fail-closed семантику.

## RC14.11: colocated toolchain + Continuous Evidence

RC14.11 не меняет selective-routing architecture и не добавляет новый transport. Корень V7 теперь является authority для `PuTTY PORTABLE\`: локальный launcher/toolchain выбирается раньше исторического absolute path из неизменяемого V6.3.1. Portable SavedSession metadata читается только для диагностики; секреты не извлекаются. Исторически RC14.11 допускал opaque `-batch` launch; RC14.13 запрещает его для GUI PuTTY и требует известный credential.

Observability plane расширен отдельным `V7-DeepTelemetry.ps1`:

```text
V7 timer (~15 s)
  -> runtime-metrics.jsonl
  -> state transition detector
  -> diagnostic-trace.jsonl
  -> operation-evidence.jsonl (Engine/VPS/Keenetic outcomes)
  -> rate-limited AUTO-incident-*.txt on degradation

startup / every 30 min / manual export
  -> environment-latest.json
     (OS/network/routes/processes/sockets/package hashes + colocated PuTTY metadata)

manual
  -> FULL-debug-*.txt
```

Telemetry остаётся read-only относительно network state. JSONL логи ротируются, automatic incident bundles сохраняются с bounded retention 30; секреты/DPAPI/private-key contents/tokens/LKG contents не экспортируются.

---

# VPS Control Center V7 — архитектурный срез RC14.10

## RC14.10: portable SavedSession truth + serialized recovery

RC14.9 runtime evidence локализовал SOCKS failure до boundary между V7/V6.5 и portable PuTTY: активный профиль `SavedSession=ExampleVPS` использовал `putty_portable.exe`, но стандартная SimonTatham HKCU session отсутствовала. Это не доказательство отсутствия portable session; стабильный V6.3.1 ранее запускал тот же logical contract через `-load ExampleVPS` и верифицировал результат по SOCKS/VPS identity.

RC14.10 возвращает compatibility invariant без переписывания V6.3.1:

```text
SavedSession + standard HKCU
  -> inspect registry metadata
  -> verify credential truth
  -> use saved D1080 or explicit -D
  -> runtime SOCKS identity verify

SavedSession + portable launcher + HKCU absent
  -> classify PORTABLE_OPAQUE
  -> require effective password source for legacy password-auth contract
  -> launch exact legacy args: -load session -l user -pw <redacted>
  -> DO NOT invent a second -D/-N
  -> runtime SOCKS identity verify is authoritative
```

Вторая correction — recovery ownership. Child process object теперь остаётся operation lease до того, как UI completion handler прочитал exit/output и очистил object. `RuntimeRecoveryAction` дополнительно блокирует повторный recovery. Это закрывает observed race RC14.9, когда следующий Apply стартовал после `HasExited`, но до consumption результата предыдущего.

Третья correction — result truth: native `rc=0` не является PASS для `Apply/RestartTunnel`, если engine output содержит явный `[FAIL]`. Такой outcome участвует в rollback/backoff как failure.

Observability RC14.9 сохраняется:
- `VPS-Control-Data/logs/socks-runtime.log`;
- `VPS-Control-Data/logs/socks-engine.log`;
- `VPS-Control-Data/exports/SOCKS-debug-*.txt`;
- secrets redaction для password/DPAPI/private keys/`-pw` values.

RC14.10 не добавляет новый transport, не меняет default route Windows и не модифицирует стабильный V6.3.1.

## RC14.8: runtime recovery / SSH trust continuity

RC14.7 подтвердил, что GUI и integrity plane запускаются, но выявил два оставшихся сквозных разрыва: одноразовая recovery-попытка не восстанавливала runtime после более позднего возвращения VPS, а SSH password/host-key boundary мог уходить в скрытый/интерактивный prompt. RC14.8 закрывает эти разрывы без изменения V6.3.1.

- recovery state machine: saved AUTO/VPS -> inspect SOCKS/watchdog -> Apply -> verify -> exponential-like bounded backoff 30/60/120/300s -> retry while UI alive;
- SavedSession credential truth: password from V7 DPAPI/legacy source либо valid saved key/Pageant; иначе fail-closed с явной инструкцией;
- SavedSession SOCKS contract: D1080 из PuTTY session либо command-line `-D 127.0.0.1:1080 -N`;
- Keenetic trust boundary: read-only fingerprint probe -> explicit owner confirmation -> local pinned SHA256 -> `plink -hostkey` + DPAPI secret;
- interactive PuTTY перестаёт быть обязательным шагом для Entware automation.

## История RC14.7
RC14 — стабилизационный инкремент поверх RC13. Он не добавляет новый transport stack и не меняет проверенный routing-engine V6.3.1. Главная архитектурная цель RC14 — **сквозная связанность**: capability declaration → UI → application action → helper boundary → evidence → Status Center → support snapshot.

## RC14.7: runtime / SSH continuity

Фактический RC14.6 Windows-run подтвердил GUI и integrity plane, но выявил разрывы на границах process/runtime. RC14.7 закрывает их без переписывания V6.3.1:

- при старте V7 выполняется максимум **одна** восстановительная `Apply` сохранённой конфигурации, если есть `AUTO/VPS`, а SOCKS/watchdog отсутствуют;
- `plink` является источником истины для собственного exit code; PowerShell `NativeCommandError` больше не должен подменять/скрывать результат native process;
- environment readiness и execution helpers используют согласованный discovery portable PuTTY/plink;
- cumulative Keenetic inventory использует snapshot ключей перед merge;
- подтверждение SSH host key остаётся интерактивным и fail-closed; сохранённый DPAPI password не помещается в process command line интерактивного PuTTY;
- runtime V6.3 (`%LOCALAPPDATA%`) и portable data V7 (`VPS-Control-Data`) явно различены в UI.

Однократная startup-recovery не является новым Windows autostart и не создаёт Scheduled Task. Она работает только при фактическом запуске V7 и восстанавливает уже сохранённое состояние.

## Инварианты

- `VPS-Control-v6.3.1.ps1` остаётся внешней неизменяемой rollback-базой и не входит в RC ZIP.
- GUI V7 не является вторым routing-engine; routing mutation делегируется генерируемому V6.5.
- Unmatched Windows traffic остаётся DIRECT; full/default-route VPN не является функцией operational contour.
- Статус без evidence не превращается в положительное утверждение.
- Keenetic — отдельный health domain; его ошибка не должна скрыто переопределять Windows routing health.
- Entware install/remove остаётся fail-closed до реального device/storage/component/recovery evidence.
- Secrets не входят в обычный backup, snapshot или event log.

## Functional integrity plane

Новый `modules/V7-Consistency.ps1` и `VPS-Control-v7-CAPABILITY-TRUTH.md` образуют небольшой integrity plane.

Он проверяет не сеть, а связность самого продукта:

`Capability Truth -> files/modules -> launcher wiring -> UI action -> helper ValidateSet -> manifest`

Required mismatch является startup blocker. Проверка read-only и может быть повторена из вкладки «Диагностика».

## Текущие модули

- `modules/V7-Core.ps1` — file/JSON helpers, atomic writes, UI name normalization.
- `modules/V7-Observability.ps1` — telemetry, AUTO explanations, events composition, UI settings.
- `modules/V7-Runtime.ps1` — runtime/watchdog/Proxifier/autostart state.
- `modules/V7-UiCommon.ps1` — reusable WinForms controls.
- `modules/V7-Readiness.ps1` — read-only local environment inventory.
- `modules/V7-StatusCenter.ps1` — unified health tree и safe snapshot composition.
- `modules/V7-Consistency.ps1` — functional integrity/capability wiring verification.
- `modules/V7-Maintenance.ps1` — package SHA/integrity и temp cleanup.
- `modules/V7-Storage.ps1` — portable storage, safe backup, storage migration preference.
- `modules/V7-Events.ps1` — schema-v2 event envelope с обратным чтением старых JSONL.
- `modules/V7-KeeneticModel.ps1` — cumulative Keenetic/Entware evidence и lifecycle model.
- `modules/V7-Demo.ps1` — isolated synthetic evidence.

Mutation-heavy helpers остаются отдельными process boundaries:

- `VPS-Control-v7-engine-upgrade.ps1`
- `VPS-Control-v7-vps-manager.ps1`
- `VPS-Control-v7-keenetic.ps1`
- `VPS-Control-v7-vm-gateway.ps1`
- `VPS-Control-v7-browser-strict.ps1`

## Status Center

Status Center остаётся read-only aggregator. Начиная с RC14 operational ControlState включает:

`Local -> Routing -> VPS dependencies -> Runtime freshness -> V7 storage -> Functional consistency`

Keenetic выводится отдельным node и отображается рядом, но не входит в Windows ControlState.

Верхний индикатор GUI и tray теперь выводятся из той же combined модели, поэтому Status Center и крупная индикация не должны противоречить друг другу. Watchdog считается обязательной зависимостью только когда сохранённая конфигурация содержит `AUTO/VPS` (или VPS фактически используется); при полностью `DIRECT` конфигурации его отсутствие нейтрально.

## Keenetic / Entware

Cumulative inventory:

`VPS-Control-Data\nodes\keenetic\inventory.json`

Evidence-bearing actions:

- `Probe` — read-only router reachability;
- `EntwareStatus` — read-only SSH inventory;
- `EntwareRefresh` — confirmed `opkg update`;
- `EntwareUpgrade` — confirmed `opkg update + opkg upgrade`.

Для SSH password-mode helper использует только DPAPI secret. Поле пароля WinForms не передаётся дочернему процессу напрямую. Discovery PuTTY/plink унифицирован между readiness и VPS/Keenetic helpers: учитываются путь из внешнего V6.3.1, стандартный `Program Files\PuTTY` и PATH. Для первого подключения есть отдельный interactive boundary `OpenEntwareSsh`, чтобы пользователь мог сверить/принять SSH host key до `plink -batch`.

`ENTWARE=NOT_DETECTED` является валидным read-only evidence (`NOT_INSTALLED`) и не считается техническим failure. Ошибка выполнения helper и ошибка локальной записи cumulative inventory учитываются раздельно.

Mutation `EntwareRefresh`/`EntwareUpgrade` требует свежего (≤24h) inventory `EntwareState=INSTALLED`. Это UI/application guard; helper дополнительно проверяет наличие `opkg` на целевой системе.

Полные install/remove действия отсутствуют. Текущий путь:

`inventory -> precheck -> recovery backup -> exact transaction plan -> explicit confirmation -> [BLOCKED UNTIL RUNTIME EVIDENCE]`

## Rollback boundary

Кнопка «Открыть консоль V6.3.1» обязана вести в стабильный внешний rollback source. При наличии `VPS-Control-v6.3.1.cmd` запускается он; иначе запускается `$EngineSourcePath` (`VPS-Control-v6.3.1.ps1`). Generated V6.5 не используется как подмена подписанного пользователю fallback.

## Data / evidence boundaries

V7-owned data живут в `VPS-Control-Data\` или явно выбранном data root. Runtime V6.3.1 пока остаётся в `%LOCALAPPDATA%\VPS-Control-v6.3`.

Safe snapshot содержит readiness, package integrity, functional consistency, Status Center, sanitized active VPS metadata, sanitized Keenetic config/inventory, routing/runtime и recent events. Секреты не включаются.

## RC14.1 Windows parser/preflight hotfix

Первый реальный запуск RC14 на Windows PowerShell 5.1 выявил parser defect в `V7-Storage.ps1` (`$name:` внутри interpolated string). RC14.1 исправляет выражение на `${name}:` и меняет startup ordering: SHA verification → AST parse всех package `.ps1` → только затем dot-source Storage и инициализация data root.

## RC14.2 package-root / collection integrity hotfix

Второй реальный Windows-запуск RC14.1 выявил ложный fail-closed во вторичной package integrity проверке: `V7-Maintenance.ps1` использовал module-local `$PSScriptRoot`, поэтому искал manifest внутри `modules\`; одновременно tuple-like `@(@(...))` конструкции могли разворачиваться PowerShell и терять структуру записей. RC14.2 передаёт package root явно (`-BaseDir $PSScriptRoot`) и заменяет tuple arrays на именованные `PSCustomObject` records.

Этот же класс устранён в consistency file list, legacy VPS field mapping, таблицах observation/events, диагностических кнопках и Keenetic overview cards. `V7-Runtime.ps1` также получает package root явно для HKCU autostart command, чтобы путь указывал на корневой `VPS-Control-v7-launch.ps1`.

Startup contract теперь различает три корня: package root, modules root и portable data root; ни один module-local `$PSScriptRoot` не должен неявно подменять package root.

## RC14.3 Windows PowerShell 5.1 consistency parser hotfix

Третий реальный Windows-запуск RC14.2 подтвердил корректность раннего AST-preflight: launcher остановил пакет до dot-source/GUI и точно указал синтаксическую ошибку в `modules\V7-Consistency.ps1`. В `NO_NESTED_TUPLE_ARRAYS` внешняя скобка закрывалась до третьей части boolean-выражения; последующая `)` и `$true` становились неожиданными токенами, а сообщения о незакрытом блоке функции были каскадными.

RC14.3 заменяет сложное inline-выражение на отдельный `$hasNestedTupleArrays` и простой boolean argument `(-not $hasNestedTupleArrays)`. Operational/routing feature set не расширяется; цель hotfix — пройти следующий этап реального PowerShell 5.1 startup-chain.

## RC14.4 Functional Consistency regex/literal hotfix

Четвёртый реальный Windows PowerShell 5.1 запуск подтвердил, что SHA/AST/bootstrap дошли до `Test-V7FunctionalConsistency`, но self-check ошибочно использовал C-style `\$Variable` внутри double-quoted regex. В PowerShell обратный слэш не экранирует `$`, поэтому `$BaseDir` подставлялся как `X:\Example\...`, а regex parser видел недопустимую escape-последовательность `\M`.

RC14.4 переводит проверки literal source-wiring (`Package Root`, autostart launcher и Strict Browser wiring) с regex на `String.Contains()`. Это делает self-check независимым от буквы диска, обратных слэшей, YandexDisk-пути и regex escaping. Operational/routing feature set не расширяется.

## Следующий безопасный шаг после RC14.4


До доступа к Windows следующий release не должен расширять operational feature set без необходимости. Наиболее ценное следующее evidence — native Windows 10 / PowerShell 5.1 / WinForms smoke и последовательный E2E-проход ключевых пользовательских цепочек.

## RC14.5 WinForms type/namespace hotfix

Пятый фактический Windows 10 / Windows PowerShell 5.1 запуск прошёл package SHA, AST и Functional Consistency и остановился уже при построении WinForms UI: `Drawing.Padding` не существует. `Padding` является `System.Windows.Forms.Padding`.

RC14.5 исправляет оба использования `Drawing.Padding` в Keenetic UI, добавляет source-level invariant `UI_PADDING_NAMESPACE` и ранний runtime smoke основных WinForms/System.Drawing primitive types в launcher. Функциональный объём не расширяется; routing/network helpers не перепроектируются.

RC14.5 оставался Release Candidate до подтверждённого полного запуска GUI и дальнейшего Windows runtime evidence.


## RC14.7 Windows runtime truth boundary

RC14.5 впервые дошёл до полноценного WinForms GUI на реальном Windows 10 / Windows PowerShell 5.1. RC14.7 фиксирует два runtime-класса ошибок: конфликт с read-only automatic variable `$Host` и смешение устаревшего runtime evidence с текущим состоянием.

Инвариант RC14.7: `runtime-state.json` старше 300 секунд может использоваться только как **последнее evidence**, но не как утверждение «сейчас». Текущие локальные проверки (watchdog process, SOCKS listener, Proxifier process, storage/consistency) остаются независимыми и могут сообщать фактическую ошибку даже при устаревшем routing runtime.