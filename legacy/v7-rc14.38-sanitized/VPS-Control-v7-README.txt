VPS CONTROL CENTER v7.0.0-rc14.38 — WINDOWS POWERSHELL 5.1 ENCODING CORRECTION

Fresh Windows Validation Lab v1.0.4 evidence for exact RC14.37:
- classification: PRODUCT_DEFECT;
- RC14.37-modified `VPS-Control-v7-launch.ps1`, `VPS-Control-v7.ps1`, and `modules\V7-Consistency.ps1` were UTF-8 without BOM;
- Windows PowerShell 5.1 parsed those files through the legacy ANSI decoding path and reported AST failures;
- manifest, dual-tunnel contract, generated-engine isolation, secure-pwfile primitive and immutable V6.3.1 checks remained intact.

RC14.38 restores UTF-8 BOM on all PowerShell package files. No runtime policy or credential semantics are changed.

1081 = PRIMARY_AUTO.
1080 = RESERVE_MANUAL / MANUAL_ONLY.
V6.3.1 remains immutable.
Stable/DONE requires fresh Windows validation and controlled runtime proof.

VPS CONTROL CENTER v7.0.0-rc14.38 — RUNTIME SELF-GATE INTERPOLATION CORRECTION

Fresh Windows runtime-gate evidence for exact RC14.36:
- candidate SHA matched the validated artifact;
- V6.3.1 immutable SHA matched;
- startup stopped fail-closed before generated V6.5 creation;
- mandatory capability `PUTTY_PWFILE_ACL_AT_CREATION` falsely failed.

Root cause:
- `modules\V7-Consistency.ps1` used an unescaped `$env:LOCALAPPDATA` inside a double-quoted `.Contains()` source marker;
- PowerShell expanded the environment variable before comparison;
- the intended consistency-marker safety scan inspected `VPS-Control-v7-browser-strict.ps1` instead of `V7-Consistency.ps1`, so it could not catch its own marker interpolation bug.

RC14.38 corrects only that self-gate logic. Secure credential creation, DPAPI, PuTTY `-pwfile`, host-key verification, routing and tunnel lifecycle are unchanged.

1081 = PRIMARY_AUTO.
1080 = RESERVE_MANUAL / MANUAL_ONLY.
V6.3.1 remains immutable.
Stable/DONE requires fresh Windows validation and controlled runtime proof.

VPS CONTROL CENTER v7.0.0-rc14.36 — PSSCRIPTANALYZER WARNING BUDGET REMEDIATION RC

Fresh Windows Validation Lab v1.0.3 evidence for exact RC14.35:
- validator self-preflight: 13/13 PASS;
- all blocking product checks PASS except PSSCRIPTANALYZER_WARNING_BUDGET;
- PSScriptAnalyzer: 0 Errors, 510 Warnings;
- allowed RC14.34 warning budget: 508;
- classification: PRODUCT_DEFECT;
- product mutation during validation: false.

RC14.36 is a narrow remediation of warning debt introduced by the RC14.35 SecureString staging helper:
- helper verb New-V7SecureStringFromText -> ConvertTo-V7SecureStringFromText, removing the unnecessary ShouldProcess warning;
- two SecureString disposal catch blocks now contain generic Write-Debug diagnostics instead of empty catch blocks;
- no tunnel policy, credential transport, DPAPI format, host-key policy, routing, lifecycle, or V6.3.1 behavior is changed.

Expected static effect: three RC14.35-introduced warnings removed. Because the RC14.35 $Error -> $ErrorText correction had already removed one prior warning, expected total is 507 warnings (ratchet below the 508 baseline). This expectation is NOT release evidence until rerun on Windows PowerShell 5.1.

1081 = PRIMARY_AUTO.
1080 = RESERVE_MANUAL / MANUAL_ONLY.
V6.3.1 remains immutable.

--------------------------------------------------------------------------------
HISTORICAL RC14.35 NOTES
--------------------------------------------------------------------------------

VPS CONTROL CENTER v7.0.0-rc14.35 — PSSCRIPTANALYZER ERROR REMEDIATION RC

RC14.34 Validation Lab:
- AST PASS
- manifest PASS
- dual tunnel PASS
- generated V6.5 PASS
- FileSecurity primitive PASS
- PSScriptAnalyzer: 4 Error diagnostics

RC14.35 removes all four evidence-proven error patterns without changing tunnel policy or stored-password compatibility.

1081 = PRIMARY_AUTO.
1080 = RESERVE_MANUAL.

RC14.13 baseline основан на фактическом Windows evidence RC14.12. Исправлены два runtime-дефекта: тяжёлый forensic telemetry больше не выполняется на WinForms timer; GUI putty/putty_portable больше никогда не получает Plink-only `-batch`. Периодическая telemetry теперь LIGHT раз в 30 секунд, а process/socket/CIM/hash/EventLog forensic сбор выполняет отдельный скрытый `VPS-Control-v7-evidence-worker.ps1`. Portable SavedSession остаётся совместимым с proven V6.3.1 `-load` contract, но автоматический запуск fail-closed требует известный password/.ppk/Pageant credential; пароль может быть взят из V7 DPAPI или legacy V6.3.1/V6.x/V5 без вывода значения в лог.

V7.0.0-RC14.12 — CONSISTENCY SELF-CHECK CONTRACT HOTFIX

Назначение RC14.12

RC14.12 — узкий стабилизационный hotfix по фактическому Windows evidence RC14.11. Сетевой runtime, deep telemetry и local-first PuTTY не перепроектируются. Исправлены два drift-дефекта самой fail-closed проверки связанности: (1) PORTABLE_PUTTY_SAVED_SESSION_COMPAT теперь проверяет актуальные RC14.11/14.12 markers explicit credential + opaque -batch paths, а не удалённый marker старой реализации; (2) Capability Truth parser учитывает explicit current-RC delta declarations, поэтому DEEP_TELEMETRY не теряется только потому, что его declaration находится выше сохранённой исторической таблицы.

Сохранено из RC14.11:

RC14.12 не меняет маршрутизацию, SSH/PuTTY execution, recovery backoff или telemetry collection; это integrity-plane-only hotfix.
- local-first PuTTY discovery: `<V7 root>\PuTTY PORTABLE\putty_portable.exe` имеет приоритет над историческим абсолютным `$PuttyPath`;
- read-only portable session parser: host/port/protocol/forwardings/key evidence без чтения секретов;
- RC14.11 historical: non-interactive portable `-batch` probe; RC14.13: removed for GUI PuTTY, explicit credential required;
- `runtime-metrics.jsonl` каждые ~15 секунд: UI process, SOCKS/listener owner, watchdog heartbeat, Proxifier, recovery, active VPS, per-module route/health/latency, relevant processes и sockets;
- `diagnostic-trace.jsonl`: state transitions, telemetry lifecycle и auto incidents;
- `operation-evidence.jsonl`: завершения Engine/VPS/Keenetic операций, exit code, duration и bounded sanitized stdout/stderr tail до удаления temp-файлов;
- `environment-latest.json`: OS/PowerShell, network adapters/IP/DNS/default routes, package/engine/PuTTY hashes, process/socket inventory и metadata/hashes файлов локального `PuTTY PORTABLE` без чтения их содержимого;
- runtime metrics дополнены host CPU/RAM/uptime и счётчиками RX/TX/errors/discards сетевых адаптеров;
- rate-limited `AUTO-incident-*.txt` при деградации важных runtime states или logical `[FAIL]`; автоматические bundles имеют bounded retention (30 последних), чтобы диагностика не съедала диск;
- кнопка `Полный лог / метрики` создаёт `FULL-debug-*.txt` с максимальным sanitized evidence;
- debug export теперь читает UTF-8 через smart decoder, чтобы Windows PowerShell 5.1 не превращал кириллицу events.jsonl в mojibake.

Security boundary: password/DPAPI blobs/private-key contents/tokens/LKG contents и credential command lines не включаются в telemetry/support reports.

Runtime acceptance: после запуска ожидается `PUTTY_DISCOVERY ... source=colocated`, затем `PORTABLE_SESSION_PARSE`, `PORTABLE_SESSION_RUNTIME`, `PUTTY_PROCESS`, `ENSURE_WAIT` и, при успешной аутентификации session, `IDENTITY ... ok=True`. Если auth требует неизвестный пароль, RC14.13 не запускает GUI PuTTY и возвращает CREDENTIAL_REQUIRED; после сохранения DPAPI-пароля recovery повторяется автоматически.

Статус: Release Candidate; offline/static checks не заменяют реальный Windows runtime.

---

V7.0.0-RC14.10 — PORTABLE PUTTY / RECOVERY SERIALIZATION HOTFIX
=================================================================================

Назначение RC14.10
-----------------
RC14.10 — узкий runtime hotfix по фактическому SOCKS-debug RC14.9. Новые transport/VPN технологии не добавляются, стабильный внешний V6.3.1 не изменяется.

Подтверждённая первопричина RC14.9:
- активный профиль использует `AuthMode=SavedSession`, `SavedSession=ExampleVPS` и `putty_portable.exe`;
- стандартного `HKCU\Software\SimonTatham\PuTTY\Sessions\ExampleVPS` нет;
- RC14.9 ошибочно приравнивал отсутствие этой registry-записи к отсутствию самой portable session и останавливал запуск ДО PuTTY;
- стабильный V6.3.1 ранее работал иначе: запускал portable PuTTY через `-load ExampleVPS -l root -pw <password>` и принимал фактический SOCKS/VPS identity как runtime truth.

Исправления RC14.10:
- для `SavedSession + portable PuTTY` отсутствие стандартной HKCU session больше не является fatal precheck;
- opaque portable SavedSession запускается по доказанному legacy contract V6.3.1: `-load <session> -l <user> -pw <effective password>` без навязывания второго `-D` или `-N`;
- пароль берётся из V7 DPAPI, текущего legacy source или sibling V6 source; значение никогда не попадает в SOCKS debug trace;
- если password source действительно отсутствует, отказ теперь точный: V7 просит один раз сохранить пароль в DPAPI вместо ложного сообщения про отсутствующую session;
- standard HKCU SavedSession остаётся строго проверяемой: host/port/forwarding/key/Pageant читаются как раньше, а при отсутствии D1080 может использоваться command-line `-D`;
- recovery сериализован до полного consumption результата child process: exited-but-not-yet-consumed Apply больше не освобождает operation lease и не запускает несколько Apply параллельно;
- `$script:RuntimeRecoveryAction` является отдельным in-flight guard;
- `[FAIL]` в выводе Apply/RestartTunnel считается logical failure даже при ошибочном native `rc=0`, поэтому GUI/rollback/retry не получают ложный PASS;
- snapshot различает `session.source=HKCU` и `session.source=PORTABLE_OPAQUE` вместо ложного `session.exists=False` только из-за отсутствия registry-записи.

Диагностика RC14.9 сохранена и используется дальше:
- `VPS-Control-Data\logs\socks-runtime.log`;
- `VPS-Control-Data\logs\socks-engine.log`;
- Диагностика → «Собрать лог SOCKS» → `exports\SOCKS-debug-*.txt`;
- password/DPAPI/private-key contents и значение `-pw` в отчёт не включаются.

Ожидаемый runtime acceptance RC14.10:
1. после запуска V7 при сохранённом `OpenAI=VPS` recovery делает только один Apply одновременно;
2. в `socks-engine.log` появляется `PORTABLE_SESSION ... registry=ABSENT_EXPECTED` и затем реальный `PUTTY_START`;
3. `127.0.0.1:1080` начинает слушать;
4. identity probe подтверждает VPS exit;
5. Status Center показывает SOCKS и VPS route как фактический HEALTHY;
6. если пароль не найден, вместо циклических попыток выдаётся конкретный `portable-session-no-password`.

Статус: Release Candidate. Offline package/static checks не заменяют реальный Windows runtime; RC14.10 считается квалифицированным только после указанного прогона.

История RC14.9
--------------
RC14.9 добавил deep SOCKS trace и единый sanitized `SOCKS-debug-*.txt`. Именно этот evidence позволил локализовать RC14.10 root cause до ложного требования standard HKCU session и увидеть overlapping recovery race.

История RC14.8
--------------
VPS CONTROL CENTER V7.0.0-RC14.8 — RUNTIME RECOVERY / SSH TRUST STABILIZATION
=================================================================================

Назначение RC14.8
-----------------
RC14.8 продолжает runtime-qualification после фактического Windows-прогона RC14.7. Новых transport/VPN технологий нет; V6.3.1 не изменяется.

Исправления по подтверждённым замечаниям RC14.7:
- startup-recovery больше не одноразовый: при сохранённых AUTO/VPS отсутствующий SOCKS/watchdog повторно восстанавливается через Apply с backoff 30/60/120/300 секунд, без tight loop и без нового Scheduled Task;
- SavedSession больше не может молча открыть скрытый PuTTY без пригодной аутентификации: используется DPAPI/legacy password либо подтверждённый .ppk/Pageant, иначе GUI/engine выдаёт понятную причину;
- для SavedSession гарантируется dynamic SOCKS: если в ExampleVPS уже есть D1080, используется saved-session forwarding; иначе V6.5 добавляет command-line -D 127.0.0.1:1080 -N;
- вкладка VPS-серверы показывает фактический статус DPAPI для SavedSession вместо общего текста «необязательно»;
- Keenetic host key больше не требует интерактивной PuTTY-консоли и повторного password prompt: plink read-only probe получает SHA256 fingerprint, пользователь явно подтверждает его, после чего fingerprint сохраняется локально и последующие действия используют -hostkey + DPAPI password;
- изменение адреса/SSH-порта Keenetic автоматически сбрасывает ранее закреплённый fingerprint;
- HostKeyProbe/OpenEntwareSsh не загрязняют cumulative inventory как device evidence.

Статус: Release Candidate. GUI и основные read-only контуры подтверждены Windows runtime, но RC14.8 требует повторной проверки SOCKS/watchdog recovery и нового pinned-host-key flow Keenetic.

История RC14.7
--------------
Назначение RC14.7
-----------------
RC14.7 — узкий стабилизационный инкремент по фактическому Windows runtime RC14.6. Новых transport/VPN технологий нет; V6.3.1 не изменяется.

Подтверждённые RC14.6 разрывы и исправления RC14.7:
- V7 GUI уже стабильно запускается на Windows 10 / Windows PowerShell 5.1, но сохранённая AUTO/VPS-конфигурация не восстанавливала отсутствующий SOCKS/watchdog сама. RC14.7 выполняет одну ограниченную попытку Apply после старта UI, только если сохранённая конфигурация реально требует AUTO/VPS и runtime отсутствует. Бесконечного цикла нет.
- PuTTY/plink ошибки в VPS/Keenetic helper больше не могут превращаться в ложный rc=0 из-за PowerShell 5.1 NativeCommandError. На время native pipeline ErrorActionPreference переводится в Continue, затем используется реальный LASTEXITCODE; non-zero остаётся failure.
- Environment Readiness теперь ищет portable PuTTY из неизменяемого V6.3.1 и plink/Pageant рядом с ним, тем же способом, что runtime helpers.
- Keenetic cumulative inventory больше не изменяет OrderedDictionary во время live-enumeration Keys: ключи сначала snapshot-ятся. Это устраняет runtime «Коллекция была изменена; невозможно выполнить операцию перечисления» после успешного Probe/SSH action.
- Host-key workflow Keenetic уточнён: пользователь сверяет и принимает fingerprint в PuTTY, а на последующем запросе пароля может закрыть PuTTY; batch Entware action использует уже сохранённый DPAPI-пароль. Пароль намеренно не передаётся интерактивному PuTTY через process command line.
- Диагностическая строка «Журнал V7 / Копировать вывод» переведена на TableLayoutPanel, чтобы кнопки не перекрывались при масштабировании/DPI.
- Кнопка открытия legacy state переименована в «Открыть runtime V6.3», чтобы не путать `%LOCALAPPDATA%\VPS-Control-v6.3` с portable `VPS-Control-Data` V7.
- Генерируемый V6.5 пишет, какой PuTTY auth/session/host используется при попытке поднять SSH/SOCKS; секреты в этот trace не входят.

Важная граница диагностики
--------------------------
Если PuTTY сообщает `Remote side unexpectedly closed network connection` или plink возвращает ошибку соединения, это фактическая ошибка SSH-транспорта. RC14.7 корректно показывает её и автоматически повторяет Apply только один раз при старте, но не может создать SOCKS-туннель, пока SSH-соединение с VPS не принимается сервером.

Статус: Release Candidate. Основной GUI подтверждён runtime; RC14.7 требует повторного Windows-прогона SOCKS/watchdog, VPS helper и Keenetic inventory после этих исправлений.

История предыдущего RC14.4
--------------------------
Назначение RC14.4
---------------
RC14.4 — точечный self-check hotfix поверх RC14.3 по результатам четвёртого реального Windows-запуска.
Новый ранний AST-preflight в RC14.2 сработал корректно и остановил запуск на синтаксической ошибке в modules\V7-Consistency.ps1. В проверке NO_NESTED_TUPLE_ARRAYS была лишняя закрывающая скобка; сообщения по строкам 30 и 144 были каскадными последствиями этой ошибки.
RC14.4 устраняет C-style escaping внутри Functional Consistency: literal source-wiring checks больше не строят regex из строк с $BaseDir/$desired. Для них используется literal Contains(), поэтому путь вида X:\Example\... не может превратиться в regex escape \M. Функциональный объём не расширяется.

История RC14.2: RC14.2 — startup/package-root/collection integrity hotfix поверх RC14.1 по результатам второго реального Windows-запуска. Он исправил поиск manifest относительно modules, nested-array anti-pattern и package-root для автозапуска.

История RC14.1: RC14.1 — точечный Windows PowerShell 5.1 parser/preflight hotfix поверх RC14.
Первый реальный Windows-запуск RC14 обнаружил ParserError в modules\V7-Storage.ps1: интерполяция
`$name:` недопустима для Windows PowerShell 5.1; исправлено на `${name}:`.
AST-проверка launcher перенесена ДО dot-source V7-Storage, чтобы такой дефект helper останавливался
контролируемым preflight-сообщением, а не необработанным ParserError.
RC14.1 сохраняет функциональный состав RC14 без перепроектирования и без добавления новых transport/VPN технологий.
Главная цель — чтобы пользовательский интерфейс, helper-процессы, status model, документация и package manifest
говорили об одном и том же фактическом состоянии продукта.

V6.3.1 НЕ изменяется и НЕ включается в RC14.7 ZIP. Рабочий V7 по-прежнему требует внешний
VPS-Control-v6.3.1.ps1 рядом с программой как проверенную rollback-базу.

Функциональный состав RC14, сохранённый в RC14.7
----------------------
1. Capability Truth.
   Добавлен VPS-Control-v7-CAPABILITY-TRUTH.md — каноническая таблица того, что реально IMPLEMENTED,
   READ_ONLY, GUARDED/CONFIRMED MUTATION или BLOCKED. Будущие идеи не выдаются за реализованные функции.

2. Автоматическая проверка «заявлено ↔ реализовано».
   Новый modules\V7-Consistency.ps1 проверяет:
   - согласованность версии main / launcher / README / architecture;
   - наличие обязательных файлов;
   - подключение всех modules\*.ps1 в main и launcher AST-list;
   - соответствие GUI-вызовов Keenetic/VPS actions ValidateSet соответствующих helper;
   - отсутствие Keenetic Install/Remove mutation action;
   - наличие fail-closed marker для Entware install/remove;
   - покрытие distributable-файлов SHA manifest;
   - наличие всех routing modules.

   Проверка выполняется при старте. Required mismatch останавливает V7 fail-closed.
   В «Диагностика» добавлена кнопка «Проверить связанность» для повторного read-only запуска.

3. Status Center теперь действительно связан с общей индикацией.
   Узел «Связанность функций» входит в health tree. Верхний общий индикатор и tray используют тот же
   combined ControlState, а не более узкую runtime-оценку, которая могла расходиться со Status Center.
   Keenetic по-прежнему отдельный домен и не делает Windows routing ошибочным сам по себе.

4. Устранена ложная индикация маршрута.
   Если runtime не содержит корректного Effective=DIRECT/VPS, колонка «Сейчас» показывает «—»,
   а не ошибочно «Напрямую».

5. SOCKS / Proxifier показываются контекстно.
   Если текущая и сохранённая конфигурация полностью DIRECT, отсутствие SOCKS/Proxifier не отображается
   как безусловная авария. Если есть AUTO/VPS readiness — показывается предупреждение; если VPS реально
   используется — отсутствие зависимости остаётся ошибкой.

6. Keenetic: устранён разрыв «Save → Action».
   RC13 мог продолжить действие после нажатия внутреннего PerformClick на «Сохранить» даже при ошибке
   сохранения и тем самым использовать старую конфигурацию. RC14.1 запускает Probe/SSH/helper только если
   фактическое сохранение настроек завершилось успешно.

7. Keenetic: пароль и SSH-операции приведены к реальной модели.
   Отдельный SSH helper получает password-mode credential только из DPAPI-файла. Интерфейс теперь говорит
   это прямо. Если DPAPI secret отсутствует, EntwareStatus/Refresh/Upgrade блокируются fail-closed;
   router Probe и локальный transaction plan остаются доступны.

8. Keenetic mutation имеет evidence-precondition.
   opkg update / opkg upgrade разрешаются из GUI только после:
   - успешного сохранения текущей конфигурации;
   - наличия DPAPI secret;
   - read-back inventory с EntwareState=INSTALLED;
   - свежего LastEntwareAt не старше 24 часов;
   - отдельного явного подтверждения.
   Подтверждение показывает последние известные counts пакетов/обновлений.

9. Интерфейс Keenetic стал однозначнее.
   Кнопки изменения помечены «Изменить: ...», а бывшая «Установка / удаление» переименована в
   «План установки / удаления», потому что install/remove mutation в RC14.1 отсутствует.

10. «Применить сохранённое» больше не маскирует dirty-state.
    Если таблица содержит несохранённые изменения, GUI/tray явно предупреждает, что будет применён
    прежний routing-config.json, а не текущие значения таблицы.

11. System Snapshot дополнен consistency result.
    Snapshot включает PackageIntegrity + Consistency + StatusCenter + sanitized Keenetic inventory.
    Пароли, DPAPI blobs, private key contents, tokens и LKG contents не включаются.

12. Readiness и SSH helpers используют одну модель discovery PuTTY/plink.
    Standard Program Files\PuTTY, путь PuTTY из внешнего V6.3.1 и PATH больше не расходятся между
    диагностикой и фактическим VPS/Keenetic исполнителем. Ситуация «readiness PASS, helper не находит plink» устранена.

13. Entware NOT_INSTALLED больше не считается технической ошибкой.
    Read-only EntwareStatus с ENTWARE=NOT_DETECTED завершает inventory успешно и фиксирует lifecycle
    NOT_INSTALLED. Ненулевой rc остаётся для реального SSH/opkg failure.

14. Успех helper и успех сохранения evidence разделены.
    Если Keenetic-команда выполнилась, но локальный inventory записать не удалось, UI выдаёт отдельный WARN,
    а event содержит inventory=FAILED вместо ложного полного SUCCESS.

15. Watchdog учитывает реальную необходимость.
    При полностью DIRECT сохранённой конфигурации остановленный watchdog не объявляется аварией.
    При наличии AUTO/VPS он остаётся необходимой зависимостью и влияет на общий статус.

16. Главный пользовательский поток сделан однозначнее.
    Основное действие — «Сохранить и применить». Отдельная кнопка теперь называется «Сохранить без применения»;
    Status Center выводится двумя короткими строками, чтобы Windows-контур и отдельный Keenetic domain читались без горизонтальной простыни.

17. Замкнут первый SSH-connect Keenetic.
    Batch plink не может безопасно принять неизвестный host key. Поэтому в Keenetic добавлен явный путь
    «Открыть SSH / принять ключ»: он запускает интерактивный PuTTY без передачи DPAPI-пароля в командную строку.
    После проверки fingerprint пользователь возвращается к read-only EntwareStatus.

18. Fallback V6.3.1 теперь соответствует своей подписи.
    Если внешний VPS-Control-v6.3.1.cmd отсутствует, кнопка «Открыть консоль V6.3.1» запускает именно
    внешний VPS-Control-v6.3.1.ps1 (EngineSourcePath), а не generated V6.5. Если rollback source отсутствует,
    UI показывает ошибку вместо скрытой подмены fallback.


19. VM Gateway mutation UX.
    Кнопки включения/отключения явно помечены как изменение. Перед UAC интерфейс показывает конкретный
    vEthernet IP/порт и точную границу transaction: portproxy + собственное firewall-правило; default route
    и сторонние firewall rules не изменяются.

Запуск
------
Обычный режим:
  VPS-Control-v7.cmd

Демо-режим без реальных сетевых/system mutations:
  VPS-Control-v7-demo.cmd

Что остаётся заблокировано
--------------------------
- полная установка/удаление Entware;
- новые transports/VPN/research mechanisms;
- full VPN/default-route всей Windows;
- автоматическое превращение Keenetic readiness-plan в mutation;
- заявление Stable/DONE без native Windows runtime evidence.

Где смотреть правду о возможностях
----------------------------------
1. VPS-Control-v7-CAPABILITY-TRUTH.md — текущая capability truth.
2. «Диагностика → Проверить связанность» — машинная сверка package wiring.
3. «Статус → Связанность функций» — текущий результат consistency в общей health-модели.
4. VPS-Control-v7-ARCHITECTURE.md — границы модулей и safety invariants.

Статус релиза
-------------
RC14.7 остаётся Release Candidate: основной WinForms GUI уже подтверждён на Windows 10 / Windows PowerShell 5.1, но E2E-проверка отдельных функций продолжается; недоступный VPS во время плановых работ не используется как доказательство дефекта V7.
