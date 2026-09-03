# PNCC State Snapshot CLI

Этот каталог содержит read-only инструменты для формирования, проверки и просмотра `PNCC_STATE_SNAPSHOT` на Windows PowerShell 5.1.

## Быстрый запуск

В репозитории есть безопасный синтетический пример `tools/cli/examples/state-input.example.json`. Он предназначен только для проверки CLI и **не является Runtime Truth**.

Сначала можно выполнить read-only preflight входного JSON:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Test-PnccStateSnapshotInput.ps1 -InputPath .\tools\cli\examples\state-input.example.json
```

Machine-readable результат preflight:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Test-PnccStateSnapshotInput.ps1 -InputPath .\tools\cli\examples\state-input.example.json -Json
```

Для автоматизации, где нужен надёжный process exit code, используйте отдельный wrapper:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Invoke-PnccStateSnapshotInputCheck.ps1 -InputPath .\tools\cli\examples\state-input.example.json -Json; $LASTEXITCODE
```

Exit-code contract wrapper:

- `0` — input валиден (`Code=VALID`);
- `2` — caller input невалиден; stdout содержит нормализованный `PNCC_STATE_SNAPSHOT_INPUT_VALIDATION` с исходным validation `Code`;
- `3` — validator dependency/internal contract failure; stdout остаётся нормализованным, без raw exception/path.

`Invoke-PnccStateSnapshotInputCheck.ps1` предназначен для отдельного `powershell.exe -File` процесса и использует `exit`. Для вызова из существующей PowerShell-сессии/другого скрипта без завершения процесса используйте composable `Test-PnccStateSnapshotInput.ps1`.

Русский человекочитаемый статус одной командой:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Show-PnccStateSnapshot.ps1 -InputPath .\tools\cli\examples\state-input.example.json
```

Machine-readable snapshot JSON:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Show-PnccStateSnapshot.ps1 -InputPath .\tools\cli\examples\state-input.example.json -Json
```

`Show-PnccStateSnapshot.ps1` сам выполняет fail-closed preflight через canonical `Test-PnccStateSnapshotInput.ps1`. Для невалидного caller input наружу выходит только нормализованная ошибка вида `PNCC_STATE_SNAPSHOT_INPUT_INVALID:<CODE>` — без input path и raw PowerShell/JSON exception details. Валидный text/JSON output остаётся обычным `PNCC_STATE_SNAPSHOT`.

Справка PowerShell:

```powershell
Get-Help .\tools\cli\Test-PnccStateSnapshotInput.ps1 -Full
```

## Что находится в каталоге

- `Invoke-PnccStateSnapshotInputCheck.ps1` — process-oriented automation wrapper с exit codes `0/2/3`.
- `Test-PnccStateSnapshotInput.ps1` — composable read-only preflight: русский `КОРРЕКТЕН/НЕКОРРЕКТЕН` по умолчанию, нормализованный machine result с `-Json`.
- `Show-PnccStateSnapshot.ps1` — основной пользовательский entrypoint: fail-closed preflight, русский текст по умолчанию, `-Json` для machine snapshot contract.
- `Get-PnccStateSnapshot.ps1` — преобразует caller-supplied deterministic state JSON в `PNCC_STATE_SNAPSHOT`.
- `Format-PnccStateSnapshot.ps1` — форматирует уже готовый snapshot из файла или из строки `-SnapshotJson`.
- `examples/state-input.example.json` — публичный синтетический copy-run пример без приватной Runtime Truth.

## Preflight validation contract

`Test-PnccStateSnapshotInput.ps1 -Json` и automation wrapper возвращают нормализованный результат:

- `SchemaVersion = 1`;
- `Contract = PNCC_STATE_SNAPSHOT_INPUT_VALIDATION`;
- `ReadOnly = true`;
- `Valid = true/false`;
- `Code` — нормализованный код.

Machine result намеренно не содержит input path, raw exception text, secrets или private Runtime Truth. Семантическая проверка использует тот же `Get-PnccStateSnapshot.ps1`, что и `Show-PnccStateSnapshot.ps1`, поэтому отдельная копия правил построения snapshot не создаётся.

## Входные данные

`state-input.json` — не live probe и не приватный runtime dump, автоматически полученный GitHub CI. Это детерминированные данные, которые предоставляет вызывающая сторона. Поддерживаемые поля включают `Config`, `Runtime`, `Watchdog`, `ProxifierStatus`, `ModuleNames`, `OverallState`, `PrimarySocksListening`, `ReserveSocksListening`, `RoutingTunnelId`, `LastKnownGoodPresent`, `RuntimeAgeSeconds` и `CapturedAt`.

Минимальный пример:

```json
{
  "ModuleNames": ["OpenAI"],
  "OverallState": "HEALTHY",
  "PrimarySocksListening": true,
  "ReserveSocksListening": false,
  "RoutingTunnelId": "PRIMARY_AUTO",
  "RuntimeAgeSeconds": 42
}
```

Отсутствующие необязательные значения нормализуются существующим State Snapshot foundation; команды не делают сетевых запросов, не запускают сетевые/служебные процессы и не изменяют routing/runtime.

## Фиксированный tunnel contract

- `127.0.0.1:1081` = `PRIMARY_AUTO`, lifecycle `AUTO`.
- `127.0.0.1:1080` = `RESERVE_MANUAL`, lifecycle `MANUAL_ONLY`.
- PNCC automation не имеет права автоматически start/stop/restart/recover или иным образом управлять lifecycle 1080.

## Границы достоверности

`CI VERIFIED != RUNTIME VERIFIED`.

Checked-in example является только synthetic demonstration input. Эти CLI подтверждают структуру и отображение caller-supplied данных. Они не выполняют physical probes и сами по себе не доказывают реальное состояние Windows, VPS, Keenetic, Proxifier или SOCKS-туннелей. Physical Runtime Truth требует отдельного доверенного runtime evidence path.

## Fail-closed formatter

`Format-PnccStateSnapshot.ps1` принимает только snapshot, для которого одновременно выполняется:

- `SchemaVersion = 1`;
- `Contract = PNCC_STATE_SNAPSHOT`;
- `ReadOnly = true`;
- `SecretsIncluded = false`.

Несоответствие этим признакам приводит к ошибке вместо попытки отобразить сомнительные данные.
