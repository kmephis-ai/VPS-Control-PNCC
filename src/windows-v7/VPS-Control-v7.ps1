#requires -Version 5.1
<#
VPS Control Center v7.0.2
Russian-only Tray GUI / Control Center UI with an extensible V6.5 engine generated conservatively from the proven V6.3.1 source.

The routing engine is intentionally NOT reimplemented here.
V6.5 is generated locally from the user's V6.3.1 and preserves its SOCKS, Proxifier, AUTO hysteresis, failover,
failback, LKG rollback, probes, watchdog and routing safety. V6.3.1 is never overwritten and remains rollback.

Safety invariants:
  - unmatched Windows traffic remains DIRECT;
  - V7 uses the same V6.3 mutation mutex for configuration writes;
  - config writes are atomic and keep routing-config.json.bak;
  - routing mutations are delegated to the generated V6.5 engine actions;
  - GitHub WRITE diagnostics are intentionally not exposed in the GUI;
  - closing V7 never stops routing/watchdog/SOCKS/Proxifier;
  - V6.3.1 remains the immediate rollback path.
#>

[CmdletBinding()]
param(
    [switch]$StartHidden,
    [switch]$Demo
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$script:ChartsAvailable = $true
try {
    Add-Type -AssemblyName System.Windows.Forms.DataVisualization
}
catch {
    $script:ChartsAvailable = $false
}

[System.Windows.Forms.Application]::EnableVisualStyles()
[System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false)

$UiVersion = '7.0.2'
$EngineVersion = '6.5'
$VccSocksHost = '127.0.0.1'
$VccSocksPort = 1081
$ReserveSocksHost = '127.0.0.1'
$ReserveSocksPort = 1080
$ModuleNames = @('OpenAI','GitHub','DevPackages','Firefox','Claude','Gemini','Docker','Telegram','YandexBrowser','Edge','CustomExe','CustomSite')
$ModuleDefaultModes = @{ OpenAI='VPS'; GitHub='AUTO'; DevPackages='AUTO'; Firefox='DIRECT'; Claude='AUTO'; Gemini='AUTO'; Docker='AUTO'; Telegram='AUTO'; YandexBrowser='DIRECT'; Edge='DIRECT'; CustomExe='DIRECT'; CustomSite='DIRECT' }
$ValidModes = @('DIRECT', 'AUTO', 'VPS')

$ModuleUiNames = @{
    OpenAI = 'OpenAI'
    GitHub = 'GitHub'
    DevPackages = 'Пакеты разработки'
    Firefox = 'Firefox'
    Claude = 'Claude'
    Gemini = 'Gemini'
    Docker = 'Docker'
    Telegram = 'Telegram'
    YandexBrowser = 'Яндекс Браузер'
    Edge = 'Microsoft Edge'
    CustomExe = 'Свой EXE'
    CustomSite = 'Свой сайт'
}

$ModeCodeToUi = @{
    DIRECT = 'Напрямую'
    AUTO = 'Авто'
    VPS = 'Через VPS'
}
$ModeUiToCode = @{
    'Напрямую' = 'DIRECT'
    'Авто' = 'AUTO'
    'Через VPS' = 'VPS'
}

$ActionUiNames = @{
    Apply = 'применение сохранённой маршрутизации'
    Direct = 'временный режим «всё напрямую»'
    RestartTunnel = 'перезапуск VCC SOCKS 1081'
    SelfTest = 'самопроверка только для чтения'
    Diagnose = 'полная диагностика'
    Summary = 'сводка наблюдения за 24 часа'
    GitHubReadTest = 'проверка чтения GitHub'
    SupportBundle = 'создание безопасного пакета поддержки'
}

$StorageHelperPath = Join-Path $PSScriptRoot 'modules\V7-Storage.ps1'
$EventsHelperPath = Join-Path $PSScriptRoot 'modules\V7-Events.ps1'
$DemoHelperPath = Join-Path $PSScriptRoot 'modules\V7-Demo.ps1'
$KeeneticModelHelperPath = Join-Path $PSScriptRoot 'modules\V7-KeeneticModel.ps1'
$CoreHelperPath = Join-Path $PSScriptRoot 'modules\V7-Core.ps1'
$ObservabilityHelperPath = Join-Path $PSScriptRoot 'modules\V7-Observability.ps1'
$RuntimeHelperPath = Join-Path $PSScriptRoot 'modules\V7-Runtime.ps1'
$DeepTelemetryHelperPath = Join-Path $PSScriptRoot 'modules\V7-DeepTelemetry.ps1'
$EvidenceWorkerPath = Join-Path $PSScriptRoot 'VPS-Control-v7-evidence-worker.ps1'
$UiCommonHelperPath = Join-Path $PSScriptRoot 'modules\V7-UiCommon.ps1'
$ReadinessHelperPath = Join-Path $PSScriptRoot 'modules\V7-Readiness.ps1'
$StatusCenterHelperPath = Join-Path $PSScriptRoot 'modules\V7-StatusCenter.ps1'
$ConsistencyHelperPath = Join-Path $PSScriptRoot 'modules\V7-Consistency.ps1'
$MaintenanceHelperPath = Join-Path $PSScriptRoot 'modules\V7-Maintenance.ps1'
$TunnelModelHelperPath = Join-Path $PSScriptRoot 'modules\V7-Tunnels.ps1'
$CapabilityTruthPath = Join-Path $PSScriptRoot 'VPS-Control-v7-CAPABILITY-TRUTH.md'
$TunnelContractPath = Join-Path $PSScriptRoot 'VPS-Control-v7-TUNNEL-CONTRACT.json'
$TunnelManagerPath = Join-Path $PSScriptRoot 'VPS-Control-v7-tunnel-manager.ps1'
foreach($helper in @($StorageHelperPath,$EventsHelperPath,$DemoHelperPath,$KeeneticModelHelperPath,$CoreHelperPath,$ObservabilityHelperPath,$RuntimeHelperPath,$DeepTelemetryHelperPath,$UiCommonHelperPath,$ReadinessHelperPath,$StatusCenterHelperPath,$ConsistencyHelperPath,$MaintenanceHelperPath,$TunnelModelHelperPath)) {
    if(-not(Test-Path -LiteralPath $helper -PathType Leaf)){ throw "Не найден обязательный модуль текущего RC: $helper" }
    . $helper
}
if(-not(Test-Path -LiteralPath $TunnelContractPath -PathType Leaf)){throw "Не найден dual-tunnel contract: $TunnelContractPath"}
if(-not(Test-Path -LiteralPath $TunnelManagerPath -PathType Leaf)){throw "Не найден tunnel manager: $TunnelManagerPath"}

$EngineSourcePath = Join-Path $PSScriptRoot 'VPS-Control-v6.3.1.ps1'
$EnginePath = Join-Path $PSScriptRoot 'VPS-Control-v6.5.ps1'
$EngineUpgradePath = Join-Path $PSScriptRoot 'VPS-Control-v7-engine-upgrade.ps1'
$BundledModulesFile = Join-Path $PSScriptRoot 'VPS-Control-v6.5-modules.json'
$VmGatewayHelperPath = Join-Path $PSScriptRoot 'VPS-Control-v7-vm-gateway.ps1'
$VpsManagerHelperPath = Join-Path $PSScriptRoot 'VPS-Control-v7-vps-manager.ps1'
$KeeneticHelperPath = Join-Path $PSScriptRoot 'VPS-Control-v7-keenetic.ps1'
$ResolvedDataRoot = Resolve-V7DataRoot -BaseDir $PSScriptRoot
$UiStateDir = if($Demo){ Join-Path $ResolvedDataRoot 'demo-ui' } else { $ResolvedDataRoot }
$StorageLayout = Initialize-V7StorageLayout -BaseDir $PSScriptRoot -DataRoot $UiStateDir
$ConfigDir = $StorageLayout.Config
$SecretsDir = $StorageLayout.Secrets
$UiRuntimeDir = $StorageLayout.Runtime
$UiTelemetryDir = $StorageLayout.Telemetry
$UiLogsDir = $StorageLayout.Logs
$UiBackupsDir = $StorageLayout.Backups
$UiExportsDir = $StorageLayout.Exports
$UiNodesDir = $StorageLayout.Nodes
$UiTempDir = $StorageLayout.Temp
$VpsNodeDir = $StorageLayout.Vps
$KeeneticNodeDir = $StorageLayout.Keenetic

$StateDir = if($Demo){ Join-Path $UiRuntimeDir 'demo-engine' } else { Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3' }
$ConfigFile = Join-Path $StateDir 'routing-config.json'
$ConfigBackupFile = Join-Path $StateDir 'routing-config.json.bak'
$RuntimeFile = Join-Path $StateDir 'runtime-state.json'
$WatchdogPidFile = Join-Path $StateDir 'watchdog.pid'
$WatchdogHeartbeatFile = Join-Path $StateDir 'watchdog-heartbeat.json'
$AttentionFile = Join-Path $StateDir 'attention.json'
$LastGoodProfilePath = Join-Path $StateDir 'last-known-good.ppx'
$TelemetryFile = Join-Path $StateDir 'telemetry.jsonl'
$OperationalStatsFile = Join-Path $StateDir 'operational-stats.json'
$IncidentFile = Join-Path $StateDir 'incidents.jsonl'
$DecisionLogFile = Join-Path $StateDir 'route-decisions.log'
$SelfTestHistoryFile = Join-Path $StateDir 'selftest-history.jsonl'
$ModulesFile = Join-Path $StateDir 'modules.json'
$ModulesBackupFile = Join-Path $StateDir 'modules.json.v7.bak'

$UiLogFile = Join-Path $UiLogsDir 'ui.log'
$SocksTraceFile = Join-Path $UiLogsDir 'socks-runtime.log'
$EngineSocksTraceFile = Join-Path $UiLogsDir 'socks-engine.log'
$V7EventsFile = Join-Path $UiLogsDir 'events.jsonl'
$V7RuntimeMetricsFile = Join-Path $UiTelemetryDir 'runtime-metrics.jsonl'
$V7DiagnosticTraceFile = Join-Path $UiTelemetryDir 'diagnostic-trace.jsonl'
$V7OperationEvidenceFile = Join-Path $UiTelemetryDir 'operation-evidence.jsonl'
$V7EnvironmentLatestFile = Join-Path $UiRuntimeDir 'environment-latest.json'
$UiSettingsFile = Join-Path $ConfigDir 'ui-settings.json'
$CustomSettingsFile = Join-Path $ConfigDir 'custom-routes.json'
$VpsProfilesFile = Join-Path $VpsNodeDir 'vps-profiles.json'
$ActiveVpsFile = Join-Path $VpsNodeDir 'active-vps.json'
$VpsSecretsDir = $StorageLayout.VpsSecrets
$VpsHealthDir = $StorageLayout.VpsHealth
$EngineBuildStateFile = Join-Path $UiRuntimeDir 'engine-build-state.json'
$KeeneticConfigFile = Join-Path $KeeneticNodeDir 'keenetic.json'
$KeeneticInventoryFile = Join-Path $KeeneticNodeDir 'inventory.json'
$KeeneticSecretFile = Join-Path $SecretsDir 'keenetic-entware.dpapi'
$StrictBrowserHelperPath = Join-Path $PSScriptRoot 'VPS-Control-v7-browser-strict.ps1'
$MutationMutexName = "Local\VPSControlV63Mutation-$env:USERNAME"
$UiMutexName = "Local\VPSControlV7UI-$env:USERNAME"
$RunValueName = 'VPS Control Center V7'
$RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$PowerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'


function Ensure-ExtendedEngine {
    if($Demo){ return $true }
    try {
        if (-not (Test-Path -LiteralPath $EngineSourcePath)) {
            throw "Не найден исходный стабильный движок VPS-Control-v6.3.1.ps1: $EngineSourcePath"
        }
        if (-not (Test-Path -LiteralPath $EngineUpgradePath)) {
            throw "Не найден генератор расширенного движка: $EngineUpgradePath"
        }

        $sourceSha = Get-FileSha256 $EngineSourcePath
        $upgradeSha = Get-FileSha256 $EngineUpgradePath
        if (-not $sourceSha -or -not $upgradeSha) { throw 'Не удалось вычислить SHA-256 исходного движка или генератора.' }
        $build = Read-JsonFile $EngineBuildStateFile
        $needBuild = -not (Test-Path -LiteralPath $EnginePath)
        if (-not $needBuild) {
            $engineSha = Get-FileSha256 $EnginePath
            if (-not $build -or [string]$build.SourceSha256 -ne $sourceSha -or [string]$build.UpgradeSha256 -ne $upgradeSha -or [string]$build.EngineSha256 -ne $engineSha) {
                $needBuild = $true
            }
        }
        if (-not $needBuild) { return $true }

        $stamp = Get-Date -Format 'yyyyMMdd-HHmmssfff'
        $out = Join-Path $UiTempDir "engine-upgrade-$stamp.out.txt"
        $err = Join-Path $UiTempDir "engine-upgrade-$stamp.err.txt"
        $args = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$EngineUpgradePath`" -SourcePath `"$EngineSourcePath`" -DestinationPath `"$EnginePath`""
        $proc = Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
        $proc.Refresh()
        if ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $EnginePath)) {
            $detail = ((Read-TextFileSmart $err) + "`r`n" + (Read-TextFileSmart $out)).Trim()
            throw "Не удалось сформировать VPS-Control-v6.5.ps1. Код=$($proc.ExitCode). $detail"
        }
        $engineSha = Get-FileSha256 $EnginePath
        if (-not $engineSha) { throw 'V6.5 создан, но его SHA-256 не удалось вычислить.' }
        $buildState = [pscustomobject]@{
            Version = 1
            GeneratedAt = (Get-Date).ToString('o')
            SourceSha256 = $sourceSha
            UpgradeSha256 = $upgradeSha
            EngineSha256 = $engineSha
        }
        Write-TextAtomic -Path $EngineBuildStateFile -Text ($buildState | ConvertTo-Json -Depth 4)
        Remove-Item -LiteralPath $out,$err -Force -ErrorAction SilentlyContinue
        Write-UiLog "V6.5 engine generated and fingerprinted. source=$sourceSha upgrade=$upgradeSha engine=$engineSha"
        return $true
    }
    catch {
        Write-UiLog "V6.5 engine generation failed: $($_.Exception.Message)"
        [System.Windows.Forms.MessageBox]::Show(
            "V7 не может безопасно включить расширенные маршруты.`r`n`r`n$($_.Exception.Message)`r`n`r`nVPS-Control-v6.3.1.ps1 не изменён и остаётся rollback.",
            'VPS Control Center',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
        return $false
    }
}

function Merge-ExtendedModuleCatalog {
    if($Demo){ return $true }
    if (-not (Test-Path -LiteralPath $BundledModulesFile)) { throw "Не найден $BundledModulesFile" }
    $bundled = Read-JsonFile $BundledModulesFile
    if (-not $bundled) { throw 'Не удалось прочитать bundled module catalog V6.5.' }

    $mutex = $null; $acquired = $false
    try {
        $mutex = New-Object System.Threading.Mutex($false, $MutationMutexName)
        try { $acquired = $mutex.WaitOne(15000, $false) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
        if (-not $acquired) { throw 'Истекло время ожидания блокировки при обновлении каталога модулей.' }

        if (-not (Test-Path -LiteralPath $ModulesFile)) {
            Copy-Item -LiteralPath $BundledModulesFile -Destination $ModulesFile -Force
            return $true
        }
        $current = Read-JsonFile $ModulesFile
        if (-not $current) { throw 'Текущий modules.json повреждён; автоматическая перезапись запрещена.' }
        Copy-Item -LiteralPath $ModulesFile -Destination $ModulesBackupFile -Force -ErrorAction SilentlyContinue
        foreach ($module in $ModuleNames) {
            if (-not $current.PSObject.Properties[$module]) {
                $clone = (($bundled.$module | ConvertTo-Json -Depth 12) | ConvertFrom-Json)
                Add-Member -InputObject $current -NotePropertyName $module -NotePropertyValue $clone
            }
        }
        if ($current.PSObject.Properties['Version']) { $current.Version = '3' }
        else { Add-Member -InputObject $current -NotePropertyName Version -NotePropertyValue '3' }
        Write-TextAtomic -Path $ModulesFile -Text ($current | ConvertTo-Json -Depth 12)
        return $true
    }
    finally {
        if ($acquired -and $mutex) { try { $mutex.ReleaseMutex() } catch { } }
        if ($mutex) { try { $mutex.Dispose() } catch { } }
    }
}

function Get-LegacyVpsDefaults {
    $result = [ordered]@{
        Id = 'legacy-examplevps'
        Name = 'Текущий ExampleVPS'
        Host = ''
        SshPort = 22
        User = 'root'
        ExpectedExitIp = '203.0.113.10'
        AuthMode = 'SavedSession'
        SavedSession = 'ExampleVPS'
        KeyFile = ''
    }
    try {
        if (Test-Path -LiteralPath $EngineSourcePath) {
            $raw = Get-Content -LiteralPath $EngineSourcePath -Raw -ErrorAction Stop
            $legacyFields = @(
                [pscustomobject]@{ Source='ExpectedVpsIp'; Target='ExpectedExitIp' },
                [pscustomobject]@{ Source='PuttySession'; Target='SavedSession' },
                [pscustomobject]@{ Source='PuttyUser'; Target='User' }
            )
            foreach ($pair in $legacyFields) {
                $m = [regex]::Match($raw, "(?m)^\s*\`$$($pair.Source)\s*=\s*'([^']*)'\s*$")
                if ($m.Success -and $m.Groups[1].Value) { $result[$pair.Target] = $m.Groups[1].Value }
            }
        }
    }
    catch { }
    return [pscustomobject]$result
}

function New-VpsProfileDocument {
    $legacy = Get-LegacyVpsDefaults
    return [pscustomobject]@{
        Version = 1
        ActiveId = [string]$legacy.Id
        Profiles = @($legacy)
    }
}

function Get-VpsProfileDocument {
    $doc = Read-JsonFile $VpsProfilesFile
    if (-not $doc -or -not $doc.Profiles) { return (New-VpsProfileDocument) }
    return $doc
}

function Save-VpsProfileDocument($Doc) {
    Write-TextAtomic -Path $VpsProfilesFile -Text ($Doc | ConvertTo-Json -Depth 10)
}

function Get-VpsProfileById([string]$Id) {
    if (-not $Id) { return $null }
    $doc = Get-VpsProfileDocument
    return @($doc.Profiles | Where-Object { [string]$_.Id -eq $Id } | Select-Object -First 1)[0]
}

function Get-ActiveVpsProfile {
    $doc = Get-VpsProfileDocument
    $profile = @($doc.Profiles | Where-Object { [string]$_.Id -eq [string]$doc.ActiveId } | Select-Object -First 1)[0]
    if (-not $profile -and @($doc.Profiles).Count -gt 0) { $profile = @($doc.Profiles)[0] }
    return $profile
}

function Sync-ActiveVpsFile {
    $profile = Get-ActiveVpsProfile
    if (-not $profile) { throw 'Нет активного профиля VPS.' }
    $safe = [ordered]@{
        Id = [string]$profile.Id
        Name = [string]$profile.Name
        Host = [string]$profile.Host
        SshPort = [int]$profile.SshPort
        User = [string]$profile.User
        ExpectedExitIp = [string]$profile.ExpectedExitIp
        AuthMode = [string]$profile.AuthMode
        SavedSession = [string]$profile.SavedSession
        KeyFile = [string]$profile.KeyFile
        SecretId = [string]$profile.Id
        UpdatedAt = (Get-Date).ToString('o')
    }
    Write-TextAtomic -Path $ActiveVpsFile -Text (([pscustomobject]$safe) | ConvertTo-Json -Depth 5)
}

function Initialize-VpsProfileStore {
    if (-not (Test-Path -LiteralPath $VpsProfilesFile)) {
        $doc = New-VpsProfileDocument
        Save-VpsProfileDocument $doc
    }
    Sync-ActiveVpsFile
    return $true
}

function Get-VpsSecretPath([string]$ProfileId) {
    if ($ProfileId -notmatch '^[A-Za-z0-9._-]+$') { throw 'Некорректный идентификатор профиля VPS.' }
    return (Join-Path $VpsSecretsDir ($ProfileId + '.dpapi'))
}

function Test-VpsSecretStored([string]$ProfileId) {
    try { return (Test-Path -LiteralPath (Get-VpsSecretPath $ProfileId)) } catch { return $false }
}

function ConvertTo-V7SecureStringFromText([string]$Text) {
    $secure = New-Object Security.SecureString
    try {
        if ($null -ne $Text) {
            foreach ($ch in $Text.ToCharArray()) {
                $secure.AppendChar($ch)
            }
        }
        $secure.MakeReadOnly()
        return $secure
    }
    catch {
        try { $secure.Dispose() } catch { Write-Debug 'SecureString disposal failed during conversion cleanup.' }
        throw
    }
}

function Save-VpsSecret([string]$ProfileId, [string]$SecretText) {
    if (-not $SecretText) { return }
    $secure = ConvertTo-V7SecureStringFromText -Text $SecretText
    try {
        $cipher = ConvertFrom-SecureString -SecureString $secure
        Write-TextAtomic -Path (Get-VpsSecretPath $ProfileId) -Text $cipher
    }
    finally {
        if ($secure) { try { $secure.Dispose() } catch { Write-Debug 'SecureString disposal failed during persistence cleanup.' } }
    }
}

function Remove-VpsSecret([string]$ProfileId) {
    try { Remove-Item -LiteralPath (Get-VpsSecretPath $ProfileId) -Force -ErrorAction SilentlyContinue } catch { }
}

function Test-VpsProfileFields($Profile) {
    if (-not ([string]$Profile.Name).Trim()) { throw 'Укажите понятное имя VPS.' }
    if (-not ([string]$Profile.User).Trim()) { throw 'Укажите SSH-логин.' }
    $port = [int]$Profile.SshPort
    if ($port -lt 1 -or $port -gt 65535) { throw 'SSH-порт должен быть от 1 до 65535.' }
    $ipObj = $null
    if (-not [System.Net.IPAddress]::TryParse(([string]$Profile.ExpectedExitIp).Trim(), [ref]$ipObj)) { throw 'Укажите ожидаемый внешний IP VPS. Он нужен для fail-closed проверки правильного сервера.' }
    $mode = [string]$Profile.AuthMode
    if (@('SavedSession','Password','PrivateKey','Pageant') -notcontains $mode) { throw 'Неизвестный способ подключения VPS.' }
    if ($mode -eq 'SavedSession') {
        if (-not ([string]$Profile.SavedSession).Trim()) { throw 'Для режима PuTTY session укажите имя сохранённой сессии.' }
    }
    else {
        $vpsHost = ([string]$Profile.Host).Trim()
        if (-not $vpsHost) { throw 'Для подключения по IP укажите IP или hostname VPS.' }
        if ($vpsHost -match '[\s;&|<>]') { throw 'IP/hostname содержит недопустимые символы.' }
        if ($mode -eq 'PrivateKey') {
            $key = ([string]$Profile.KeyFile).Trim()
            if (-not $key) { throw 'Для режима SSH-ключ укажите файл приватного ключа PuTTY (.ppk).' }
            if (-not (Test-Path -LiteralPath $key -PathType Leaf)) { throw "Файл SSH-ключа не найден: $key" }
        }
    }
    return $true
}

function Save-OrUpdateVpsProfile($Profile, [string]$Password, [bool]$RememberPassword) {
    [void](Test-VpsProfileFields $Profile)
    $doc = Get-VpsProfileDocument
    $profiles = New-Object System.Collections.ArrayList
    $found = $false
    foreach ($item in @($doc.Profiles)) {
        if ([string]$item.Id -eq [string]$Profile.Id) { [void]$profiles.Add($Profile); $found = $true }
        else { [void]$profiles.Add($item) }
    }
    if (-not $found) { [void]$profiles.Add($Profile) }
    $doc.Profiles = @($profiles)
    if (-not $doc.ActiveId) { $doc.ActiveId = [string]$Profile.Id }
    Save-VpsProfileDocument $doc
    if ($RememberPassword -and $Password) { Save-VpsSecret -ProfileId ([string]$Profile.Id) -SecretText $Password }
    elseif (-not $RememberPassword) { Remove-VpsSecret ([string]$Profile.Id) }
    Sync-ActiveVpsFile
    return $true
}

function Set-ActiveVpsProfile([string]$ProfileId) {
    $doc = Get-VpsProfileDocument
    $p = @($doc.Profiles | Where-Object { [string]$_.Id -eq $ProfileId } | Select-Object -First 1)[0]
    if (-not $p) { throw 'Профиль VPS не найден.' }
    [void](Test-VpsProfileFields $p)
    if ([string]$p.AuthMode -eq 'Password' -and -not (Test-VpsSecretStored $ProfileId)) { throw 'Для этого VPS не сохранён пароль. Сначала сохраните профиль с паролем.' }
    if (-not (Test-VpsPreflightReady $ProfileId)) { throw 'Перед переключением активного VPS выполните «Оценить / предпроверка». Нужен свежий PASS SSH + совпадение ожидаемого exit IP (не старше 15 минут).' }
    $doc.ActiveId = $ProfileId
    Save-VpsProfileDocument $doc
    Sync-ActiveVpsFile
    return $p
}

function Get-VpsHealthPath([string]$ProfileId) {
    if ($ProfileId -notmatch '^[A-Za-z0-9._-]+$') { throw 'Некорректный идентификатор профиля VPS.' }
    return (Join-Path $VpsHealthDir ($ProfileId + '.json'))
}

function Get-VpsHealthResult([string]$ProfileId) {
    try { return (Read-JsonFile (Get-VpsHealthPath $ProfileId)) } catch { return $null }
}

function Test-VpsPreflightReady([string]$ProfileId) {
    $h = Get-VpsHealthResult $ProfileId
    $p = Get-VpsProfileById $ProfileId
    if (-not $h -or -not $p) { return $false }
    try {
        $t = [datetimeoffset]::Parse([string]$h.GeneratedAt)
        if ((([datetimeoffset]::Now - $t).TotalMinutes) -gt 15) { return $false }
    } catch { return $false }
    foreach ($name in @('Host','User','ExpectedExitIp','AuthMode','SavedSession','KeyFile')) {
        if ([string]$h.$name -ne [string]$p.$name) { return $false }
    }
    try { if ([int]$h.SshPort -ne [int]$p.SshPort) { return $false } } catch { return $false }
    return ([bool]$h.SshOk -and [bool]$h.ExitIpOk)
}

function Get-PageantPath {
    $candidates = New-Object System.Collections.ArrayList
    try {
        if (Test-Path -LiteralPath $EngineSourcePath) {
            $raw = Get-Content -LiteralPath $EngineSourcePath -Raw -ErrorAction SilentlyContinue
            $m = [regex]::Match($raw, "(?m)^\s*\`$PuttyPath\s*=\s*'([^']+)'\s*$")
            if ($m.Success) { [void]$candidates.Add((Join-Path (Split-Path -Parent $m.Groups[1].Value) 'pageant.exe')) }
        }
    } catch { }
    foreach ($path in @(
        (Join-Path $env:ProgramFiles 'PuTTY\pageant.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'PuTTY\pageant.exe')
    )) { if ($path) { [void]$candidates.Add($path) } }
    try { $cmd = Get-Command pageant.exe -ErrorAction SilentlyContinue; if ($cmd -and $cmd.Source) { [void]$candidates.Add($cmd.Source) } } catch { }
    foreach ($x in @($candidates | Select-Object -Unique)) { if ($x -and (Test-Path -LiteralPath $x -PathType Leaf)) { return $x } }
    return ''
}

function Remove-VpsProfile([string]$ProfileId) {
    $doc = Get-VpsProfileDocument
    if ([string]$doc.ActiveId -eq $ProfileId) { throw 'Нельзя удалить активный VPS. Сначала выполните предпроверку другого профиля и явно сделайте его активным.' }
    $remaining = @($doc.Profiles | Where-Object { [string]$_.Id -ne $ProfileId })
    if ($remaining.Count -eq 0) { throw 'Нельзя удалить последний профиль VPS. Сначала создайте другой.' }
    $doc.Profiles = $remaining
    Save-VpsProfileDocument $doc
    Remove-VpsSecret $ProfileId
    try { Remove-Item -LiteralPath (Get-VpsHealthPath $ProfileId) -Force -ErrorAction SilentlyContinue } catch { }
    Sync-ActiveVpsFile
}

function Restore-ActiveVpsProfile([string]$ProfileId) {
    if (-not $ProfileId) { return }
    $doc = Get-VpsProfileDocument
    if (-not (@($doc.Profiles | Where-Object { [string]$_.Id -eq $ProfileId }).Count)) { return }
    $doc.ActiveId = $ProfileId
    Save-VpsProfileDocument $doc
    Sync-ActiveVpsFile
}

$script:VpsProcess = $null
$script:KeeneticProcess = $null
$script:KeeneticOut = ''
$script:KeeneticErr = ''
$script:KeeneticAction = ''
$script:KeeneticStartedAt = $null
$script:KeeneticOutputControl = $null
$script:KeeneticStatusControl = $null
$script:KeeneticOverviewRouter = $null
$script:KeeneticOverviewEntware = $null
$script:KeeneticOverviewPackages = $null
$script:KeeneticOverviewStorage = $null
$script:KeeneticOverviewSummary = $null
$script:VpsOut = $null
$script:VpsErr = $null
$script:VpsAction = ''
$script:VpsProfileId = ''
$script:VpsOutputControl = $null
$script:VpsStatusControl = $null
$script:PendingVpsSwitch = $null
$script:ConfigDirty = $false
$script:BusyControls = New-Object System.Collections.ArrayList
$script:BusyProgress = $null
$script:LongOperationWarned = $false

function Test-UiOperationBusy {
    # A child-process object remains the operation lease until its completion handler
    # consumes exit/output and clears the object.  HasExited alone is insufficient:
    # a fast failure can exit before the UI timer processes it, allowing overlapping Apply.
    $engineBusy = [bool]$script:EngineProcess
    $vpsBusy = [bool]$script:VpsProcess
    $keeneticBusy = [bool]$script:KeeneticProcess
    return ($engineBusy -or $vpsBusy -or $keeneticBusy)
}

function Update-UiBusyState {
    $busy = Test-UiOperationBusy
    foreach ($control in @($script:BusyControls)) {
        try { if ($control -and -not $control.IsDisposed) { $control.Enabled = -not $busy } } catch { }
    }
    try {
        if ($script:BusyProgress) {
            $script:BusyProgress.Visible = $busy
            if ($busy) { $script:BusyProgress.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee }
        }
    } catch { }
    try {
        if ($miApply) { $miApply.Enabled = -not $busy }
        if ($miDirect) { $miDirect.Enabled = -not $busy }
        if ($miRestart) { $miRestart.Enabled = -not $busy }
        if ($miSelfTest) { $miSelfTest.Enabled = -not $busy }
    } catch { }
    if (-not $busy) { try { Update-VpsAuthUi } catch { } }
}

function Start-VpsManagerAction([string]$Action, [string]$ProfileId) {
    if($Demo){ [System.Windows.Forms.MessageBox]::Show('Демо-режим: операции SSH/VPS заблокированы. Интерфейс и данные можно изучать без сетевых изменений.','VPS Control Center','OK','Information')|Out-Null; Write-UiEvent 'DEMO' 'Операция VPS заблокирована в демо' $Action; return $false }
    if (-not (Test-Path -LiteralPath $VpsManagerHelperPath)) { throw "Не найден VPS Manager helper: $VpsManagerHelperPath" }
    if (Test-UiOperationBusy) {
        [System.Windows.Forms.MessageBox]::Show('Уже выполняется операция Control Center. Дождитесь её завершения.', 'VPS Control Center', 'OK', 'Information') | Out-Null
        return $false
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmssfff'
    $script:VpsOut = Join-Path $UiTempDir "vps-$stamp.out.txt"
    $script:VpsErr = Join-Path $UiTempDir "vps-$stamp.err.txt"
    $args = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$VpsManagerHelperPath`" -Action $Action -ProfileId `"$ProfileId`""
    try {
        $script:VpsProcess = Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $script:VpsOut -RedirectStandardError $script:VpsErr
        $script:VpsAction = $Action
        $script:VpsProfileId = $ProfileId
        $script:VpsStartedAt = Get-Date
        $script:LongOperationWarned = $false
        if ($script:VpsStatusControl) { $script:VpsStatusControl.Text = 'Операция с VPS выполняется…'; $script:VpsStatusControl.ForeColor = [System.Drawing.Color]::DarkOrange }
        Write-UiLog "VPS helper START action=$Action profile=$ProfileId pid=$($script:VpsProcess.Id)"
        Update-UiBusyState
        return $true
    }
    catch {
        $script:VpsProcess = $null
        Write-UiLog "VPS helper start failed action=$Action profile=$ProfileId :: $($_.Exception.Message)"
        [System.Windows.Forms.MessageBox]::Show("Не удалось запустить операцию VPS.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', 'OK', 'Error') | Out-Null
        Update-UiBusyState
        return $false
    }
}

function Complete-VpsManagerActionIfNeeded {
    if (-not $script:VpsProcess) { return }
    try { if (-not $script:VpsProcess.HasExited) { return } } catch { return }
    $rc = -1
    try { $script:VpsProcess.WaitForExit(); $script:VpsProcess.Refresh(); $rc = [int]$script:VpsProcess.ExitCode } catch { }
    $text = ''
    if (Test-Path -LiteralPath $script:VpsOut) { $text += Read-TextFileSmart $script:VpsOut }
    if (Test-Path -LiteralPath $script:VpsErr) { $e = Read-TextFileSmart $script:VpsErr; if ($e) { $text += "`r`n" + $e } }
    if ($script:VpsOutputControl) { $script:VpsOutputControl.Text = $text.Trim(); $script:VpsOutputControl.SelectionStart=0; $script:VpsOutputControl.SelectionLength=0; $script:VpsOutputControl.ScrollToCaret() }
    if ($script:VpsStatusControl) {
        if ($rc -eq 0) { $script:VpsStatusControl.Text = 'Операция VPS завершена успешно.'; $script:VpsStatusControl.ForeColor = [System.Drawing.Color]::DarkGreen }
        else { $script:VpsStatusControl.Text = "Операция VPS завершилась с кодом $rc."; $script:VpsStatusControl.ForeColor = [System.Drawing.Color]::DarkRed }
    }
    try { if ($script:VpsAction -eq 'Health' -and $script:VpsProfileId) { Refresh-VpsHealthUi $script:VpsProfileId } } catch { }
    $durationMs=0;if($script:VpsStartedAt){try{$durationMs=[int]((Get-Date)-$script:VpsStartedAt).TotalMilliseconds}catch{}}
    try{Write-V7OperationEvidence -Component 'VPS' -Action ([string]$script:VpsAction) -ExitCode $rc -DurationMs $durationMs -Text $text -Meta ("profile=$([string]$script:VpsProfileId)") }catch{}
    Write-UiLog "VPS helper END action=$($script:VpsAction) profile=$($script:VpsProfileId) rc=$rc durationMs=$durationMs"; Write-UiEvent 'VPS' "VPS: $($script:VpsAction)" "profile=$($script:VpsProfileId); rc=$rc; durationMs=$durationMs" $(if($rc -eq 0){'INFO'}else{'ERROR'})
    Remove-Item -LiteralPath $script:VpsOut -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $script:VpsErr -Force -ErrorAction SilentlyContinue
    try { $script:VpsProcess.Dispose() } catch { }
    $script:VpsProcess = $null
    $script:VpsAction = ''
    $script:VpsStartedAt = $null
    $script:LongOperationWarned = $false
    Update-UiBusyState
}


function Get-KeeneticConfig {
    $d=[pscustomobject]@{Host='192.0.2.1';EntwareSshPort=222;EntwareUser='root';EntwareHostKey=''}
    $x=Read-JsonFile $KeeneticConfigFile
    if($x){
        if($x.Host){$d.Host=[string]$x.Host}
        try{if([int]$x.EntwareSshPort -gt 0){$d.EntwareSshPort=[int]$x.EntwareSshPort}}catch{}
        if($x.EntwareUser){$d.EntwareUser=[string]$x.EntwareUser}
        if($x.EntwareHostKey){$d.EntwareHostKey=[string]$x.EntwareHostKey}
    }
    return $d
}
function Save-KeeneticConfig([string]$RouterAddress,[int]$Port,[string]$User,[Security.SecureString]$Secret,[bool]$Remember){
    $routerAddress2=$RouterAddress.Trim();if(-not $routerAddress2){throw 'Не указан адрес Keenetic.'}
    if($Port -lt 1 -or $Port -gt 65535){throw 'Некорректный SSH-порт Entware.'}
    $user2=$User.Trim();if(-not $user2){throw 'Не указан пользователь Entware SSH.'}
    $old=Read-JsonFile $KeeneticConfigFile
    $hostKey=''
    if($old -and [string]$old.Host -eq $routerAddress2 -and [int]$old.EntwareSshPort -eq $Port -and $old.EntwareHostKey){$hostKey=[string]$old.EntwareHostKey}
    $obj=[pscustomobject]@{Version=3;Host=$routerAddress2;EntwareSshPort=$Port;EntwareUser=$user2;EntwareHostKey=$hostKey;UpdatedAt=(Get-Date).ToString('o')}
    Write-TextAtomic -Path $KeeneticConfigFile -Text ($obj|ConvertTo-Json -Depth 4)
    if($Remember -and $null -ne $Secret -and $Secret.Length -gt 0){
        $enc=ConvertFrom-SecureString -SecureString $Secret
        Write-TextAtomic -Path $KeeneticSecretFile -Text $enc
    }
    elseif(-not $Remember){
        Remove-Item -LiteralPath $KeeneticSecretFile -Force -ErrorAction SilentlyContinue
    }
    return $true
}
function Save-KeeneticHostKey([string]$Fingerprint){
    if(-not $Fingerprint -or $Fingerprint -notmatch '^(SHA256:[A-Za-z0-9+/=]+|(?i:(?:[0-9a-f]{2}:){15}[0-9a-f]{2}))$'){throw 'Некорректный SSH fingerprint.'}
    $cfg=Get-KeeneticConfig
    $obj=[pscustomobject]@{Version=3;Host=[string]$cfg.Host;EntwareSshPort=[int]$cfg.EntwareSshPort;EntwareUser=[string]$cfg.EntwareUser;EntwareHostKey=$Fingerprint;UpdatedAt=(Get-Date).ToString('o')}
    Write-TextAtomic -Path $KeeneticConfigFile -Text ($obj|ConvertTo-Json -Depth 4)
    return $true
}
function Start-KeeneticAction([string]$Action){
    if($Demo){ [System.Windows.Forms.MessageBox]::Show('Демо-режим: операции Keenetic/SSH заблокированы.','VPS Control Center','OK','Information')|Out-Null; Write-UiEvent 'DEMO' 'Операция Keenetic заблокирована в демо' $Action; return $false }
    if(-not(Test-Path -LiteralPath $KeeneticHelperPath)){throw "Не найден Keenetic helper: $KeeneticHelperPath"}
    if(Test-UiOperationBusy){[System.Windows.Forms.MessageBox]::Show('Уже выполняется операция Control Center. Дождитесь её завершения.','VPS Control Center','OK','Information')|Out-Null;return $false}
    $stamp=Get-Date -Format 'yyyyMMdd-HHmmssfff';$script:KeeneticOut=Join-Path $UiTempDir "keenetic-$stamp.out.txt";$script:KeeneticErr=Join-Path $UiTempDir "keenetic-$stamp.err.txt"
    $args="-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$KeeneticHelperPath`" -Action $Action"
    try{$script:KeeneticProcess=Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $script:KeeneticOut -RedirectStandardError $script:KeeneticErr;$script:KeeneticAction=$Action;$script:KeeneticStartedAt=Get-Date;$script:LongOperationWarned=$false;if($script:KeeneticStatusControl){$script:KeeneticStatusControl.Text='Операция Keenetic выполняется…';$script:KeeneticStatusControl.ForeColor=[Drawing.Color]::DarkOrange};Write-UiLog "Keenetic helper START action=$Action pid=$($script:KeeneticProcess.Id)";Update-UiBusyState;return $true}catch{$script:KeeneticProcess=$null;Write-UiLog "Keenetic helper start failed action=$Action :: $($_.Exception.Message)";[System.Windows.Forms.MessageBox]::Show("Не удалось запустить операцию Keenetic.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null;Update-UiBusyState;return $false}
}
function Complete-KeeneticActionIfNeeded {
    if(-not $script:KeeneticProcess){return}
    try{if(-not $script:KeeneticProcess.HasExited){return}}catch{return}
    $rc=-1
    try{$script:KeeneticProcess.WaitForExit();$script:KeeneticProcess.Refresh();$rc=[int]$script:KeeneticProcess.ExitCode}catch{}
    $text=''
    if(Test-Path -LiteralPath $script:KeeneticOut){$text+=Read-TextFileSmart $script:KeeneticOut}
    if(Test-Path -LiteralPath $script:KeeneticErr){$e=Read-TextFileSmart $script:KeeneticErr;if($e){$text+="`r`n"+$e}}
    if($script:KeeneticOutputControl){$script:KeeneticOutputControl.Text=$text.Trim();$script:KeeneticOutputControl.SelectionStart=0;$script:KeeneticOutputControl.SelectionLength=0;$script:KeeneticOutputControl.ScrollToCaret()}

    $trustAccepted=$false
    $trustRejected=$false
    if($script:KeeneticAction -eq 'HostKeyProbe' -and $rc -eq 0){
        $m=[regex]::Match($text,'(?im)^HOSTKEY_FINGERPRINT=(SHA256:[A-Za-z0-9+/=]+|(?:[0-9a-f]{2}:){15}[0-9a-f]{2})\s*$')
        if($m.Success){
            $fp=$m.Groups[1].Value
            $cfg=Get-KeeneticConfig
            $question="Получен SSH fingerprint Keenetic/Entware:`r`n`r`n$fp`r`n`r`nАдрес: $([string]$cfg.Host):$([int]$cfg.EntwareSshPort)`r`n`r`nДоверять этому ключу для последующих автоматических SSH-операций?`r`nПароль при этом не показывается и не передаётся в интерактивную консоль."
            if([Windows.Forms.MessageBox]::Show($question,'VPS Control Center · SSH host key','YesNo','Question') -eq [Windows.Forms.DialogResult]::Yes){
                try{[void](Save-KeeneticHostKey $fp);$trustAccepted=$true}catch{$rc=91;$text+="`r`nНе удалось сохранить fingerprint: $($_.Exception.Message)"}
            }else{$trustRejected=$true}
        }else{$rc=92;$text+="`r`nНе удалось выделить SHA256 fingerprint из ответа plink."}
    }

    $inventoryOk=$true
    $inventoryError=''
    $mergeInventory=($script:KeeneticAction -notin @('HostKeyProbe','OpenEntwareSsh'))
    if($mergeInventory){
        try{
            $existingInventory=Read-JsonFile $KeeneticInventoryFile
            $inventory=Merge-V7KeeneticInventory -Existing $existingInventory -Text $text -Action $script:KeeneticAction -ExitCode $rc
            Write-TextAtomic -Path $KeeneticInventoryFile -Text ($inventory|ConvertTo-Json -Depth 8)
            if($script:KeeneticOverviewRouter){$script:KeeneticOverviewRouter.Text=Get-V7KeeneticRouterUi $inventory}
            if($script:KeeneticOverviewEntware){$script:KeeneticOverviewEntware.Text=Get-V7KeeneticEntwareUi $inventory}
            if($script:KeeneticOverviewPackages){$script:KeeneticOverviewPackages.Text=("Пакеты: $(if($inventory.Packages){$inventory.Packages}else{'—'}) · обновления: $(if($inventory.Updates){$inventory.Updates}else{'—'})")}
            if($script:KeeneticOverviewStorage -and $inventory.OptFs){$script:KeeneticOverviewStorage.Text=[string]$inventory.OptFs}
            if($script:KeeneticOverviewSummary){$script:KeeneticOverviewSummary.Text=Format-V7KeeneticInventorySummary $inventory}
        }catch{
            $inventoryOk=$false;$inventoryError=$_.Exception.Message;Write-UiLog "Keenetic inventory merge failed: $inventoryError"
        }
    }

    if($script:KeeneticStatusControl){
        if($trustAccepted){$script:KeeneticStatusControl.Text='SSH fingerprint подтверждён и закреплён. «Статус Entware» теперь использует pinned host key + сохранённый DPAPI-пароль без повторного ввода.';$script:KeeneticStatusControl.ForeColor=[Drawing.Color]::DarkGreen}
        elseif($trustRejected){$script:KeeneticStatusControl.Text='SSH fingerprint не принят. Автоматические Entware SSH-операции остаются заблокированы fail-closed.';$script:KeeneticStatusControl.ForeColor=[Drawing.Color]::DarkOrange}
        elseif($rc -ne 0){$script:KeeneticStatusControl.Text="Операция Keenetic завершилась с кодом $rc.";$script:KeeneticStatusControl.ForeColor=[Drawing.Color]::DarkRed}
        elseif(-not $inventoryOk){$script:KeeneticStatusControl.Text='Операция завершена, но локальный inventory не обновлён. Проверьте диагностику.';$script:KeeneticStatusControl.ForeColor=[Drawing.Color]::DarkOrange}
        else{
            if($script:KeeneticAction -eq 'OpenEntwareSsh'){$script:KeeneticStatusControl.Text='Интерактивная SSH-консоль открыта вручную. Для автоматизации рекомендуется «Проверить / доверить SSH-ключ».'}
            elseif($script:KeeneticAction -eq 'InstallReadiness'){$script:KeeneticStatusControl.Text='Readiness-план сформирован; install/remove по-прежнему заблокирован.'}
            else{$script:KeeneticStatusControl.Text='Операция Keenetic завершена успешно; inventory обновлён.'}
            $script:KeeneticStatusControl.ForeColor=[Drawing.Color]::DarkGreen
        }
    }

    $eventSeverity='INFO';$eventDetail="rc=$rc; inventory=$(if($mergeInventory){if($inventoryOk){'PASS'}else{'FAILED'}}else{'SKIPPED'})"
    if($rc -ne 0){$eventSeverity='ERROR'}elseif(-not $inventoryOk){$eventSeverity='WARN'}elseif($trustRejected){$eventSeverity='WARN'}
    if($inventoryError){$eventDetail+="; $inventoryError"}
    $durationMs=0;if($script:KeeneticStartedAt){try{$durationMs=[int]((Get-Date)-$script:KeeneticStartedAt).TotalMilliseconds}catch{}}
    $operationMeta="inventory=$(if($mergeInventory){if($inventoryOk){'PASS'}else{'FAILED'}}else{'SKIPPED'}); trustAccepted=$trustAccepted; trustRejected=$trustRejected"
    try{Write-V7OperationEvidence -Component 'Keenetic' -Action ([string]$script:KeeneticAction) -ExitCode $rc -DurationMs $durationMs -Text $text -Meta $operationMeta}catch{}
    Write-UiLog "Keenetic helper END action=$($script:KeeneticAction) rc=$rc durationMs=$durationMs inventory=$(if($mergeInventory){if($inventoryOk){'PASS'}else{'FAILED'}}else{'SKIPPED'})"
    Write-UiEvent 'KEENETIC' "Keenetic: $($script:KeeneticAction)" ("$eventDetail; durationMs=$durationMs") $eventSeverity
    Remove-Item -LiteralPath $script:KeeneticOut,$script:KeeneticErr -Force -ErrorAction SilentlyContinue
    try{$script:KeeneticProcess.Dispose()}catch{}
    $script:KeeneticProcess=$null;$script:KeeneticAction='';$script:KeeneticStartedAt=$null;$script:LongOperationWarned=$false
    Update-UiBusyState
}

function Get-DefaultCustomSettings {
    return [pscustomobject]@{
        CustomExePath = ''
        CustomSiteUrl = ''
        VmInterfaceAlias = ''
        VmListenAddress = ''
        VmListenPort = 1081
        VmTunnelId = 'PRIMARY_AUTO'
        StrictYandex = $false
        StrictEdge = $false
    }
}

function Get-CustomSettings {
    $d = Get-DefaultCustomSettings
    $s = Read-JsonFile $CustomSettingsFile
    if (-not $s) { return $d }
    if ($s.CustomExePath) { $d.CustomExePath = [string]$s.CustomExePath }
    if ($s.CustomSiteUrl) { $d.CustomSiteUrl = [string]$s.CustomSiteUrl }
    if ($s.VmInterfaceAlias) { $d.VmInterfaceAlias = [string]$s.VmInterfaceAlias }
    if ($s.VmListenAddress) { $d.VmListenAddress = [string]$s.VmListenAddress }
    try { if ([int]$s.VmListenPort -ge 1024 -and [int]$s.VmListenPort -le 65535) { $d.VmListenPort = [int]$s.VmListenPort } } catch { }
    if([string]$s.VmTunnelId -in @('PRIMARY_AUTO','RESERVE_MANUAL')){$d.VmTunnelId=[string]$s.VmTunnelId}
    if ($s.StrictYandex -ne $null) { $d.StrictYandex = [bool]$s.StrictYandex }
    if ($s.StrictEdge -ne $null) { $d.StrictEdge = [bool]$s.StrictEdge }
    return $d
}

function Save-CustomSettings($Settings) {
    Write-TextAtomic -Path $CustomSettingsFile -Text ($Settings | ConvertTo-Json -Depth 5)
}

function Get-BrowserExecutable([string]$Module) {
    $candidates = New-Object System.Collections.ArrayList
    if ($Module -eq 'YandexBrowser') {
        foreach ($p in @(
            (Join-Path $env:LOCALAPPDATA 'Yandex\YandexBrowser\Application\browser.exe'),
            (Join-Path $env:ProgramFiles 'Yandex\YandexBrowser\Application\browser.exe'),
            (Join-Path ${env:ProgramFiles(x86)} 'Yandex\YandexBrowser\Application\browser.exe')
        )) { if ($p) { [void]$candidates.Add($p) } }
    }
    elseif ($Module -eq 'Edge') {
        foreach ($p in @(
            (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
            (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
            (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe')
        )) { if ($p) { [void]$candidates.Add($p) } }
    }
    foreach ($p in @($candidates | Select-Object -Unique)) { if ($p -and (Test-Path -LiteralPath $p -PathType Leaf)) { return $p } }
    return ''
}

function Invoke-StrictBrowserHelper([string]$Action, [string]$Module) {
    if($Demo){ throw 'Демо-режим: Windows Firewall и запуск браузеров не изменяются.' }
    if (-not (Test-Path -LiteralPath $StrictBrowserHelperPath)) { throw "Не найден helper строгого режима браузера: $StrictBrowserHelperPath" }
    $exe = Get-BrowserExecutable $Module
    if ($Action -eq 'Enable' -and -not $exe) { throw "Не найден исполняемый файл браузера: $Module" }
    $browser = if ($Module -eq 'YandexBrowser') { 'Yandex' } else { 'Edge' }
    $args = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$StrictBrowserHelperPath`" -Action $Action -Browser $browser"
    if ($exe) { $args += " -ExePath `"$exe`"" }
    if ($Action -in @('Enable','Disable')) {
        $proc = Start-Process -FilePath $PowerShellExe -ArgumentList $args -Verb RunAs -Wait -PassThru
        $proc.Refresh()
        return [int]$proc.ExitCode
    }
    $stamp=Get-Date -Format 'yyyyMMdd-HHmmssfff'; $o=Join-Path $UiTempDir "strict-browser-$stamp.out.txt"; $e=Join-Path $UiTempDir "strict-browser-$stamp.err.txt"
    $proc=Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $o -RedirectStandardError $e; $proc.Refresh()
    $text=((Read-TextFileSmart $o)+"`r`n"+(Read-TextFileSmart $e)).Trim(); Remove-Item $o,$e -Force -ErrorAction SilentlyContinue
    return [pscustomobject]@{ ExitCode=[int]$proc.ExitCode; Output=$text }
}

function Invoke-EngineActionSync([string]$Action) {
    if($Demo){$x=Invoke-V7DemoAction -Action $Action -StateDir $StateDir -ModuleNames $ModuleNames;return [pscustomobject]@{ExitCode=[int]$x.ExitCode;Output=[string]$x.Text}}
    if (-not (Test-Path -LiteralPath $EnginePath)) { throw "Расширенный движок недоступен: $EnginePath" }
    $stamp=Get-Date -Format 'yyyyMMdd-HHmmssfff'; $o=Join-Path $UiTempDir "engine-sync-$stamp.out.txt"; $e=Join-Path $UiTempDir "engine-sync-$stamp.err.txt"
    $args="-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$EnginePath`" -Action $Action -NoAppLaunch"
    $proc=Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $o -RedirectStandardError $e; $proc.Refresh()
    $text=((Read-TextFileSmart $o)+"`r`n"+(Read-TextFileSmart $e)).Trim(); Remove-Item $o,$e -Force -ErrorAction SilentlyContinue
    return [pscustomobject]@{ ExitCode=[int]$proc.ExitCode; Output=$text }
}

function Start-StrictBrowser([string]$Module) {
    if($Demo){throw 'Демо-режим: строгий запуск браузера не изменяет Windows Firewall и реальные процессы.'}
    $processName = if ($Module -eq 'YandexBrowser') { 'browser' } else { 'msedge' }
    if (Get-Process -Name $processName -ErrorAction SilentlyContinue) {
        throw 'Браузер уже запущен. Полностью закройте все его окна/фоновые процессы и повторите запуск, иначе Chromium может передать новое окно старому процессу без строгих параметров.'
    }
    $exe = Get-BrowserExecutable $Module
    if (-not $exe) { throw 'Исполняемый файл браузера не найден автоматически.' }
    $cfg=Get-ConfigSnapshot; $cfg.$Module='VPS'; if (-not (Save-ConfigSnapshot $cfg)) { throw 'Не удалось сохранить режим VPS для браузера.' }
    $apply=Invoke-EngineActionSync 'Apply'; if ($apply.ExitCode -ne 0) { throw "Не удалось применить VPS-маршрут перед запуском браузера. $($apply.Output)" }
    $status=Invoke-StrictBrowserHelper 'Status' $Module
    if ($status.ExitCode -ne 0 -or $status.Output -notmatch 'Healthy=True') { throw 'Строгая UDP-защита не прошла проверку целостности. Сначала отметьте строгий режим и нажмите «Применить строгую защиту».' }
    Start-Process -FilePath $exe -ArgumentList '--disable-quic' | Out-Null
    try { Load-ConfigIntoGrid; Refresh-UiStatus } catch { }
}

function Update-CustomModuleCatalog([string]$ExePath, [string]$SiteUrl) {
    $mutex = $null; $acquired = $false
    try {
        $mutex = New-Object System.Threading.Mutex($false, $MutationMutexName)
        try { $acquired = $mutex.WaitOne(15000, $false) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
        if (-not $acquired) { throw 'Истекло время ожидания блокировки изменения custom rules.' }
        $catalog = Read-JsonFile $ModulesFile
        if (-not $catalog) { throw 'modules.json недоступен.' }
        Copy-Item -LiteralPath $ModulesFile -Destination $ModulesBackupFile -Force -ErrorAction SilentlyContinue

        $apps = @()
        if ($ExePath) {
            if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) { throw "EXE не найден: $ExePath" }
            if ([IO.Path]::GetExtension($ExePath) -ne '.exe') { throw 'Для правила «Свой EXE» выберите файл .exe.' }
            $apps = @([IO.Path]::GetFileName($ExePath), $ExePath) | Select-Object -Unique
        }
        $catalog.CustomExe.Applications = @($apps)

        if ($SiteUrl) {
            $value = $SiteUrl.Trim()
            if ($value -notmatch '^[a-zA-Z][a-zA-Z0-9+.-]*://') { $value = 'https://' + $value }
            $uri = New-Object System.Uri($value)
            if (@('http','https') -notcontains $uri.Scheme) { throw 'Для своего сайта поддерживаются только http/https.' }
            if (-not $uri.Host) { throw 'Не удалось определить имя сайта.' }
            $targets = @($uri.Host)
            if ($uri.Host -notmatch '^\d{1,3}(\.\d{1,3}){3}$' -and $uri.Host -notmatch ':') { $targets += "*.$($uri.Host)" }
            $catalog.CustomSite.Targets = @($targets | Select-Object -Unique)
            $catalog.CustomSite.HealthUrls = @($uri.AbsoluteUri)
        }
        else {
            $catalog.CustomSite.Targets = @()
            $catalog.CustomSite.HealthUrls = @('https://example.com/')
        }

        Write-TextAtomic -Path $ModulesFile -Text ($catalog | ConvertTo-Json -Depth 12)
        return $true
    }
    finally {
        if ($acquired -and $mutex) { try { $mutex.ReleaseMutex() } catch { } }
        if ($mutex) { try { $mutex.Dispose() } catch { } }
    }
}

function Test-CustomDefinitionsForConfig($Config) {
    $custom = Get-CustomSettings
    if ([string]$Config.CustomExe -ne 'DIRECT' -and -not $custom.CustomExePath) {
        [System.Windows.Forms.MessageBox]::Show('Для «Свой EXE» сначала выберите исполняемый файл на вкладке «Дополнительно».', 'VPS Control Center', 'OK', 'Warning') | Out-Null
        return $false
    }
    if ([string]$Config.CustomSite -ne 'DIRECT' -and -not $custom.CustomSiteUrl) {
        [System.Windows.Forms.MessageBox]::Show('Для «Свой сайт» сначала укажите адрес на вкладке «Дополнительно».', 'VPS Control Center', 'OK', 'Warning') | Out-Null
        return $false
    }
    return $true
}

function Get-HyperVAdapterChoices {
    $result = New-Object System.Collections.ArrayList
    try {
        foreach ($ip in @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.InterfaceAlias -like 'vEthernet*' -and $_.IPAddress -notlike '169.254.*' })) {
            [void]$result.Add([pscustomobject]@{ Alias=[string]$ip.InterfaceAlias; Address=[string]$ip.IPAddress; Display="$($ip.InterfaceAlias) — $($ip.IPAddress)" })
        }
    }
    catch { }
    return @($result)
}

function Invoke-VmGatewayChild([string]$Action, [string]$InterfaceAlias, [string]$ListenAddress, [int]$ListenPort, [int]$ConnectPort=(Get-V7RoutingTunnelPort), [switch]$Elevated) {
    if($Demo){ throw 'Демо-режим: Hyper-V gateway не изменяется.' }
    if (-not (Test-Path -LiteralPath $VmGatewayHelperPath)) { throw "Не найден helper VM gateway: $VmGatewayHelperPath" }
    $args = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$VmGatewayHelperPath`" -Action $Action -InterfaceAlias `"$InterfaceAlias`" -ListenAddress `"$ListenAddress`" -ListenPort $ListenPort -ConnectAddress `"127.0.0.1`" -ConnectPort $ConnectPort"
    if ($Elevated) {
        $p = Start-Process -FilePath $PowerShellExe -ArgumentList $args -Verb RunAs -Wait -PassThru
        return [pscustomobject]@{ ExitCode=$p.ExitCode; Output='' }
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmssfff'
    $out = Join-Path $UiTempDir "vm-gateway-$stamp.out.txt"
    $err = Join-Path $UiTempDir "vm-gateway-$stamp.err.txt"
    $p = Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
    $p.Refresh()
    return [pscustomobject]@{ ExitCode=$p.ExitCode; Output=((Read-TextFileSmart $out) + (Read-TextFileSmart $err)).Trim() }
}

function Get-EngineAutostartStatus {
    $taskName = 'VPS Control V6.3 - AutoStart'
    try {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if (-not $task) {
            return [pscustomobject]@{ Exists=$false; Enabled=$false; UsesV65=$false; Detail='Системный autostart движка не установлен (это необязательно).' }
        }
        $enabled = ([string]$task.State -ne 'Disabled')
        $actionText = (@($task.Actions | ForEach-Object { "$(($_.Execute + ' ' + $_.Arguments).Trim())" }) -join ' | ')
        $uses65 = ($actionText -match '(?i)VPS-Control-v6\.5\.ps1')
        if ($uses65) {
            $detail = if ($enabled) { 'Системный autostart: включён и уже использует V6.5.' } else { 'Системный autostart: настроен на V6.5, но отключён.' }
        }
        else {
            $detail = if ($enabled) { 'ВНИМАНИЕ: включён старый autostart. Перед reboot обновите его на V6.5.' } else { 'Найден старый, но отключённый autostart движка.' }
        }
        return [pscustomobject]@{ Exists=$true; Enabled=$enabled; UsesV65=$uses65; Detail=$detail }
    }
    catch {
        return [pscustomobject]@{ Exists=$false; Enabled=$false; UsesV65=$false; Detail="Не удалось проверить системный autostart: $($_.Exception.Message)" }
    }
}

function Invoke-EngineElevatedAction([string]$Action) {
    if($Demo){ throw 'Демо-режим: системные изменяющие операции отключены.' }
    if (-not (Test-Path -LiteralPath $EnginePath)) { throw "Расширенный движок недоступен: $EnginePath" }
    $args = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$EnginePath`" -Action $Action -NoAppLaunch"
    $p = Start-Process -FilePath $PowerShellExe -ArgumentList $args -Verb RunAs -Wait -PassThru
    $p.Refresh()
    return [int]$p.ExitCode
}

function Get-ConfigSnapshot {
    $cfg = Read-JsonFile $ConfigFile
    $h = [ordered]@{ Version = $EngineVersion }
    foreach ($module in $ModuleNames) {
        $fallback = if ($ModuleDefaultModes.ContainsKey($module)) { [string]$ModuleDefaultModes[$module] } else { 'DIRECT' }
        $value = $null
        if ($cfg -and $cfg.PSObject.Properties[$module]) { $value = [string]$cfg.$module }
        $h[$module] = Normalize-Mode $value $fallback
    }
    return [pscustomobject]$h
}



$script:EngineProcess = $null
$script:EngineOut = $null
$script:EngineErr = $null
$script:EngineAction = ''
$script:EngineStartedAt = $null
$script:RuntimeRecoveryAttempts = 0
$script:RuntimeRecoveryNextAt = [datetime]::MinValue
$script:RuntimeRecoveryAction = $false
$script:RuntimeRecoveryMaxBackoffSeconds = 300
$script:AllowExit = $false
$script:LoadingConfig = $false
$script:LastRuntime = $null
$script:LastConfig = $null
$script:AutoHistoryCache = $null
$script:LastObservationRefresh = [datetime]::MinValue
$script:LastEventsRefresh = [datetime]::MinValue
$script:LastOverallState = ''
$script:LastEffectiveSignature = ''
$script:Consistency = $null
$script:UiSettings = Get-UiSettings
$script:CustomSettings = Get-CustomSettings
$script:VmChoicesByDisplay = @{}
$script:SuppressSettingsEvents = $false

function Get-ActionUiName([string]$Action) {
    if ($ActionUiNames.ContainsKey($Action)) { return [string]$ActionUiNames[$Action] }
    return $Action
}

function Start-EngineAction([string]$Action) {
    if($Demo){
        try{
            $dr=Invoke-V7DemoAction -Action $Action -StateDir $StateDir -ModuleNames $ModuleNames
            Write-UiEvent 'DEMO' "Демо: $(Get-ActionUiName $Action)" $dr.Text
            try{$lblOperation.Text=$dr.Text;$lblOperation.ForeColor=[Drawing.Color]::DarkGreen}catch{}
            try{Refresh-UiStatus;Refresh-Observation;Refresh-Events}catch{}
            return $true
        }catch{[Windows.Forms.MessageBox]::Show("Ошибка демо-операции: $($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null;return $false}
    }
    if (-not (Test-Path -LiteralPath $EnginePath)) {
        [System.Windows.Forms.MessageBox]::Show(
            "Расширенный движок VPS-Control-v6.5.ps1 недоступен.`r`n`r`n$EnginePath",
            'VPS Control Center',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
        return $false
    }

    if (Test-UiOperationBusy) {
        [System.Windows.Forms.MessageBox]::Show('Уже выполняется операция Control Center. Дождитесь её завершения.', 'VPS Control Center', 'OK', 'Information') | Out-Null
        return $false
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmssfff'
    $script:EngineOut = Join-Path $UiTempDir "engine-$stamp.out.txt"
    $script:EngineErr = Join-Path $UiTempDir "engine-$stamp.err.txt"
    $args = "-NoProfile -ExecutionPolicy Bypass -File `"$EnginePath`" -Action $Action -NoAppLaunch"

    try {
        if($Action -in @('Apply','RestartTunnel')){
            Write-V7SocksTrace 'ENGINE_ACTION_PRE' ("action=$Action tempOut=$([IO.Path]::GetFileName($script:EngineOut)) tempErr=$([IO.Path]::GetFileName($script:EngineErr))")
            Write-V7SocksSnapshot ("before-$Action")
        }
        $script:EngineProcess = Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $script:EngineOut -RedirectStandardError $script:EngineErr
        $script:EngineAction = $Action
        $script:EngineStartedAt = Get-Date
        $script:LongOperationWarned = $false
        $lblOperation.Text = "Выполняется: $(Get-ActionUiName $Action)…"
        $lblOperation.ForeColor = [System.Drawing.Color]::DarkOrange
        Write-UiLog "Engine action START $Action pid=$($script:EngineProcess.Id)"
        if($Action -in @('Apply','RestartTunnel')){Write-V7SocksTrace 'ENGINE_ACTION_START' ("action=$Action pid=$($script:EngineProcess.Id)")}
        Update-UiBusyState
        return $true
    }
    catch {
        $script:EngineProcess = $null
        Write-UiLog "Engine action start failed: $Action :: $($_.Exception.Message)"
        [System.Windows.Forms.MessageBox]::Show(
            "Не удалось запустить операцию «$(Get-ActionUiName $Action)».`r`n`r`n$($_.Exception.Message)",
            'VPS Control Center',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
        Update-UiBusyState
        return $false
    }
 }

function Test-V7SavedRoutesNeedRuntime {
    try{
        $cfg=Get-ConfigSnapshot
        foreach($module in $ModuleNames){
            $mode='DIRECT'
            try{if($cfg -and $cfg.PSObject.Properties[$module]){$mode=Normalize-Mode ([string]$cfg.$module) 'DIRECT'}}catch{}
            if($mode -in @('AUTO','VPS')){return $true}
        }
    }catch{}
    return $false
}
function Get-V7RoutingTunnelSelection {
    $path=Join-Path $UiRuntimeDir 'tunnel-routing.json'
    $id='PRIMARY_AUTO'
    try{
        if(Test-Path -LiteralPath $path -PathType Leaf){
            $d=Read-JsonFile $path
            if($d -and [string]$d.SelectedTunnelId -in @('PRIMARY_AUTO','RESERVE_MANUAL')){$id=[string]$d.SelectedTunnelId}
        }
    }catch{}
    return $id
}
function Get-V7RoutingTunnelPort {
    return $(if((Get-V7RoutingTunnelSelection) -eq 'RESERVE_MANUAL'){1080}else{1081})
}
function Invoke-V7TunnelManagerSync(
    [ValidateSet('Status','StartReserve','StopReserve','TestReserve','SelectPrimaryRoute','SelectReserveRoute')]
    [string]$TunnelAction
){
    if($Demo){return [pscustomobject]@{ExitCode=0;Output='DEMO'}}
    $stamp=Get-Date -Format 'yyyyMMdd-HHmmssfff'
    $o=Join-Path $UiTempDir "tunnel-manager-$stamp.out.txt"
    $e=Join-Path $UiTempDir "tunnel-manager-$stamp.err.txt"
    $args='-NoProfile -ExecutionPolicy Bypass -File "'+$TunnelManagerPath+'" -Action '+$TunnelAction+' -SourceRoot "'+$PSScriptRoot+'"'
    $proc=Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $o -RedirectStandardError $e
    $proc.Refresh()
    $text=((Read-TextFileSmart $o)+"`r`n"+(Read-TextFileSmart $e)).Trim()
    Remove-Item $o,$e -Force -ErrorAction SilentlyContinue
    return [pscustomobject]@{ExitCode=[int]$proc.ExitCode;Output=$text}
}

function Start-V7TunnelManagerAction([ValidateSet('Status','StartReserve','StopReserve','TestReserve','SelectPrimaryRoute','SelectReserveRoute')][string]$TunnelAction){
    try{
        $args='-NoProfile -ExecutionPolicy Bypass -File "'+$TunnelManagerPath+'" -Action '+$TunnelAction+' -SourceRoot "'+$PSScriptRoot+'"'
        $proc=Start-Process -FilePath $PowerShellExe -ArgumentList $args -WindowStyle Hidden -PassThru
        Write-UiLog "Tunnel manager START action=$TunnelAction pid=$($proc.Id)"
        try{$proc.Dispose()}catch{}
        return $true
    }catch{
        Write-UiLog "Tunnel manager FAIL action=$TunnelAction error=$($_.Exception.Message)"
        return $false
    }
}
function Get-V7TunnelManagerStatus {
    $path=Join-Path $UiRuntimeDir 'tunnel-status.json'
    return Read-JsonFile $path
}

function Get-V7RuntimeRecoveryHealth {
    $socksUp=Test-TcpListener $VccSocksHost $VccSocksPort 250
    $watch=Get-WatchdogUiStatus
    $watchRunning=($watch -and [string]$watch.State -eq 'RUNNING' -and [bool]$watch.Fresh)
    return [pscustomobject]@{Socks=[bool]$socksUp;Watchdog=[bool]$watchRunning;WatchdogState=$(if($watch){[string]$watch.State}else{'UNKNOWN'});WatchdogDetail=$(if($watch){[string]$watch.Detail}else{''})}
}
function Reset-V7RuntimeRecovery {
    $script:RuntimeRecoveryAttempts=0
    $script:RuntimeRecoveryNextAt=[datetime]::MinValue
}
function Schedule-V7RuntimeRecovery([string]$Reason){
    $script:RuntimeRecoveryAttempts++
    $delays=@(30,60,120,300)
    $idx=[Math]::Min([Math]::Max($script:RuntimeRecoveryAttempts-1,0),$delays.Count-1)
    $delay=[Math]::Min([int]$delays[$idx],[int]$script:RuntimeRecoveryMaxBackoffSeconds)
    $script:RuntimeRecoveryNextAt=(Get-Date).AddSeconds($delay)
    Write-UiLog "RUNTIME_RECOVERY retry scheduled in ${delay}s attempt=$($script:RuntimeRecoveryAttempts) reason=$Reason"
    Write-V7SocksTrace 'RECOVERY_SCHEDULE' ("delay=${delay}s attempt=$($script:RuntimeRecoveryAttempts) reason=$Reason")
    Write-UiEvent 'RECOVERY' 'Повтор восстановления runtime запланирован' "через ${delay}с; попытка=$($script:RuntimeRecoveryAttempts); $Reason" 'WARN'
}
function Get-V7SavedRouteModeSummary {
    try {
        $cfg=Get-ConfigSnapshot
        $parts=New-Object Collections.ArrayList
        foreach($module in $ModuleNames){
            $mode='DIRECT'
            try{if($cfg -and $cfg.PSObject.Properties[$module]){$mode=Normalize-Mode ([string]$cfg.$module) 'DIRECT'}}catch{}
            [void]$parts.Add("$module=$mode")
        }
        return (@($parts)-join ',')
    } catch { return ('ERROR='+$_.Exception.Message) }
}
function Invoke-V7RuntimeRecoveryIfNeeded([switch]$Startup){
    $busy=Test-UiOperationBusy
    $needs=Test-V7SavedRoutesNeedRuntime
    $modeSummary=Get-V7SavedRouteModeSummary
    $nextText=if($script:RuntimeRecoveryNextAt -gt [datetime]::MinValue){$script:RuntimeRecoveryNextAt.ToString('o')}else{'MIN'}
    Write-V7SocksTrace 'RECOVERY_EVAL' ("startup=$Startup demo=$([bool]$Demo) busy=$busy needsRuntime=$needs attempts=$($script:RuntimeRecoveryAttempts) nextAt=$nextText modes=$modeSummary")
    if($Demo){Write-V7SocksTrace 'RECOVERY_SKIP' 'reason=DEMO';return}
    if(-not $needs){Write-V7SocksTrace 'RECOVERY_SKIP' 'reason=NO_AUTO_OR_VPS';Reset-V7RuntimeRecovery;return}
    if($script:RuntimeRecoveryAction){Write-V7SocksTrace 'RECOVERY_SKIP' ("reason=RECOVERY_IN_FLIGHT action=$([string]$script:EngineAction)");return}
    if($busy){Write-V7SocksTrace 'RECOVERY_SKIP' ("reason=UI_OPERATION_BUSY action=$([string]$script:EngineAction)");return}
    $h=Get-V7RuntimeRecoveryHealth
    Write-V7SocksTrace 'RECOVERY_HEALTH' ("socks=$($h.Socks) watchdog=$($h.Watchdog) watchdogState=$($h.WatchdogState) detail=$($h.WatchdogDetail)")
    if($h.Socks -and $h.Watchdog){Write-V7SocksTrace 'RECOVERY_SKIP' 'reason=ALREADY_HEALTHY';Reset-V7RuntimeRecovery;return}
    if(-not $Startup -and (Get-Date) -lt $script:RuntimeRecoveryNextAt){Write-V7SocksTrace 'RECOVERY_SKIP' ("reason=BACKOFF nextAt=$nextText");return}
    Write-UiLog "RUNTIME_RECOVERY Apply: startup=$Startup socks=$($h.Socks) watchdog=$($h.WatchdogState) attempt=$($script:RuntimeRecoveryAttempts)"
    Write-V7SocksTrace 'RECOVERY_TRIGGER' ("startup=$Startup socks=$($h.Socks) watchdog=$($h.WatchdogState) watchdogDetail=$($h.WatchdogDetail) attempt=$($script:RuntimeRecoveryAttempts)")
    Write-V7SocksSnapshot 'recovery-trigger'
    Write-UiEvent 'RECOVERY' 'Восстановление сохранённой маршрутизации' "startup=$Startup; SOCKS=$($h.Socks); watchdog=$($h.WatchdogState); используется сохранённая конфигурация" 'WARN'
    $lblOperation.Text='Восстановление SOCKS/watchdog по сохранённой конфигурации…'
    $lblOperation.ForeColor=[Drawing.Color]::DarkOrange
    $script:RuntimeRecoveryAction=$true
    if(-not(Start-EngineAction 'Apply')){
        $script:RuntimeRecoveryAction=$false
        Schedule-V7RuntimeRecovery 'не удалось запустить Apply'
    }
}
function Complete-EngineActionIfNeeded {
    if (-not $script:EngineProcess) { return }
    try { if (-not $script:EngineProcess.HasExited) { return } }
    catch { return }

    $exitCode = $null
    try {
        $script:EngineProcess.WaitForExit()
        $script:EngineProcess.Refresh()
        $exitCode = [int]$script:EngineProcess.ExitCode
    }
    catch { Write-UiLog "ExitCode read failed for $($script:EngineAction): $($_.Exception.Message)" }

    $text = ''
    try {
        if (Test-Path -LiteralPath $script:EngineOut) { $text += (Read-TextFileSmart $script:EngineOut) }
        if (Test-Path -LiteralPath $script:EngineErr) {
            $errText = Read-TextFileSmart $script:EngineErr
            if ($errText) { $text += "`r`n[ОШИБКИ ПРОЦЕССА]`r`n$errText" }
        }
    }
    catch { }

    $durationMs = 0
    if ($script:EngineStartedAt) { try { $durationMs = [int]((Get-Date) - $script:EngineStartedAt).TotalMilliseconds } catch { } }

    if($script:EngineAction -in @('Apply','RestartTunnel')){
        Write-V7SocksTrace 'ENGINE_ACTION_OUTPUT' ("action=$($script:EngineAction) rc=$(if($null -ne $exitCode){$exitCode}else{'UNKNOWN'}) durationMs=$durationMs")
        if($text){ Write-V7SocksMultiline 'ENGINE_STDOUT_STDERR' $text }
        Write-V7SocksSnapshot ("after-$($script:EngineAction)")
    }

    if ($text) {
        $txtOutput.Text = $text
        $txtOutput.SelectionStart = 0
        $txtOutput.SelectionLength = 0
        $txtOutput.ScrollToCaret()
    }

    $uiAction = Get-ActionUiName $script:EngineAction
    $logicalFailure = ($script:EngineAction -in @('Apply','RestartTunnel') -and $text -match '(?im)^\s*\[FAIL\]')
    $success = ($null -ne $exitCode -and $exitCode -eq 0 -and -not $logicalFailure)
    if($logicalFailure){Write-V7SocksTrace 'ENGINE_LOGICAL_FAILURE' ("action=$($script:EngineAction); nativeRc=$(if($null -ne $exitCode){$exitCode}else{'UNKNOWN'}); reason=engine-output-contained-FAIL")}
    if($logicalFailure){try{Invoke-V7AutoIncidentCapture -Reason ("engine-logical-failure action=$($script:EngineAction) nativeRc=$(if($null -ne $exitCode){$exitCode}else{'UNKNOWN'})")|Out-Null}catch{}}
    try{Write-V7OperationEvidence -Component 'Engine' -Action ([string]$script:EngineAction) -ExitCode $(if($null -ne $exitCode){[int]$exitCode}else{-999}) -DurationMs $durationMs -Text $text -Meta ("logicalFailure=$logicalFailure; runtimeRecovery=$([bool]$script:RuntimeRecoveryAction)") }catch{}
    $wasRuntimeRecovery = [bool]$script:RuntimeRecoveryAction

    if ($null -ne $exitCode) {
        Write-UiLog "Engine action END $($script:EngineAction) rc=$exitCode durationMs=$durationMs"
        if ($success) {
            $lblOperation.Text = "Готово: $uiAction"
            $lblOperation.ForeColor = [System.Drawing.Color]::DarkGreen
        }
        else {
            $suffix=if($logicalFailure -and $exitCode -eq 0){'движок сообщил [FAIL] при native rc=0'}else{"код $exitCode"}
            $lblOperation.Text = "Ошибка: $uiAction ($suffix)"
            $lblOperation.ForeColor = [System.Drawing.Color]::DarkRed
        }
    }
    else {
        Write-UiLog "Engine action END $($script:EngineAction) rc=UNKNOWN durationMs=$durationMs"
        $lblOperation.Text = "Операция завершена, код возврата недоступен: $uiAction"
        $lblOperation.ForeColor = [System.Drawing.Color]::DarkOrange
    }

    if ($script:EngineAction -eq 'Apply' -and $script:PendingVpsSwitch) {
        if ($success) {
            Write-UiLog "VPS switch COMMIT new=$($script:PendingVpsSwitch.NewId) previous=$($script:PendingVpsSwitch.PreviousId)"
            $script:PendingVpsSwitch = $null
        }
        else {
            $oldId = [string]$script:PendingVpsSwitch.PreviousId
            $newId = [string]$script:PendingVpsSwitch.NewId
            try {
                Restore-ActiveVpsProfile $oldId
                Write-UiLog "VPS switch ROLLBACK metadata new=$newId -> previous=$oldId after failed Apply."
                $lblOperation.Text += ' · активный профиль VPS возвращён к предыдущему.'
            }
            catch { Write-UiLog "VPS switch metadata rollback failed: $($_.Exception.Message)" }
            $script:PendingVpsSwitch = $null
        }
    }

    if($wasRuntimeRecovery){
        $script:RuntimeRecoveryAction=$false
        $rh=Get-V7RuntimeRecoveryHealth
        if($success -and $rh.Socks -and $rh.Watchdog){
            Write-UiLog 'RUNTIME_RECOVERY PASS: SOCKS and watchdog healthy.'
            Write-UiEvent 'RECOVERY' 'Runtime восстановлен' 'SOCKS и watchdog подтверждены после Apply' 'INFO'
            Reset-V7RuntimeRecovery
        }else{
            $reason="Apply rc=$(if($null -ne $exitCode){$exitCode}else{'UNKNOWN'}); SOCKS=$($rh.Socks); watchdog=$($rh.WatchdogState)"
            Schedule-V7RuntimeRecovery $reason
        }
    }elseif($script:EngineAction -in @('Apply','RestartTunnel')){
        $rh=Get-V7RuntimeRecoveryHealth
        if($rh.Socks -and $rh.Watchdog){Reset-V7RuntimeRecovery}
    }

    Remove-Item -LiteralPath $script:EngineOut -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $script:EngineErr -Force -ErrorAction SilentlyContinue
    try { $script:EngineProcess.Dispose() } catch { }
    $script:EngineProcess = $null
    $script:EngineAction = ''
    $script:EngineStartedAt = $null
    $script:LongOperationWarned = $false
    Update-UiBusyState
    Refresh-UiStatus
    Refresh-Observation
    try { Refresh-VpsProfileList (Get-SelectedVpsProfileId) } catch { }
}

# --------------------------------------------------------------------------
# Single instance
# --------------------------------------------------------------------------
$uiMutex = New-Object System.Threading.Mutex($false, $UiMutexName)
$uiAcquired = $false
try {
    try { $uiAcquired = $uiMutex.WaitOne(0, $false) }
    catch [System.Threading.AbandonedMutexException] { $uiAcquired = $true }

    if (-not $uiAcquired) {
        [System.Windows.Forms.MessageBox]::Show(
            'VPS Control Center V7 уже запущен. Проверьте область уведомлений Windows.',
            'VPS Control Center',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
        return
    }

    Cleanup-UiTempFiles
    $integrity = Test-PackageIntegrity -BaseDir $PSScriptRoot
    if (-not $integrity.Ok) {
        $detail = (@($integrity.Errors) -join "`r`n - ")
        [System.Windows.Forms.MessageBox]::Show("Пакет V7 не прошёл стартовую проверку целостности.`r`n`r`n - $detail`r`n`r`nV6.3.1 не изменён; запуск V7 остановлен fail-closed.", 'VPS Control Center', 'OK', 'Error') | Out-Null
        return
    }
    foreach ($warning in @($integrity.Warnings)) { Write-UiLog "STARTUP WARNING: $warning" }
    try {
        $script:Consistency = Test-V7FunctionalConsistency -BaseDir $PSScriptRoot -UiVersion $UiVersion -ModuleNames $ModuleNames
        if(-not $script:Consistency.Ok){
            $detail=(@($script:Consistency.Errors) -join "`r`n - " )
            [System.Windows.Forms.MessageBox]::Show("VPS Control Center $UiVersion обнаружил разрыв между заявленным и реализованным функционалом.`r`n`r`n - $detail`r`n`r`nЗапуск остановлен fail-closed.",'VPS Control Center','OK','Error')|Out-Null
            return
        }
        foreach($warning in @($script:Consistency.Warnings)){Write-UiLog "CONSISTENCY WARNING: $warning"}
    } catch {
        [System.Windows.Forms.MessageBox]::Show("Не удалось выполнить стартовую проверку связанности RC14.12.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null
        return
    }
    if($Demo){ try{Initialize-V7DemoEvidence -StateDir $StateDir -ModuleNames $ModuleNames -Defaults $ModuleDefaultModes;if(Test-Path -LiteralPath $BundledModulesFile){Copy-Item -LiteralPath $BundledModulesFile -Destination $ModulesFile -Force}; Write-UiEvent 'DEMO' 'Запущен демонстрационный режим' 'Никакие сетевые mutation-операции не выполняются.'}catch{[Windows.Forms.MessageBox]::Show("Не удалось подготовить демо-данные.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null;return} }
    try { [void](Initialize-VpsProfileStore) } catch { [System.Windows.Forms.MessageBox]::Show("Не удалось подготовить хранилище профилей VPS.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', 'OK', 'Error') | Out-Null; return }
    if (-not (Ensure-ExtendedEngine)) { return }
    try { [void](Merge-ExtendedModuleCatalog) }
    catch {
        [System.Windows.Forms.MessageBox]::Show("Не удалось подготовить расширенный каталог маршрутов.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', 'OK', 'Error') | Out-Null
        return
    }

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "VPS Control Center v$UiVersion$(if($Demo){' · ДЕМО'}else{''})"
    $form.StartPosition = 'CenterScreen'
    $form.Size = New-Object System.Drawing.Size(1200, 820)
    $form.MinimumSize = New-Object System.Drawing.Size(1040, 720)
    $form.Font = New-Object System.Drawing.Font('Segoe UI', 9)
    $form.Icon = [System.Drawing.SystemIcons]::Shield
    $form.BackColor = [System.Drawing.Color]::WhiteSmoke
    $form.AutoScaleMode = 'Dpi'

    $toolTip = New-Object System.Windows.Forms.ToolTip
    $toolTip.AutoPopDelay = 16000
    $toolTip.InitialDelay = 350
    $toolTip.ReshowDelay = 100
    $toolTip.ShowAlways = $true

    $top = New-Object System.Windows.Forms.Panel
    $top.Dock = 'Top'
    $top.Height = 92
    $top.Padding = New-Object System.Windows.Forms.Padding(18, 10, 18, 8)
    $top.BackColor = [System.Drawing.Color]::White
    $form.Controls.Add($top)

    $lblTitle = New-Object System.Windows.Forms.Label
    $lblTitle.Text = 'VPS CONTROL CENTER'
    $lblTitle.AutoSize = $true
    $lblTitle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 16)
    $lblTitle.Location = New-Object System.Drawing.Point(18, 10)
    $top.Controls.Add($lblTitle)

    $lblSubtitle = New-Object System.Windows.Forms.Label
    $lblSubtitle.Text = if($Demo){"ДЕМО-СИМУЛЯЦИЯ · синтетические данные · Windows/VPS/Keenetic не изменяются"}else{"Интерфейс V7 · движок маршрутизации V$EngineVersion · весь прочий трафик Windows остаётся напрямую"}
    $lblSubtitle.AutoSize = $true
    $lblSubtitle.ForeColor = [System.Drawing.Color]::DimGray
    $lblSubtitle.Location = New-Object System.Drawing.Point(20, 42)
    $top.Controls.Add($lblSubtitle)

    $lblActiveVpsTop = New-Object System.Windows.Forms.Label
    $lblActiveVpsTop.Text = 'Активный VPS: —'
    $lblActiveVpsTop.ForeColor = [System.Drawing.Color]::DimGray
    $lblActiveVpsTop.Location = New-Object System.Drawing.Point(20, 66)
    $lblActiveVpsTop.Size = New-Object System.Drawing.Size(500, 18)
    $top.Controls.Add($lblActiveVpsTop)

    $lblOverall = New-Object System.Windows.Forms.Label
    $lblOverall.Text = 'ЗАГРУЗКА'
    $lblOverall.TextAlign = 'MiddleCenter'
    $lblOverall.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 11)
    $lblOverall.Size = New-Object System.Drawing.Size(185, 38)
    $lblOverall.Anchor = 'Top,Right'
    $lblOverall.Location = New-Object System.Drawing.Point(($form.ClientSize.Width - 208), 14)
    $lblOverall.BorderStyle = 'FixedSingle'
    $top.Controls.Add($lblOverall)

    $lblUpdated = New-Object System.Windows.Forms.Label
    $lblUpdated.Text = ''
    $lblUpdated.ForeColor = [System.Drawing.Color]::DimGray
    $lblUpdated.Anchor = 'Top,Right'
    $lblUpdated.TextAlign = 'MiddleRight'
    $lblUpdated.Location = New-Object System.Drawing.Point(($form.ClientSize.Width - 510), 56)
    $lblUpdated.Size = New-Object System.Drawing.Size(487, 20)
    $top.Controls.Add($lblUpdated)

    $tabs = New-Object System.Windows.Forms.TabControl
    $tabs.Dock = 'None'
    $tabs.Location = New-Object System.Drawing.Point(0, 92)
    $tabs.Size = New-Object System.Drawing.Size($form.ClientSize.Width, ($form.ClientSize.Height - 92))
    $tabs.Anchor = 'Top,Bottom,Left,Right'
    $tabs.Font = New-Object System.Drawing.Font('Segoe UI', 9.5)
    $form.Controls.Add($tabs)

    $tabMain = New-Object System.Windows.Forms.TabPage
    $tabMain.Text = 'Статус'
    $tabMain.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabMain)

    $tabObs = New-Object System.Windows.Forms.TabPage
    $tabObs.Text = 'Наблюдение'
    $tabObs.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabObs)

    $tabEvents = New-Object System.Windows.Forms.TabPage
    $tabEvents.Text = 'События'
    $tabEvents.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabEvents)

    $tabDiag = New-Object System.Windows.Forms.TabPage
    $tabDiag.Text = 'Диагностика'
    $tabDiag.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabDiag)

    $tabExtend = New-Object System.Windows.Forms.TabPage
    $tabExtend.Text = 'Дополнительно'
    $tabExtend.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabExtend)

    $tabVps = New-Object System.Windows.Forms.TabPage
    $tabVps.Text = 'VPS-серверы'
    $tabVps.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabVps)

    $tabTunnels = New-Object System.Windows.Forms.TabPage
    $tabTunnels.Text = 'Туннели'
    $tabTunnels.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabTunnels)

    $tabKeenetic = New-Object System.Windows.Forms.TabPage
    $tabKeenetic.Text = 'Keenetic'
    $tabKeenetic.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabKeenetic)

    $tabSettings = New-Object System.Windows.Forms.TabPage
    $tabSettings.Text = 'Настройки'
    $tabSettings.BackColor = [System.Drawing.Color]::WhiteSmoke
    [void]$tabs.TabPages.Add($tabSettings)

    # MAIN -----------------------------------------------------------------
    $mainLayout = New-Object System.Windows.Forms.TableLayoutPanel
    $mainLayout.Dock = 'Fill'
    $mainLayout.RowCount = 2
    $mainLayout.ColumnCount = 1
    [void]$mainLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 112)))
    [void]$mainLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    [void]$mainLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    $tabMain.Controls.Add($mainLayout)

    $mainCards = New-Object System.Windows.Forms.FlowLayoutPanel
    $mainCards.Dock = 'Fill'
    $mainCards.Padding = New-Object System.Windows.Forms.Padding(14, 14, 6, 8)
    $mainCards.WrapContents = $false
    $mainCards.AutoScroll = $true
    $mainCards.BackColor = [System.Drawing.Color]::WhiteSmoke
    $mainLayout.Controls.Add($mainCards, 0, 0)

    $cardSocks = New-StatusCard 'SOCKS 1081 · основной AUTO'
    $cardReserveSocks = New-StatusCard 'SOCKS 1080 · резерв ручной'
    $cardProxifier = New-StatusCard 'Proxifier'
    $cardWatchdog = New-StatusCard 'Фоновый контроллер'
    $cardLkg = New-StatusCard 'Резервный профиль'
    $cardSelfTest = New-StatusCard 'Последняя самопроверка'
    $cardVpsUse = New-StatusCard 'Использование VPS'
    $cardFreshness = New-StatusCard 'Свежесть данных'
    $cardConsistency = New-StatusCard 'Связанность функций'
    foreach ($c in @($cardSocks,$cardReserveSocks,$cardProxifier,$cardWatchdog,$cardLkg,$cardSelfTest,$cardVpsUse,$cardFreshness,$cardConsistency)) { [void]$mainCards.Controls.Add($c.Panel) }

    $toolTip.SetToolTip($cardSocks.Panel, 'PRIMARY_AUTO: VCC SOCKS5 127.0.0.1:1081. Автоматический start/recovery/watchdog разрешены.')
    $toolTip.SetToolTip($cardReserveSocks.Panel, 'RESERVE_MANUAL: SOCKS5 127.0.0.1:1080. Полностью видим и диагностируется, но start/stop/recovery только по вашей ручной команде.')
    $toolTip.SetToolTip($cardProxifier.Panel, 'Proxifier применяет правила только к выбранным сервисам. Неподходящий под правила трафик остаётся DIRECT.')
    $toolTip.SetToolTip($cardWatchdog.Panel, 'Фоновый контроллер регулярно проверяет автоматические маршруты, выполняет failover/failback и обновляет heartbeat.')
    $toolTip.SetToolTip($cardLkg.Panel, 'Последний проверенный профиль Proxifier. Расширенный движок V6.5 сохраняет LKG-механику V6.3.1 для безопасного отката профиля.')
    $toolTip.SetToolTip($cardSelfTest.Panel, 'Последняя самопроверка только для чтения. Она ничего не записывает в GitHub и не меняет маршруты.')
    $toolTip.SetToolTip($cardVpsUse.Panel, 'Показывает, сколько управляемых сервисов сейчас реально используют VPS. Цель — держать это число минимально необходимым.')
    $toolTip.SetToolTip($cardFreshness.Panel, 'Показывает возраст runtime-state.json. Если данные давно не обновлялись, интерфейс не должен выдавать старое состояние за текущее.')
    $toolTip.SetToolTip($cardConsistency.Panel, 'Проверяет связность заявленных возможностей, UI-действий, helper actions, модулей, manifest и текущей документации RC14.12.')

    $mainBody = New-Object System.Windows.Forms.Panel
    $mainBody.Dock = 'Fill'
    $mainBody.Padding = New-Object System.Windows.Forms.Padding(14, 4, 14, 12)
    $mainBody.AutoScroll = $true
    $mainLayout.Controls.Add($mainBody, 0, 1)

    $lblRoutesTitle = New-Object System.Windows.Forms.Label
    $lblRoutesTitle.Text = 'Маршрутизация сервисов'
    $lblRoutesTitle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 12)
    $lblRoutesTitle.Location = New-Object System.Drawing.Point(16, 10)
    $lblRoutesTitle.AutoSize = $true
    $mainBody.Controls.Add($lblRoutesTitle)

    $lblRoutesHint = New-Object System.Windows.Forms.Label
    $lblRoutesHint.Text = 'Режим «Авто» предпочитает прямой маршрут и использует VPS только при необходимости или устойчивом выигрыше.'
    $lblRoutesHint.ForeColor = [System.Drawing.Color]::DimGray
    $lblRoutesHint.Location = New-Object System.Drawing.Point(16, 36)
    $lblRoutesHint.Size = New-Object System.Drawing.Size(760, 22)
    $mainBody.Controls.Add($lblRoutesHint)

    $lblHealthTree = New-Object System.Windows.Forms.Label
    $lblHealthTree.Text = 'Status Center: фактическое состояние ещё не прочитано.'
    $lblHealthTree.Location = New-Object System.Drawing.Point(16, 60)
    $lblHealthTree.Size = New-Object System.Drawing.Size(($form.ClientSize.Width - 58), 48)
    $lblHealthTree.Anchor = 'Top,Left,Right'
    $lblHealthTree.BorderStyle = 'FixedSingle'
    $lblHealthTree.Padding = New-Object System.Windows.Forms.Padding(8, 8, 8, 6)
    $lblHealthTree.ForeColor = [System.Drawing.Color]::DimGray
    $mainBody.Controls.Add($lblHealthTree)
    $toolTip.SetToolTip($lblHealthTree, 'Единая read-only сводка: локальный контур, маршрутизация, зависимости VPS, свежесть runtime, хранилище V7 и последний Keenetic inventory. Keenetic не влияет на состояние Windows-маршрутизации.')

    $lblConfigState = New-Object System.Windows.Forms.Label
    $lblConfigState.Text = 'Настройки сохранены'
    $lblConfigState.TextAlign = 'MiddleRight'
    $lblConfigState.ForeColor = [System.Drawing.Color]::DarkGreen
    $lblConfigState.Anchor = 'Top,Right'
    $lblConfigState.Location = New-Object System.Drawing.Point(($form.ClientSize.Width - 310), 32)
    $lblConfigState.Size = New-Object System.Drawing.Size(265, 24)
    $mainBody.Controls.Add($lblConfigState)

    $gridRoutes = New-Object System.Windows.Forms.DataGridView
    $gridRoutes.Location = New-Object System.Drawing.Point(16, 116)
    $gridRoutes.Size = New-Object System.Drawing.Size(($form.ClientSize.Width - 58), 517)
    $gridRoutes.Anchor = 'Top,Left,Right'
    $gridRoutes.AllowUserToAddRows = $false
    $gridRoutes.AllowUserToDeleteRows = $false
    $gridRoutes.AllowUserToResizeRows = $false
    $gridRoutes.RowHeadersVisible = $false
    $gridRoutes.AutoGenerateColumns = $false
    $gridRoutes.SelectionMode = 'FullRowSelect'
    $gridRoutes.MultiSelect = $false
    $gridRoutes.BackgroundColor = [System.Drawing.Color]::White
    $gridRoutes.BorderStyle = 'FixedSingle'
    $gridRoutes.CellBorderStyle = 'SingleHorizontal'
    $gridRoutes.GridColor = [System.Drawing.Color]::Gainsboro
    $gridRoutes.ColumnHeadersHeight = 36
    $gridRoutes.RowTemplate.Height = 44
    $gridRoutes.EnableHeadersVisualStyles = $false
    $gridRoutes.ColumnHeadersDefaultCellStyle.BackColor = [System.Drawing.Color]::WhiteSmoke
    $gridRoutes.ColumnHeadersDefaultCellStyle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 9)
    $gridRoutes.DefaultCellStyle.SelectionBackColor = [System.Drawing.Color]::AliceBlue
    $gridRoutes.DefaultCellStyle.SelectionForeColor = [System.Drawing.Color]::Black
    $gridRoutes.AlternatingRowsDefaultCellStyle.BackColor = [System.Drawing.Color]::FromArgb(250,250,250)
    $gridRoutes.EditMode = 'EditOnEnter'

    $cService = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
    $cService.Name = 'Сервис'
    $cService.HeaderText = 'Сервис'
    $cService.Width = 150
    $cService.ReadOnly = $true
    [void]$gridRoutes.Columns.Add($cService)

    $cMode = New-Object System.Windows.Forms.DataGridViewComboBoxColumn
    $cMode.Name = 'Режим'
    $cMode.HeaderText = 'Режим'
    $cMode.Width = 150
    [void]$cMode.Items.Add('Напрямую')
    [void]$cMode.Items.Add('Авто')
    [void]$cMode.Items.Add('Через VPS')
    [void]$gridRoutes.Columns.Add($cMode)

    $cEffective = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
    $cEffective.Name = 'Сейчас'
    $cEffective.HeaderText = 'Сейчас'
    $cEffective.Width = 125
    $cEffective.ReadOnly = $true
    [void]$gridRoutes.Columns.Add($cEffective)

    $cHealth = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
    $cHealth.Name = 'Состояние'
    $cHealth.HeaderText = 'Состояние'
    $cHealth.Width = 120
    $cHealth.ReadOnly = $true
    [void]$gridRoutes.Columns.Add($cHealth)

    $cLatency = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
    $cLatency.Name = 'Задержка'
    $cLatency.HeaderText = 'Задержка'
    $cLatency.Width = 100
    $cLatency.ReadOnly = $true
    [void]$gridRoutes.Columns.Add($cLatency)

    $cWhy = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
    $cWhy.Name = 'Почему'
    $cWhy.HeaderText = 'Почему выбран этот маршрут'
    $cWhy.AutoSizeMode = 'Fill'
    $cWhy.MinimumWidth = 300
    $cWhy.ReadOnly = $true
    [void]$gridRoutes.Columns.Add($cWhy)

    foreach ($module in $ModuleNames) {
        $index = $gridRoutes.Rows.Add()
        $row = $gridRoutes.Rows[$index]
        $row.Tag = $module
        $row.Cells['Сервис'].Value = Get-ModuleUiName $module
        $row.Cells['Режим'].Value = 'Напрямую'
        $row.Cells['Сейчас'].Value = '—'
        $row.Cells['Состояние'].Value = 'Неизвестно'
        $row.Cells['Задержка'].Value = '—'
        $row.Cells['Почему'].Value = '—'
    }
    $mainBody.Controls.Add($gridRoutes)

    $actions = New-Object System.Windows.Forms.FlowLayoutPanel
    $actions.Location = New-Object System.Drawing.Point(16, 646)
    $actions.Size = New-Object System.Drawing.Size(($form.ClientSize.Width - 58), 82)
    $actions.Anchor = 'Top,Left,Right'
    $actions.WrapContents = $true
    $actions.AutoScroll = $false
    $mainBody.Controls.Add($actions)

    $btnSave = New-FlatButton 'Сохранить без применения' 185 34
    $btnSaveApply = New-FlatButton 'Сохранить и применить' 185 34
    $btnSaveApply.BackColor = [System.Drawing.Color]::FromArgb(0,120,215)
    $btnSaveApply.ForeColor = [System.Drawing.Color]::White
    $btnReload = New-FlatButton 'Обновить статус' 145 34
    $btnReloadConfig = New-FlatButton 'Перечитать настройки' 165 34
    $btnApply = New-FlatButton 'Применить сохранённое' 175 34
    $btnDirect = New-FlatButton 'Временно всё напрямую' 175 34
    $btnRestart = New-FlatButton 'Перезапустить SOCKS 1081' 195 34
    $btnCopySnapshot = New-FlatButton 'Копировать снимок' 165 34
    foreach ($b in @($btnSave,$btnSaveApply,$btnReload,$btnReloadConfig,$btnApply,$btnDirect,$btnRestart,$btnCopySnapshot)) { [void]$actions.Controls.Add($b) }

    $toolTip.SetToolTip($btnSave, 'Только сохраняет выбранные режимы в routing-config.json. Фактическая маршрутизация не меняется, пока вы явно не примените конфигурацию.')
    $toolTip.SetToolTip($btnSaveApply, 'Сохраняет режимы и передаёт применение расширенному движку V6.5, созданному из V6.3.1.')
    $toolTip.SetToolTip($btnReload, 'Обновляет только фактический статус/runtime и наблюдение. Несохранённые изменения режимов в таблице не стираются.')
    $toolTip.SetToolTip($btnReloadConfig, 'Заново читает сохранённый routing-config.json. Если в таблице есть несохранённые изменения, V7 сначала спросит подтверждение.')
    $toolTip.SetToolTip($btnApply, 'Применяет уже сохранённую конфигурацию. Временный общий DIRECT override будет снят.')
    $toolTip.SetToolTip($btnDirect, 'Временно переводит управляемые сервисы на прямой маршрут. Сохранённые режимы не стираются.')
    $toolTip.SetToolTip($btnRestart, 'Перезапускает только VCC SOCKS 127.0.0.1:1081 через движок V6.5.')
    $toolTip.SetToolTip($btnCopySnapshot, 'Копирует в буфер обмена безопасный снимок текущего состояния без паролей, токенов и содержимого профилей. Удобно для диагностики и передачи в чат.')

    $lblOperation = New-Object System.Windows.Forms.Label
    $lblOperation.Text = 'Готово к работе'
    $lblOperation.Location = New-Object System.Drawing.Point(18, 738)
    $lblOperation.Size = New-Object System.Drawing.Size(($form.ClientSize.Width - 90), 24)
    $lblOperation.Anchor = 'Top,Left,Right'
    $lblOperation.ForeColor = [System.Drawing.Color]::DimGray
    $mainBody.Controls.Add($lblOperation)

    $busyProgress = New-Object System.Windows.Forms.ProgressBar
    $busyProgress.Location = New-Object System.Drawing.Point(($form.ClientSize.Width - 230), 739)
    $busyProgress.Size = New-Object System.Drawing.Size(185, 16)
    $busyProgress.Anchor = 'Top,Right'
    $busyProgress.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee
    $busyProgress.MarqueeAnimationSpeed = 28
    $busyProgress.Visible = $false
    $mainBody.Controls.Add($busyProgress)
    $script:BusyProgress = $busyProgress

    $lblSafety = New-Object System.Windows.Forms.Label
    $lblSafety.Text = 'Защитный принцип: V6.5 создаётся из стабильного V6.3.1 без его перезаписи. Неподходящий под правила трафик Windows остаётся напрямую.'
    $lblSafety.Location = New-Object System.Drawing.Point(18, 768)
    $lblSafety.Size = New-Object System.Drawing.Size(($form.ClientSize.Width - 90), 34)
    $lblSafety.Anchor = 'Top,Left,Right'
    $lblSafety.ForeColor = [System.Drawing.Color]::DimGray
    $mainBody.Controls.Add($lblSafety)

    # OBSERVATION -----------------------------------------------------------
    $obsLayout = New-Object System.Windows.Forms.TableLayoutPanel
    $obsLayout.Dock = 'Fill'
    $obsLayout.RowCount = 2
    $obsLayout.ColumnCount = 1
    [void]$obsLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 54)))
    [void]$obsLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    [void]$obsLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    $tabObs.Controls.Add($obsLayout)

    $obsTop = New-Object System.Windows.Forms.Panel
    $obsTop.Dock = 'Fill'
    $obsTop.BackColor = [System.Drawing.Color]::WhiteSmoke
    $obsLayout.Controls.Add($obsTop, 0, 0)

    $lblObsModule = New-Object System.Windows.Forms.Label
    $lblObsModule.Text = 'Сервис:'
    $lblObsModule.Location = New-Object System.Drawing.Point(16, 17)
    $lblObsModule.AutoSize = $true
    $obsTop.Controls.Add($lblObsModule)

    $cmbObsModule = New-Object System.Windows.Forms.ComboBox
    $cmbObsModule.DropDownStyle = 'DropDownList'
    $cmbObsModule.Location = New-Object System.Drawing.Point(75, 13)
    $cmbObsModule.Width = 190
    foreach ($m in $ModuleNames) { [void]$cmbObsModule.Items.Add((Get-ModuleUiName $m)) }
    $savedObsModuleUi = Get-ModuleUiName ([string]$script:UiSettings.ObservationModule)
    $cmbObsModule.SelectedItem = $savedObsModuleUi
    if ($cmbObsModule.SelectedIndex -lt 0) { $cmbObsModule.SelectedIndex = 1 }
    $obsTop.Controls.Add($cmbObsModule)

    $lblObsPeriod = New-Object System.Windows.Forms.Label
    $lblObsPeriod.Text = 'Период:'
    $lblObsPeriod.Location = New-Object System.Drawing.Point(290, 17)
    $lblObsPeriod.AutoSize = $true
    $obsTop.Controls.Add($lblObsPeriod)

    $cmbObsPeriod = New-Object System.Windows.Forms.ComboBox
    $cmbObsPeriod.DropDownStyle = 'DropDownList'
    $cmbObsPeriod.Location = New-Object System.Drawing.Point(355, 13)
    $cmbObsPeriod.Width = 130
    foreach ($p in @('1 час','6 часов','24 часа','7 дней')) { [void]$cmbObsPeriod.Items.Add($p) }
    $cmbObsPeriod.SelectedItem = [string]$script:UiSettings.ObservationPeriod
    if ($cmbObsPeriod.SelectedIndex -lt 0) { $cmbObsPeriod.SelectedItem = '24 часа' }
    $obsTop.Controls.Add($cmbObsPeriod)

    $btnObsRefresh = New-FlatButton 'Обновить графики' 150 30
    $btnObsRefresh.Location = New-Object System.Drawing.Point(505, 11)
    $obsTop.Controls.Add($btnObsRefresh)
    $toolTip.SetToolTip($btnObsRefresh, 'Перечитывает telemetry.jsonl, operational-stats.json и incidents.jsonl. Маршруты при этом не меняются.')

    $btnObsExport = New-FlatButton 'Экспорт CSV' 120 30
    $btnObsExport.Location = New-Object System.Drawing.Point(665, 11)
    $obsTop.Controls.Add($btnObsExport)
    $toolTip.SetToolTip($btnObsExport, 'Экспортирует telemetry выбранного сервиса и периода в CSV. Это операция только чтения; маршрутизация не меняется.')

    $btnObsCopy = New-FlatButton 'Копировать анализ' 150 30
    $btnObsCopy.Location = New-Object System.Drawing.Point(795, 11)
    $obsTop.Controls.Add($btnObsCopy)
    $toolTip.SetToolTip($btnObsCopy, 'Копирует человекочитаемое объяснение режима «Авто» и количественную статистику выбранного сервиса в буфер обмена.')

    $obsSplit = New-Object System.Windows.Forms.SplitContainer
    $obsSplit.Dock = 'Fill'
    $obsSplit.Orientation = 'Horizontal'
    $obsSplit.SplitterDistance = 315
    $obsSplit.BackColor = [System.Drawing.Color]::WhiteSmoke
    $obsLayout.Controls.Add($obsSplit, 0, 1)

    if ($script:ChartsAvailable) {
        $chartLatency = New-Object System.Windows.Forms.DataVisualization.Charting.Chart
        $chartLatency.Dock = 'Fill'
        $chartLatency.BackColor = [System.Drawing.Color]::White
        $areaLatency = New-Object System.Windows.Forms.DataVisualization.Charting.ChartArea 'Задержка'
        $areaLatency.AxisX.LabelStyle.Format = 'HH:mm'
        $areaLatency.AxisX.MajorGrid.LineColor = [System.Drawing.Color]::Gainsboro
        $areaLatency.AxisY.MajorGrid.LineColor = [System.Drawing.Color]::Gainsboro
        $areaLatency.AxisY.Title = 'мс'
        $areaLatency.AxisX.Title = 'время'
        [void]$chartLatency.ChartAreas.Add($areaLatency)
        $obsSplit.Panel1.Controls.Add($chartLatency)
    }
    else {
        $chartLatency = $null
        $lblNoCharts = New-Object System.Windows.Forms.Label
        $lblNoCharts.Text = 'Компонент графиков .NET недоступен. История автоматических переключений и текстовая статистика продолжат работать.'
        $lblNoCharts.Dock = 'Fill'
        $lblNoCharts.TextAlign = 'MiddleCenter'
        $obsSplit.Panel1.Controls.Add($lblNoCharts)
    }

    $lowerObsSplit = New-Object System.Windows.Forms.SplitContainer
    $lowerObsSplit.Dock = 'Fill'
    $lowerObsSplit.Orientation = 'Vertical'
    $lowerObsSplit.SplitterDistance = 520
    $obsSplit.Panel2.Controls.Add($lowerObsSplit)

    if ($script:ChartsAvailable) {
        $chartUptime = New-Object System.Windows.Forms.DataVisualization.Charting.Chart
        $chartUptime.Dock = 'Fill'
        $chartUptime.BackColor = [System.Drawing.Color]::White
        $areaUptime = New-Object System.Windows.Forms.DataVisualization.Charting.ChartArea 'ДоляМаршрутов'
        $areaUptime.AxisX.MajorGrid.Enabled = $false
        $areaUptime.AxisY.MajorGrid.LineColor = [System.Drawing.Color]::Gainsboro
        $areaUptime.AxisY.Title = '% активного времени'
        [void]$chartUptime.ChartAreas.Add($areaUptime)
        $lowerObsSplit.Panel1.Controls.Add($chartUptime)
    }
    else {
        $chartUptime = $null
    }

    $rightObs = New-Object System.Windows.Forms.Panel
    $rightObs.Dock = 'Fill'
    $rightObs.Padding = New-Object System.Windows.Forms.Padding(8)
    $rightObs.BackColor = [System.Drawing.Color]::White
    $lowerObsSplit.Panel2.Controls.Add($rightObs)

    $lblWhyTitle = New-Object System.Windows.Forms.Label
    $lblWhyTitle.Text = 'Почему режим «Авто» выбрал маршрут · фактические числа'
    $lblWhyTitle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 10)
    $lblWhyTitle.Dock = 'Top'
    $lblWhyTitle.Height = 26
    $rightObs.Controls.Add($lblWhyTitle)

    $txtWhy = New-Object System.Windows.Forms.TextBox
    $txtWhy.Multiline = $true
    $txtWhy.ReadOnly = $true
    $txtWhy.WordWrap = $true
    $txtWhy.ScrollBars = 'Vertical'
    $txtWhy.Dock = 'Top'
    $txtWhy.Height = 140
    $txtWhy.BackColor = [System.Drawing.Color]::White
    $txtWhy.BorderStyle = 'FixedSingle'
    $rightObs.Controls.Add($txtWhy)

    $lblHistoryTitle = New-Object System.Windows.Forms.Label
    $lblHistoryTitle.Text = 'История автоматических переключений'
    $lblHistoryTitle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 10)
    $lblHistoryTitle.Dock = 'Top'
    $lblHistoryTitle.Height = 30
    $lblHistoryTitle.Padding = New-Object System.Windows.Forms.Padding(0, 8, 0, 0)
    $rightObs.Controls.Add($lblHistoryTitle)

    $gridHistory = New-Object System.Windows.Forms.DataGridView
    $gridHistory.Dock = 'Fill'
    $gridHistory.AllowUserToAddRows = $false
    $gridHistory.AllowUserToDeleteRows = $false
    $gridHistory.AllowUserToResizeRows = $false
    $gridHistory.ReadOnly = $true
    $gridHistory.RowHeadersVisible = $false
    $gridHistory.AutoGenerateColumns = $false
    $gridHistory.BackgroundColor = [System.Drawing.Color]::White
    $gridHistory.BorderStyle = 'FixedSingle'
    $gridHistory.SelectionMode = 'FullRowSelect'
    $gridHistory.MultiSelect = $false
    $gridHistory.RowTemplate.Height = 30

    $historyColumns = @(
        [pscustomobject]@{ Name='Время'; Header='Время'; Width=105 },
        [pscustomobject]@{ Name='Сервис'; Header='Сервис'; Width=110 },
        [pscustomobject]@{ Name='Переход'; Header='Переход'; Width=115 },
        [pscustomobject]@{ Name='Причина'; Header='Причина'; Width=270 }
    )
    foreach ($spec in $historyColumns) {
        $col = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
        $col.Name = $spec.Name
        $col.HeaderText = $spec.Header
        $col.Width = [int]$spec.Width
        if ($spec.Name -eq 'Причина') { $col.AutoSizeMode = 'Fill'; $col.MinimumWidth = 220 }
        [void]$gridHistory.Columns.Add($col)
    }
    $rightObs.Controls.Add($gridHistory)
    $gridHistory.BringToFront()

    # EVENTS ----------------------------------------------------------------
    $eventsLayout = New-Object System.Windows.Forms.TableLayoutPanel
    $eventsLayout.Dock = 'Fill'
    $eventsLayout.RowCount = 2
    $eventsLayout.ColumnCount = 1
    [void]$eventsLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 58)))
    [void]$eventsLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    [void]$eventsLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    $tabEvents.Controls.Add($eventsLayout)

    $eventsTop = New-Object System.Windows.Forms.FlowLayoutPanel
    $eventsTop.Dock = 'Fill'
    $eventsTop.Padding = New-Object System.Windows.Forms.Padding(14, 12, 8, 8)
    $eventsTop.WrapContents = $false
    $eventsLayout.Controls.Add($eventsTop, 0, 0)

    $lblEventsFilter = New-Object System.Windows.Forms.Label
    $lblEventsFilter.Text = 'Показывать:'
    $lblEventsFilter.AutoSize = $true
    $lblEventsFilter.Margin = New-Object System.Windows.Forms.Padding(0, 8, 8, 0)
    [void]$eventsTop.Controls.Add($lblEventsFilter)

    $cmbEventsFilter = New-Object System.Windows.Forms.ComboBox
    $cmbEventsFilter.DropDownStyle = 'DropDownList'
    $cmbEventsFilter.Width = 190
    foreach ($v in @('Все события','Операции V7','Автоматические переключения','Самопроверки')) { [void]$cmbEventsFilter.Items.Add($v) }
    $cmbEventsFilter.SelectedItem = 'Все события'
    [void]$eventsTop.Controls.Add($cmbEventsFilter)

    $btnEventsRefresh = New-FlatButton 'Обновить журнал' 150 30
    [void]$eventsTop.Controls.Add($btnEventsRefresh)
    $toolTip.SetToolTip($btnEventsRefresh, 'Перечитывает incidents.jsonl, route-decisions.log и selftest-history.jsonl. Маршрутизация не меняется.')

    $btnEventsCopy = New-FlatButton 'Копировать выбранное' 180 30
    [void]$eventsTop.Controls.Add($btnEventsCopy)
    $toolTip.SetToolTip($btnEventsCopy, 'Копирует выбранное событие в буфер обмена вместе с техническими деталями.')

    $gridEvents = New-Object System.Windows.Forms.DataGridView
    $gridEvents.Dock = 'Fill'
    $gridEvents.AllowUserToAddRows = $false
    $gridEvents.AllowUserToDeleteRows = $false
    $gridEvents.AllowUserToResizeRows = $false
    $gridEvents.ReadOnly = $true
    $gridEvents.RowHeadersVisible = $false
    $gridEvents.AutoGenerateColumns = $false
    $gridEvents.BackgroundColor = [System.Drawing.Color]::White
    $gridEvents.BorderStyle = 'FixedSingle'
    $gridEvents.SelectionMode = 'FullRowSelect'
    $gridEvents.MultiSelect = $false
    $gridEvents.RowTemplate.Height = 34
    $eventColumns = @(
        [pscustomobject]@{ Name='Время'; Header='Время'; Width=135 },
        [pscustomobject]@{ Name='Тип'; Header='Тип'; Width=120 },
        [pscustomobject]@{ Name='Сервис'; Header='Сервис'; Width=140 },
        [pscustomobject]@{ Name='Событие'; Header='Событие'; Width=210 },
        [pscustomobject]@{ Name='Подробности'; Header='Подробности'; Width=420 }
    )
    foreach ($spec in $eventColumns) {
        $col = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
        $col.Name = $spec.Name
        $col.HeaderText = $spec.Header
        $col.Width = [int]$spec.Width
        if ($spec.Name -eq 'Подробности') { $col.AutoSizeMode = 'Fill'; $col.MinimumWidth = 300 }
        [void]$gridEvents.Columns.Add($col)
    }
    $eventsLayout.Controls.Add($gridEvents, 0, 1)

    # DIAGNOSTICS -----------------------------------------------------------
    $diagLayout = New-Object System.Windows.Forms.TableLayoutPanel
    $diagLayout.Dock = 'Fill'
    $diagLayout.RowCount = 3
    $diagLayout.ColumnCount = 1
    [void]$diagLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 96)))
    [void]$diagLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 34)))
    [void]$diagLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    [void]$diagLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    $tabDiag.Controls.Add($diagLayout)

    $diagToolbar = New-Object System.Windows.Forms.FlowLayoutPanel
    $diagToolbar.Dock = 'Fill'
    $diagToolbar.Padding = New-Object System.Windows.Forms.Padding(14, 14, 8, 8)
    $diagToolbar.WrapContents = $true
    $diagLayout.Controls.Add($diagToolbar, 0, 0)

    $diagButtons = @(
        [pscustomobject]@{ Text='Самопроверка (только чтение)'; Action='SelfTest'; Tip='Проверяет состояние, прямой IP, SOCKS/VPS, Proxifier, фоновый контроллер, сервисы и чтение GitHub. Ничего не записывает в GitHub.' },
        [pscustomobject]@{ Text='Полная диагностика'; Action='Diagnose'; Tip='Запускает полную диагностику движка V6.5 и показывает технический вывод ниже.' },
        [pscustomobject]@{ Text='Сводка за 24 часа'; Action='Summary'; Tip='Показывает встроенную 24-часовую сводку движка V6.5 по telemetry.' },
        [pscustomobject]@{ Text='Проверка чтения GitHub'; Action='GitHubReadTest'; Tip='Выполняет безопасные ls-remote / clone / fetch / fsck без push.' },
        [pscustomobject]@{ Text='Пакет поддержки'; Action='SupportBundle'; Tip='Создаёт очищенный ZIP без controller PS1, пароля VPS, токенов и LKG-профиля.' }
    )
    foreach ($spec in $diagButtons) {
        $b = New-FlatButton $spec.Text 205 34
        $b.Tag = $spec.Action
        $b.Add_Click({ [void](Start-EngineAction ([string]$this.Tag)) })
        $toolTip.SetToolTip($b, [string]$spec.Tip)
        [void]$diagToolbar.Controls.Add($b)
        [void]$script:BusyControls.Add($b)
    }

    $btnState = New-FlatButton 'Открыть runtime V6.3' 205 34
    $btnState.Add_Click({ Start-Process explorer.exe -ArgumentList "`"$StateDir`"" })
    $toolTip.SetToolTip($btnState, 'Открывает runtime стабильного движка V6.3/V6.5 в %LOCALAPPDATA%. Данные интерфейса V7 находятся отдельно в VPS-Control-Data рядом с программой или в выбранной папке.')
    [void]$diagToolbar.Controls.Add($btnState)

    $btnLegacy = New-FlatButton 'Открыть консоль V6.3.1' 205 34
    $btnLegacy.Add_Click({
        $cmd = Join-Path $PSScriptRoot 'VPS-Control-v6.3.1.cmd'
        if (Test-Path -LiteralPath $cmd) { Start-Process -FilePath $cmd | Out-Null }
        elseif (Test-Path -LiteralPath $EngineSourcePath) { Start-Process $PowerShellExe -ArgumentList "-NoLogo -NoProfile -ExecutionPolicy Bypass -STA -File `"$EngineSourcePath`" -Action Menu" | Out-Null }
        else { [Windows.Forms.MessageBox]::Show('Стабильный VPS-Control-v6.3.1.ps1 не найден рядом с V7. Fallback не запущен.','VPS Control Center','OK','Error')|Out-Null }
    })
    $toolTip.SetToolTip($btnLegacy, 'Открывает прежнее консольное меню. Это основной ручной fallback, если GUI V7 понадобится закрыть.')
    [void]$diagToolbar.Controls.Add($btnLegacy)

    $btnReadiness = New-FlatButton 'Проверить окружение' 205 34
    $toolTip.SetToolTip($btnReadiness, 'Только чтение: проверяет PowerShell, rollback V6.3.1, Proxifier, PuTTY/plink/Pageant, Git/GitHub CLI, Hyper-V, браузеры и доступность хранилища V7. Ничего не устанавливает и не меняет.')
    $btnReadiness.Add_Click({
        try {
            $r = Get-V7EnvironmentReadiness -BaseDir $PSScriptRoot -PowerShellExe $PowerShellExe -EngineSourcePath $EngineSourcePath -EnginePath $EnginePath -StateDir $StateDir -StorageLayout $StorageLayout -Demo:$Demo
            $txtOutput.Text = Format-V7EnvironmentReadinessText $r
            $txtOutput.SelectionStart = 0; $txtOutput.SelectionLength = 0; $txtOutput.ScrollToCaret()
            $lblDiagOperation.Text = "Проверка окружения: обязательных проблем $($r.RequiredProblems), предупреждений $($r.OptionalProblems)."
            Write-UiEvent 'READINESS' 'Проверено локальное окружение' "required=$($r.RequiredProblems); optional=$($r.OptionalProblems)" $(if($r.RequiredProblems -gt 0){'ERROR'}elseif($r.OptionalProblems -gt 0){'WARN'}else{'INFO'})
        } catch {
            $txtOutput.Text = "Не удалось проверить окружение.`r`n`r`n$($_.Exception.Message)"
            Write-UiEvent 'READINESS' 'Ошибка проверки окружения' $_.Exception.Message 'ERROR'
        }
    })
    [void]$diagToolbar.Controls.Add($btnReadiness)

    $btnConsistency = New-FlatButton 'Проверить связанность' 205 34
    $toolTip.SetToolTip($btnConsistency, 'Только чтение: сверяет текущую версию, Capability Truth, manifest, module wiring и соответствие GUI action вызовов helper ValidateSet. Ничего не меняет.')
    $btnConsistency.Add_Click({
        try {
            $script:Consistency=Test-V7FunctionalConsistency -BaseDir $PSScriptRoot -UiVersion $UiVersion -ModuleNames $ModuleNames
            $txtOutput.Text=Format-V7FunctionalConsistencyText $script:Consistency
            $txtOutput.SelectionStart=0;$txtOutput.SelectionLength=0;$txtOutput.ScrollToCaret()
            $lblDiagOperation.Text="Проверка связанности: $([int]$script:Consistency.Summary.Passed)/$([int]$script:Consistency.Summary.Checks), errors=$([int]$script:Consistency.Summary.Errors), warnings=$([int]$script:Consistency.Summary.Warnings)."
            Write-UiEvent 'CONSISTENCY' 'Проверена связанность функций' "passed=$([int]$script:Consistency.Summary.Passed); checks=$([int]$script:Consistency.Summary.Checks); errors=$([int]$script:Consistency.Summary.Errors); warnings=$([int]$script:Consistency.Summary.Warnings)" $(if($script:Consistency.Ok){'INFO'}else{'ERROR'})
            Refresh-UiStatus
        } catch {
            $txtOutput.Text="Не удалось выполнить проверку связанности.`r`n`r`n$($_.Exception.Message)"
            Write-UiEvent 'CONSISTENCY' 'Ошибка проверки связанности' $_.Exception.Message 'ERROR'
        }
    })
    [void]$diagToolbar.Controls.Add($btnConsistency)

    $btnSnapshot = New-FlatButton 'Снимок системы' 205 34
    $toolTip.SetToolTip($btnSnapshot, 'Создаёт schema v2 JSON-снимок: readiness, package integrity, единый Status Center, маршрутизацию и накопительный Keenetic inventory. Пароли, DPAPI-секреты, токены и содержимое LKG не включаются.')
    $btnSnapshot.Add_Click({
        try {
            $r = Get-V7EnvironmentReadiness -BaseDir $PSScriptRoot -PowerShellExe $PowerShellExe -EngineSourcePath $EngineSourcePath -EnginePath $EnginePath -StateDir $StateDir -StorageLayout $StorageLayout -Demo:$Demo
            $active = Get-ActiveVpsProfile
            $activeSafe = if($active){ [pscustomobject]@{ Name=[string]$active.Name; Host=[string]$active.Host; SshPort=[int]$active.SshPort; AuthMode=[string]$active.AuthMode; ExpectedExitIp=[string]$active.ExpectedExitIp } } else { $null }
            $kc = Get-KeeneticConfig
            $keenSafe = if($kc){ [pscustomobject]@{ Host=[string]$kc.Host; EntwareSshPort=[int]$kc.EntwareSshPort; EntwareUser=[string]$kc.EntwareUser; EntwareHostKey=[string]$kc.EntwareHostKey } } else { $null }
            $runtimeForSnapshot=Read-JsonFile $RuntimeFile
            $watchForSnapshot=Get-WatchdogUiStatus;$socksForSnapshot=Test-TcpListener $VccSocksHost $VccSocksPort 250;$reserveForSnapshot=Test-TcpListener $ReserveSocksHost $ReserveSocksPort 180;$proxForSnapshot=Get-ProxifierUiStatus
            $ageForSnapshot=Get-V7RuntimeEvidenceAgeSeconds -Path $RuntimeFile
            $overallForSnapshot=Get-UiOverallState -Runtime $runtimeForSnapshot -Watchdog $watchForSnapshot -SocksUp $socksForSnapshot -ProxifierStatus $proxForSnapshot -Config (Get-ConfigSnapshot) -RuntimeAgeSeconds $ageForSnapshot
            $storageForSnapshot=Test-V7StorageHealth -Layout $StorageLayout;$keenInventory=Read-JsonFile $KeeneticInventoryFile
            $statusForSnapshot=Get-V7StatusCenterModel -Runtime $runtimeForSnapshot -Watchdog $watchForSnapshot -SocksUp $socksForSnapshot -ProxifierStatus $proxForSnapshot -StorageHealth $storageForSnapshot -ModuleNames $ModuleNames -OverallState $overallForSnapshot -RuntimeAgeSeconds $ageForSnapshot -KeeneticInventory $keenInventory -Consistency $script:Consistency -Tunnels (Get-V7TunnelLightMatrix) -RoutingTunnelId (Get-V7RoutingTunnelSelection)
            $snap=New-V7SafeSystemSnapshot -UiVersion $UiVersion -EngineVersion $EngineVersion -Demo ([bool]$Demo) -DataRoot ([string]$StorageLayout.Root) -StateDir ([string]$StateDir) -Readiness $r -Storage $storageForSnapshot -PackageIntegrity (Test-PackageIntegrity -BaseDir $PSScriptRoot) -Consistency $script:Consistency -ActiveVps $activeSafe -KeeneticConfig $keenSafe -KeeneticInventory $keenInventory -StatusCenter $statusForSnapshot -RoutingConfig (Get-ConfigSnapshot) -Runtime $runtimeForSnapshot -RecentEvents @((Get-CombinedEvents 50)) -Tunnels (Get-V7TunnelLightMatrix) -RoutingTunnelId (Get-V7RoutingTunnelSelection)
            $path = Join-Path $UiExportsDir ("system-snapshot-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
            Write-TextAtomic -Path $path -Text ($snap | ConvertTo-Json -Depth 12)
            $txtOutput.Text = (Format-V7EnvironmentReadinessText $r) + "`r`n`r`nБезопасный снимок сохранён:`r`n$path`r`n`r`nСекреты в файл не включены."
            $lblDiagOperation.Text = 'Безопасный снимок системы создан.'
            Write-UiEvent 'SNAPSHOT' 'Создан безопасный снимок системы' $path 'INFO'
        } catch {
            $txtOutput.Text = "Не удалось создать снимок системы.`r`n`r`n$($_.Exception.Message)"
            Write-UiEvent 'SNAPSHOT' 'Ошибка создания снимка системы' $_.Exception.Message 'ERROR'
        }
    })
    [void]$diagToolbar.Controls.Add($btnSnapshot)

    $btnSocksDebug = New-FlatButton 'Собрать лог SOCKS' 205 34
    $toolTip.SetToolTip($btnSocksDebug, 'Создаёт подробный безопасный TXT-отчёт по автоподъёму SOCKS: recovery attempts, engine stdout/stderr, PuTTY/session metadata, listener/watchdog/process state и хвосты controller/watchdog logs. Пароли, DPAPI blobs и private key contents не включаются.')
    $btnSocksDebug.Add_Click({
        try {
            Write-V7SocksTrace 'USER_ACTION' 'Запрошен диагностический отчёт SOCKS.'
            Write-V7SocksSnapshot 'manual-debug-export'
            $path=New-V7SocksDebugReport -OutputDir $UiExportsDir
            $txtOutput.Text="Подробный лог SOCKS создан:`r`n$path`r`n`r`nЗагрузите этот TXT в чат. Пароли/DPAPI/private key contents в отчёт не включаются."
            $lblDiagOperation.Text='Собран подробный лог SOCKS.'
            Write-UiEvent 'DIAGNOSTICS' 'Собран подробный лог SOCKS' $path 'INFO'
            Start-Process notepad.exe -ArgumentList "`"$path`"" | Out-Null
        } catch {
            $txtOutput.Text="Не удалось собрать лог SOCKS.`r`n`r`n$($_.Exception.Message)"
            Write-UiEvent 'DIAGNOSTICS' 'Ошибка сборки лога SOCKS' $_.Exception.Message 'ERROR'
        }
    })
    [void]$diagToolbar.Controls.Add($btnSocksDebug)

    $btnFullDebug = New-FlatButton 'Полный лог / метрики' 205 34
    $toolTip.SetToolTip($btnFullDebug, 'Запускает тяжёлый forensic evidence в отдельном скрытом PowerShell-процессе, чтобы WinForms не зависал. В фоне собираются environment/process/socket/PuTTY evidence, журналы и Windows Application events. Секреты исключаются.')
    $btnFullDebug.Add_Click({
        try {
            Write-V7SocksTrace 'USER_ACTION' 'Запрошен полный диагностический evidence bundle (background worker).'
            Invoke-V7DeepTelemetryTick -Force
            $path=New-V7FullDebugReport -OutputDir $UiExportsDir -Reason 'manual-full-debug'
            $txtOutput.Text="Фоновый сбор полного диагностического лога запущен.`r`n`r`nОжидаемый файл:`r`n$path`r`n`r`nИнтерфейс можно продолжать использовать. Подождите 15–60 секунд и загрузите готовый TXT в чат. Секреты и содержимое ключей не включаются."
            $lblDiagOperation.Text='Фоновый сбор полного лога запущен.'
            Write-UiEvent 'DIAGNOSTICS' 'Фоновый diagnostic evidence поставлен в очередь' $path 'INFO'
            Start-Process explorer.exe -ArgumentList "`"$UiExportsDir`"" | Out-Null
        } catch {
            $txtOutput.Text="Не удалось собрать полный диагностический лог.`r`n`r`n$($_.Exception.Message)"
            Write-UiEvent 'DIAGNOSTICS' 'Ошибка сборки полного диагностического evidence' $_.Exception.Message 'ERROR'
        }
    })
    [void]$diagToolbar.Controls.Add($btnFullDebug)

    $diagStatus = New-Object System.Windows.Forms.TableLayoutPanel
    $diagStatus.Dock = 'Fill'
    $diagStatus.Padding = New-Object System.Windows.Forms.Padding(16, 4, 10, 4)
    $diagStatus.RowCount = 1
    $diagStatus.ColumnCount = 3
    [void]$diagStatus.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent,100)))
    [void]$diagStatus.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute,112)))
    [void]$diagStatus.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute,142)))
    $diagLayout.Controls.Add($diagStatus, 0, 1)

    $lblDiagOperation = New-Object System.Windows.Forms.Label
    $lblDiagOperation.Text = 'Технический вывод последней операции:'
    $lblDiagOperation.Dock = 'Fill'
    $lblDiagOperation.TextAlign = 'MiddleLeft'
    $lblDiagOperation.ForeColor = [System.Drawing.Color]::DimGray
    $diagStatus.Controls.Add($lblDiagOperation,0,0)

    $btnOpenUiLog = New-FlatButton 'Журнал V7' 105 25
    $btnOpenUiLog.Dock = 'Fill'
    $diagStatus.Controls.Add($btnOpenUiLog,1,0)
    $btnCopyOutput = New-FlatButton 'Копировать вывод' 135 25
    $btnCopyOutput.Dock = 'Fill'
    $diagStatus.Controls.Add($btnCopyOutput,2,0)

    $txtOutput = New-Object System.Windows.Forms.TextBox
    $txtOutput.Dock = 'Fill'
    $txtOutput.Multiline = $true
    $txtOutput.ReadOnly = $true
    $txtOutput.ScrollBars = 'Both'
    $txtOutput.WordWrap = $false
    $txtOutput.Font = New-Object System.Drawing.Font('Consolas', 9)
    $txtOutput.BackColor = [System.Drawing.Color]::White
    $txtOutput.Text = "Здесь появится технический вывод операций расширенного движка V6.5.`r`nИсходный V6.3.1 не перезаписывается и остаётся rollback."
    $diagLayout.Controls.Add($txtOutput, 0, 2)

    # EXTENSION -------------------------------------------------------------
    $extendPanel = New-Object System.Windows.Forms.Panel
    $extendPanel.Dock = 'Fill'
    $extendPanel.AutoScroll = $true
    $extendPanel.Padding = New-Object System.Windows.Forms.Padding(24)
    $extendPanel.BackColor = [System.Drawing.Color]::WhiteSmoke
    $tabExtend.Controls.Add($extendPanel)

    $lblExtendTitle = New-Object System.Windows.Forms.Label
    $lblExtendTitle.Text = 'Дополнительные маршруты и шлюзы'
    $lblExtendTitle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 14)
    $lblExtendTitle.Location = New-Object System.Drawing.Point(24, 20)
    $lblExtendTitle.AutoSize = $true
    $extendPanel.Controls.Add($lblExtendTitle)

    $lblExtendHint = New-Object System.Windows.Forms.Label
    $lblExtendHint.Text = 'Claude, Gemini, Docker и Telegram уже добавлены в основную таблицу. Здесь также есть быстрые переключатели браузеров, собственный EXE/сайт и SOCKS-шлюз для Hyper-V.'
    $lblExtendHint.Location = New-Object System.Drawing.Point(28, 55)
    $lblExtendHint.Size = New-Object System.Drawing.Size(1040, 42)
    $lblExtendHint.ForeColor = [System.Drawing.Color]::DimGray
    $extendPanel.Controls.Add($lblExtendHint)


    $groupBrowsers = New-Object System.Windows.Forms.GroupBox
    $groupBrowsers.Text = 'Браузеры: быстрый и строгий маршрут'
    $groupBrowsers.Location = New-Object System.Drawing.Point(24, 105)
    $groupBrowsers.Size = New-Object System.Drawing.Size(1040, 190)
    $extendPanel.Controls.Add($groupBrowsers)

    $chkYandexVps = New-Object System.Windows.Forms.CheckBox
    $chkYandexVps.Text = 'Яндекс Браузер через VPS'
    $chkYandexVps.Location = New-Object System.Drawing.Point(18, 28)
    $chkYandexVps.Size = New-Object System.Drawing.Size(260, 26)
    $groupBrowsers.Controls.Add($chkYandexVps)
    $chkEdgeVps = New-Object System.Windows.Forms.CheckBox
    $chkEdgeVps.Text = 'Microsoft Edge через VPS'
    $chkEdgeVps.Location = New-Object System.Drawing.Point(300, 28)
    $chkEdgeVps.Size = New-Object System.Drawing.Size(250, 26)
    $groupBrowsers.Controls.Add($chkEdgeVps)
    $btnBrowsersApply = New-FlatButton 'Применить маршруты' 180 30
    $btnBrowsersApply.Location = New-Object System.Drawing.Point(570, 24)
    $groupBrowsers.Controls.Add($btnBrowsersApply)

    $chkYandexStrict = New-Object System.Windows.Forms.CheckBox
    $chkYandexStrict.Text = 'Строгий режим Яндекс: запрет UDP'
    $chkYandexStrict.Location = New-Object System.Drawing.Point(18, 66)
    $chkYandexStrict.Size = New-Object System.Drawing.Size(280, 26)
    $chkYandexStrict.Checked = [bool]$script:CustomSettings.StrictYandex
    $groupBrowsers.Controls.Add($chkYandexStrict)
    $btnYandexStrictLaunch = New-FlatButton 'Строго запустить Яндекс' 200 30
    $btnYandexStrictLaunch.Location = New-Object System.Drawing.Point(310, 62)
    $groupBrowsers.Controls.Add($btnYandexStrictLaunch)
    $chkEdgeStrict = New-Object System.Windows.Forms.CheckBox
    $chkEdgeStrict.Text = 'Строгий режим Edge: запрет UDP'
    $chkEdgeStrict.Location = New-Object System.Drawing.Point(530, 66)
    $chkEdgeStrict.Size = New-Object System.Drawing.Size(250, 26)
    $chkEdgeStrict.Checked = [bool]$script:CustomSettings.StrictEdge
    $groupBrowsers.Controls.Add($chkEdgeStrict)
    $btnEdgeStrictLaunch = New-FlatButton 'Строго запустить Edge' 190 30
    $btnEdgeStrictLaunch.Location = New-Object System.Drawing.Point(795, 62)
    $groupBrowsers.Controls.Add($btnEdgeStrictLaunch)
    $btnStrictApply = New-FlatButton 'Применить строгую защиту' 220 30
    $btnStrictApply.Location = New-Object System.Drawing.Point(18, 102)
    $groupBrowsers.Controls.Add($btnStrictApply)
    $lblStrictStatus = New-Object System.Windows.Forms.Label
    $lblStrictStatus.Text = 'Строгий режим блокирует исходящий UDP браузера через Windows Firewall (UAC) и запускает Chromium с --disable-quic. TCP остаётся под Proxifier → VPS.'
    $lblStrictStatus.Location = New-Object System.Drawing.Point(252, 105)
    $lblStrictStatus.Size = New-Object System.Drawing.Size(750, 40)
    $lblStrictStatus.ForeColor = [System.Drawing.Color]::DimGray
    $groupBrowsers.Controls.Add($lblStrictStatus)
    $lblBrowsersHint = New-Object System.Windows.Forms.Label
    $lblBrowsersHint.Text = 'Обычная галочка меняет только TCP-маршрут браузера. Строгая защита дополнительно не даёт самому browser.exe/msedge.exe обходить VPS по UDP. Системный DNS Windows при этом не становится VPN-туннелем.'
    $lblBrowsersHint.Location = New-Object System.Drawing.Point(18, 148)
    $lblBrowsersHint.Size = New-Object System.Drawing.Size(990, 34)
    $lblBrowsersHint.ForeColor = [System.Drawing.Color]::DimGray
    $groupBrowsers.Controls.Add($lblBrowsersHint)
    $toolTip.SetToolTip($chkYandexVps, 'Правило Proxifier применяется к процессу Яндекс Браузера. Это не включает общий VPN Windows.')
    $toolTip.SetToolTip($chkEdgeVps, 'Правило Proxifier применяется только к msedge.exe. Это не влияет на другие приложения.')
    $toolTip.SetToolTip($chkYandexStrict, 'При применении с UAC создаётся отдельное outbound firewall-правило BLOCK UDP только для найденного browser.exe.')
    $toolTip.SetToolTip($chkEdgeStrict, 'При применении с UAC создаётся отдельное outbound firewall-правило BLOCK UDP только для найденного msedge.exe.')

    $groupCustomExe = New-Object System.Windows.Forms.GroupBox
    $groupCustomExe.Text = 'Свой EXE'
    $groupCustomExe.Location = New-Object System.Drawing.Point(24, 310)
    $groupCustomExe.Size = New-Object System.Drawing.Size(1040, 105)
    $extendPanel.Controls.Add($groupCustomExe)

    $txtCustomExe = New-Object System.Windows.Forms.TextBox
    $txtCustomExe.Location = New-Object System.Drawing.Point(16, 31)
    $txtCustomExe.Size = New-Object System.Drawing.Size(800, 26)
    $txtCustomExe.Text = [string]$script:CustomSettings.CustomExePath
    $groupCustomExe.Controls.Add($txtCustomExe)
    $btnBrowseExe = New-FlatButton 'Выбрать EXE…' 150 30
    $btnBrowseExe.Location = New-Object System.Drawing.Point(830, 28)
    $groupCustomExe.Controls.Add($btnBrowseExe)
    $lblCustomExeHint = New-Object System.Windows.Forms.Label
    $lblCustomExeHint.Text = 'Маршрутизируется только выбранный процесс. Пока путь не задан, режим «Свой EXE» должен оставаться «Напрямую».'
    $lblCustomExeHint.Location = New-Object System.Drawing.Point(16, 67)
    $lblCustomExeHint.Size = New-Object System.Drawing.Size(970, 24)
    $lblCustomExeHint.ForeColor = [System.Drawing.Color]::DimGray
    $groupCustomExe.Controls.Add($lblCustomExeHint)
    $toolTip.SetToolTip($txtCustomExe, 'Можно выбрать конкретный .exe. В Proxifier будут добавлены имя процесса и полный путь. Остальные приложения это правило не затрагивает.')

    $groupCustomSite = New-Object System.Windows.Forms.GroupBox
    $groupCustomSite.Text = 'Свой сайт'
    $groupCustomSite.Location = New-Object System.Drawing.Point(24, 427)
    $groupCustomSite.Size = New-Object System.Drawing.Size(1040, 105)
    $extendPanel.Controls.Add($groupCustomSite)

    $txtCustomSite = New-Object System.Windows.Forms.TextBox
    $txtCustomSite.Location = New-Object System.Drawing.Point(16, 31)
    $txtCustomSite.Size = New-Object System.Drawing.Size(800, 26)
    $txtCustomSite.Text = [string]$script:CustomSettings.CustomSiteUrl
    $groupCustomSite.Controls.Add($txtCustomSite)
    $btnSaveCustom = New-FlatButton 'Сохранить правила' 150 30
    $btnSaveCustom.Location = New-Object System.Drawing.Point(830, 28)
    $groupCustomSite.Controls.Add($btnSaveCustom)
    $lblCustomSiteHint = New-Object System.Windows.Forms.Label
    $lblCustomSiteHint.Text = 'Пример: example.org или https://example.org/path. Правило действует на этот hostname и его поддомены; весь прочий Windows-трафик остаётся напрямую.'
    $lblCustomSiteHint.Location = New-Object System.Drawing.Point(16, 67)
    $lblCustomSiteHint.Size = New-Object System.Drawing.Size(970, 24)
    $lblCustomSiteHint.ForeColor = [System.Drawing.Color]::DimGray
    $groupCustomSite.Controls.Add($lblCustomSiteHint)
    $toolTip.SetToolTip($txtCustomSite, 'V7 извлекает hostname и создаёт destination-rule. URL также используется как health probe для AUTO.')

    $groupVm = New-Object System.Windows.Forms.GroupBox
    $groupVm.Text = 'Опциональный доступ Hyper-V VM к VPS-маршруту'
    $groupVm.Location = New-Object System.Drawing.Point(24, 545)
    $groupVm.Size = New-Object System.Drawing.Size(1040, 250)
    $extendPanel.Controls.Add($groupVm)

    $lblVmIntro = New-Object System.Windows.Forms.Label
    $lblVmIntro.Text = 'Создаёт TCP/SOCKS5 gateway только на выбранном vEthernet-адресе хоста. VM сама решает, какие приложения направлять на этот SOCKS. Full VPN Windows не включается.'
    $lblVmIntro.Location = New-Object System.Drawing.Point(16, 28)
    $lblVmIntro.Size = New-Object System.Drawing.Size(990, 42)
    $lblVmIntro.ForeColor = [System.Drawing.Color]::DimGray
    $groupVm.Controls.Add($lblVmIntro)

    $lblVmAdapter = New-Object System.Windows.Forms.Label
    $lblVmAdapter.Text = 'Интерфейс Hyper-V:'
    $lblVmAdapter.Location = New-Object System.Drawing.Point(16, 84)
    $lblVmAdapter.AutoSize = $true
    $groupVm.Controls.Add($lblVmAdapter)

    $cmbVmAdapter = New-Object System.Windows.Forms.ComboBox
    $cmbVmAdapter.DropDownStyle = 'DropDownList'
    $cmbVmAdapter.Location = New-Object System.Drawing.Point(145, 80)
    $cmbVmAdapter.Size = New-Object System.Drawing.Size(520, 26)
    $groupVm.Controls.Add($cmbVmAdapter)

    $btnVmRefresh = New-FlatButton 'Обновить интерфейсы' 165 30
    $btnVmRefresh.Location = New-Object System.Drawing.Point(680, 77)
    $groupVm.Controls.Add($btnVmRefresh)

    $lblVmPort = New-Object System.Windows.Forms.Label
    $lblVmPort.Text = 'Порт VM:'
    $lblVmPort.Location = New-Object System.Drawing.Point(16, 128)
    $lblVmPort.AutoSize = $true
    $groupVm.Controls.Add($lblVmPort)

    $numVmPort = New-Object System.Windows.Forms.NumericUpDown
    $numVmPort.Minimum = 1024
    $numVmPort.Maximum = 65535
    $numVmPort.Value = [decimal][int]$script:CustomSettings.VmListenPort
    $numVmPort.Location = New-Object System.Drawing.Point(145, 124)
    $numVmPort.Width = 100
    $groupVm.Controls.Add($numVmPort)

    $btnVmEnable = New-FlatButton 'Изменить: включить VM' 175 32
    $btnVmEnable.Location = New-Object System.Drawing.Point(275, 120)
    $groupVm.Controls.Add($btnVmEnable)
    $btnVmDisable = New-FlatButton 'Изменить: отключить' 175 32
    $btnVmDisable.Location = New-Object System.Drawing.Point(465, 120)
    $groupVm.Controls.Add($btnVmDisable)
    $btnVmCopy = New-FlatButton 'Копировать адрес SOCKS' 190 32
    $btnVmCopy.Location = New-Object System.Drawing.Point(650, 120)
    $groupVm.Controls.Add($btnVmCopy)

    $lblVmStatus = New-Object System.Windows.Forms.Label
    $lblVmStatus.Text = 'Шлюз VM не проверен.'
    $lblVmStatus.Location = New-Object System.Drawing.Point(16, 170)
    $lblVmStatus.Size = New-Object System.Drawing.Size(990, 48)
    $lblVmStatus.ForeColor = [System.Drawing.Color]::DimGray
    $groupVm.Controls.Add($lblVmStatus)

    $lblVmWarning = New-Object System.Windows.Forms.Label
    $lblVmWarning.Text = 'Важно: шлюз TCP-only. Он не маршрутизирует UDP/QUIC и не меняет default route ни хоста, ни VM. Firewall ограничивается выбранным vEthernet + LocalSubnet.'
    $lblVmWarning.Location = New-Object System.Drawing.Point(16, 216)
    $lblVmWarning.Size = New-Object System.Drawing.Size(990, 26)
    $lblVmWarning.ForeColor = [System.Drawing.Color]::DarkOrange
    $groupVm.Controls.Add($lblVmWarning)
    $toolTip.SetToolTip($btnVmEnable, 'Потребуется UAC-подтверждение. Создаётся netsh portproxy с конкретной привязкой к vEthernet IPv4 и входящее firewall-правило только для этого интерфейса/LocalSubnet.')
    $toolTip.SetToolTip($btnVmDisable, 'Удаляет только portproxy и firewall-правило, созданные VPS Control V7 для выбранного адреса и порта.')


    # VPS SERVERS -----------------------------------------------------------
    $vpsPanel = New-Object System.Windows.Forms.Panel
    $vpsPanel.Dock = 'Fill'
    $vpsPanel.AutoScroll = $true
    $vpsPanel.Padding = New-Object System.Windows.Forms.Padding(18)
    $vpsPanel.BackColor = [System.Drawing.Color]::WhiteSmoke
    $tabVps.Controls.Add($vpsPanel)

    $lblVpsTitle = New-Object System.Windows.Forms.Label
    $lblVpsTitle.Text = 'Управление VPS · профили, ресурсы и безопасное обслуживание'
    $lblVpsTitle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 14)
    $lblVpsTitle.Location = New-Object System.Drawing.Point(20, 18)
    $lblVpsTitle.AutoSize = $true
    $vpsPanel.Controls.Add($lblVpsTitle)

    $lblVpsIntro = New-Object System.Windows.Forms.Label
    $lblVpsIntro.Text = 'Можно хранить несколько VPS, использовать пароль, SSH-ключ или Pageant и выбирать активный сервер только после свежей безопасной предпроверки SSH и внешнего IP. Пароль хранится через Windows DPAPI.'
    $lblVpsIntro.Location = New-Object System.Drawing.Point(24, 52)
    $lblVpsIntro.Size = New-Object System.Drawing.Size(1080, 42)
    $lblVpsIntro.ForeColor = [System.Drawing.Color]::DimGray
    $vpsPanel.Controls.Add($lblVpsIntro)

    $groupProfiles = New-Object System.Windows.Forms.GroupBox
    $groupProfiles.Text = 'Профили VPS'
    $groupProfiles.Location = New-Object System.Drawing.Point(20, 100)
    $groupProfiles.Size = New-Object System.Drawing.Size(1110, 390)
    $vpsPanel.Controls.Add($groupProfiles)

    $lstVpsProfiles = New-Object System.Windows.Forms.ListBox
    $lstVpsProfiles.Location = New-Object System.Drawing.Point(16, 28)
    $lstVpsProfiles.Size = New-Object System.Drawing.Size(255, 290)
    $groupProfiles.Controls.Add($lstVpsProfiles)
    $btnVpsNew = New-FlatButton 'Новый VPS' 115 30
    $btnVpsNew.Location = New-Object System.Drawing.Point(16, 328)
    $groupProfiles.Controls.Add($btnVpsNew)
    $btnVpsDelete = New-FlatButton 'Удалить' 115 30
    $btnVpsDelete.Location = New-Object System.Drawing.Point(145, 328)
    $groupProfiles.Controls.Add($btnVpsDelete)

    $lblVpsName = New-Object System.Windows.Forms.Label; $lblVpsName.Text='Имя:'; $lblVpsName.Location=New-Object System.Drawing.Point(292,31); $lblVpsName.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsName)
    $txtVpsName = New-Object System.Windows.Forms.TextBox; $txtVpsName.Location=New-Object System.Drawing.Point(405,27); $txtVpsName.Size=New-Object System.Drawing.Size(260,26); $groupProfiles.Controls.Add($txtVpsName)
    $lblVpsHost = New-Object System.Windows.Forms.Label; $lblVpsHost.Text='IP / hostname:'; $lblVpsHost.Location=New-Object System.Drawing.Point(292,67); $lblVpsHost.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsHost)
    $txtVpsHost = New-Object System.Windows.Forms.TextBox; $txtVpsHost.Location=New-Object System.Drawing.Point(405,63); $txtVpsHost.Size=New-Object System.Drawing.Size(260,26); $groupProfiles.Controls.Add($txtVpsHost)
    $lblVpsPort = New-Object System.Windows.Forms.Label; $lblVpsPort.Text='SSH-порт:'; $lblVpsPort.Location=New-Object System.Drawing.Point(690,67); $lblVpsPort.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsPort)
    $numVpsPort = New-Object System.Windows.Forms.NumericUpDown; $numVpsPort.Minimum=1; $numVpsPort.Maximum=65535; $numVpsPort.Value=22; $numVpsPort.Location=New-Object System.Drawing.Point(770,63); $numVpsPort.Width=90; $groupProfiles.Controls.Add($numVpsPort)
    $lblVpsUser = New-Object System.Windows.Forms.Label; $lblVpsUser.Text='Логин:'; $lblVpsUser.Location=New-Object System.Drawing.Point(292,103); $lblVpsUser.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsUser)
    $txtVpsUser = New-Object System.Windows.Forms.TextBox; $txtVpsUser.Location=New-Object System.Drawing.Point(405,99); $txtVpsUser.Size=New-Object System.Drawing.Size(180,26); $groupProfiles.Controls.Add($txtVpsUser)
    $lblVpsExit = New-Object System.Windows.Forms.Label; $lblVpsExit.Text='Ожидаемый exit IP:'; $lblVpsExit.Location=New-Object System.Drawing.Point(610,103); $lblVpsExit.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsExit)
    $txtVpsExit = New-Object System.Windows.Forms.TextBox; $txtVpsExit.Location=New-Object System.Drawing.Point(745,99); $txtVpsExit.Size=New-Object System.Drawing.Size(180,26); $groupProfiles.Controls.Add($txtVpsExit)

    $lblVpsAuth = New-Object System.Windows.Forms.Label; $lblVpsAuth.Text='Подключение:'; $lblVpsAuth.Location=New-Object System.Drawing.Point(292,139); $lblVpsAuth.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsAuth)
    $cmbVpsAuth = New-Object System.Windows.Forms.ComboBox; $cmbVpsAuth.DropDownStyle='DropDownList'; $cmbVpsAuth.Location=New-Object System.Drawing.Point(405,135); $cmbVpsAuth.Size=New-Object System.Drawing.Size(260,26); [void]$cmbVpsAuth.Items.Add('Сохранённая сессия PuTTY'); [void]$cmbVpsAuth.Items.Add('IP / логин / пароль'); [void]$cmbVpsAuth.Items.Add('IP / SSH-ключ PuTTY (.ppk)'); [void]$cmbVpsAuth.Items.Add('IP / Pageant (SSH Agent)'); $groupProfiles.Controls.Add($cmbVpsAuth)
    $lblVpsSession = New-Object System.Windows.Forms.Label; $lblVpsSession.Text='PuTTY session:'; $lblVpsSession.Location=New-Object System.Drawing.Point(690,139); $lblVpsSession.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsSession)
    $txtVpsSession = New-Object System.Windows.Forms.TextBox; $txtVpsSession.Location=New-Object System.Drawing.Point(790,135); $txtVpsSession.Size=New-Object System.Drawing.Size(190,26); $groupProfiles.Controls.Add($txtVpsSession)

    $lblVpsPassword = New-Object System.Windows.Forms.Label; $lblVpsPassword.Text='Пароль:'; $lblVpsPassword.Location=New-Object System.Drawing.Point(292,175); $lblVpsPassword.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsPassword)
    $txtVpsPassword = New-Object System.Windows.Forms.TextBox; $txtVpsPassword.Location=New-Object System.Drawing.Point(405,171); $txtVpsPassword.Size=New-Object System.Drawing.Size(260,26); $txtVpsPassword.UseSystemPasswordChar=$true; $groupProfiles.Controls.Add($txtVpsPassword)
    $chkRememberVpsPassword = New-Object System.Windows.Forms.CheckBox; $chkRememberVpsPassword.Text='Запомнить на этом ПК (DPAPI)'; $chkRememberVpsPassword.Location=New-Object System.Drawing.Point(690,171); $chkRememberVpsPassword.Size=New-Object System.Drawing.Size(240,26); $chkRememberVpsPassword.Checked=$true; $groupProfiles.Controls.Add($chkRememberVpsPassword)
    $lblVpsSecretState = New-Object System.Windows.Forms.Label; $lblVpsSecretState.Text='Пароль не сохранён'; $lblVpsSecretState.Location=New-Object System.Drawing.Point(405,202); $lblVpsSecretState.Size=New-Object System.Drawing.Size(520,22); $lblVpsSecretState.ForeColor=[System.Drawing.Color]::DimGray; $groupProfiles.Controls.Add($lblVpsSecretState)

    $lblVpsKey = New-Object System.Windows.Forms.Label; $lblVpsKey.Text='SSH-ключ .ppk:'; $lblVpsKey.Location=New-Object System.Drawing.Point(292,235); $lblVpsKey.AutoSize=$true; $groupProfiles.Controls.Add($lblVpsKey)
    $txtVpsKey = New-Object System.Windows.Forms.TextBox; $txtVpsKey.Location=New-Object System.Drawing.Point(405,231); $txtVpsKey.Size=New-Object System.Drawing.Size(430,26); $groupProfiles.Controls.Add($txtVpsKey)
    $btnVpsKeyBrowse = New-FlatButton 'Выбрать…' 95 28; $btnVpsKeyBrowse.Location=New-Object System.Drawing.Point(845,229); $groupProfiles.Controls.Add($btnVpsKeyBrowse)
    $btnPageantStart = New-FlatButton 'Запустить Pageant' 145 28; $btnPageantStart.Location=New-Object System.Drawing.Point(292,268); $groupProfiles.Controls.Add($btnPageantStart)
    $btnPageantLoad = New-FlatButton 'Загрузить ключ в Pageant' 205 28; $btnPageantLoad.Location=New-Object System.Drawing.Point(450,268); $groupProfiles.Controls.Add($btnPageantLoad)
    $lblPageantState = New-Object System.Windows.Forms.Label; $lblPageantState.Text='Pageant: проверка при использовании'; $lblPageantState.Location=New-Object System.Drawing.Point(670,273); $lblPageantState.Size=New-Object System.Drawing.Size(330,22); $lblPageantState.ForeColor=[System.Drawing.Color]::DimGray; $groupProfiles.Controls.Add($lblPageantState)

    $btnVpsSave = New-FlatButton 'Сохранить профиль' 155 32; $btnVpsSave.Location=New-Object System.Drawing.Point(292,307); $groupProfiles.Controls.Add($btnVpsSave)
    $btnVpsActivate = New-FlatButton 'Сделать активным + применить' 225 32; $btnVpsActivate.Location=New-Object System.Drawing.Point(460,307); $groupProfiles.Controls.Add($btnVpsActivate)
    $btnVpsOpenSsh = New-FlatButton 'Открыть SSH / принять ключ' 210 32; $btnVpsOpenSsh.Location=New-Object System.Drawing.Point(700,307); $groupProfiles.Controls.Add($btnVpsOpenSsh)
    $lblVpsActive = New-Object System.Windows.Forms.Label; $lblVpsActive.Text='Активный VPS: —'; $lblVpsActive.Location=New-Object System.Drawing.Point(292,347); $lblVpsActive.Size=New-Object System.Drawing.Size(760,24); $lblVpsActive.Font=New-Object System.Drawing.Font('Segoe UI Semibold',9.5); $groupProfiles.Controls.Add($lblVpsActive)

    $groupVpsOps = New-Object System.Windows.Forms.GroupBox
    $groupVpsOps.Text = 'Диагностика и расширение возможностей VPS'
    $groupVpsOps.Location = New-Object System.Drawing.Point(20, 505)
    $groupVpsOps.Size = New-Object System.Drawing.Size(1110, 465)
    $vpsPanel.Controls.Add($groupVpsOps)
    $lblVpsOpsHint = New-Object System.Windows.Forms.Label
    $lblVpsOpsHint.Text = 'Диагностика только читает состояние сервера. Автоустановка устанавливает лишь инструменты наблюдения/диагностики и НЕ меняет SSH, firewall, sysctl или сетевые маршруты.'
    $lblVpsOpsHint.Location = New-Object System.Drawing.Point(16, 27); $lblVpsOpsHint.Size=New-Object System.Drawing.Size(1060,40); $lblVpsOpsHint.ForeColor=[System.Drawing.Color]::DimGray; $groupVpsOps.Controls.Add($lblVpsOpsHint)
    $btnVpsTest = New-FlatButton 'Проверить SSH' 130 32; $btnVpsTest.Location=New-Object System.Drawing.Point(16,75); $groupVpsOps.Controls.Add($btnVpsTest)
    $btnVpsHealth = New-FlatButton 'Оценить / предпроверка' 165 32; $btnVpsHealth.Location=New-Object System.Drawing.Point(158,75); $groupVpsOps.Controls.Add($btnVpsHealth)
    $btnVpsDiagnose = New-FlatButton 'Диагностика VPS' 145 32; $btnVpsDiagnose.Location=New-Object System.Drawing.Point(335,75); $groupVpsOps.Controls.Add($btnVpsDiagnose)
    $btnVpsPlan = New-FlatButton 'Что можно установить' 165 32; $btnVpsPlan.Location=New-Object System.Drawing.Point(492,75); $groupVpsOps.Controls.Add($btnVpsPlan)
    $btnVpsInstallBase = New-FlatButton 'Базовые инструменты' 180 32; $btnVpsInstallBase.Location=New-Object System.Drawing.Point(669,75); $groupVpsOps.Controls.Add($btnVpsInstallBase)
    $btnVpsInstallMon = New-FlatButton 'Добавить мониторинг' 175 32; $btnVpsInstallMon.Location=New-Object System.Drawing.Point(861,75); $groupVpsOps.Controls.Add($btnVpsInstallMon)
    $lblVpsHealth = New-Object System.Windows.Forms.Label; $lblVpsHealth.Text='Оценка состояния: ещё не рассчитана'; $lblVpsHealth.Location=New-Object System.Drawing.Point(16,116); $lblVpsHealth.Size=New-Object System.Drawing.Size(1040,24); $lblVpsHealth.Font=New-Object System.Drawing.Font('Segoe UI Semibold',9.5); $lblVpsHealth.ForeColor=[System.Drawing.Color]::DimGray; $groupVpsOps.Controls.Add($lblVpsHealth)
    $lblVpsOpStatus = New-Object System.Windows.Forms.Label; $lblVpsOpStatus.Text='Готово. Выберите профиль VPS.'; $lblVpsOpStatus.Location=New-Object System.Drawing.Point(16,143); $lblVpsOpStatus.Size=New-Object System.Drawing.Size(1040,24); $lblVpsOpStatus.ForeColor=[System.Drawing.Color]::DimGray; $groupVpsOps.Controls.Add($lblVpsOpStatus)
    $txtVpsOutput = New-Object System.Windows.Forms.TextBox; $txtVpsOutput.Location=New-Object System.Drawing.Point(16,173); $txtVpsOutput.Size=New-Object System.Drawing.Size(1075,270); $txtVpsOutput.Multiline=$true; $txtVpsOutput.ReadOnly=$true; $txtVpsOutput.ScrollBars='Both'; $txtVpsOutput.WordWrap=$false; $txtVpsOutput.Font=New-Object System.Drawing.Font('Consolas',9); $txtVpsOutput.BackColor=[System.Drawing.Color]::White; $txtVpsOutput.Text='Здесь появится read-only диагностика ресурсов VPS и результат установки выбранных диагностических пакетов.'; $groupVpsOps.Controls.Add($txtVpsOutput)
    $script:VpsOutputControl = $txtVpsOutput
    $script:VpsStatusControl = $lblVpsOpStatus
    $toolTip.SetToolTip($btnVpsHealth, 'Выполняет безопасную SSH-предпроверку, сверяет внешний IP с ожидаемым IP и рассчитывает оценку 0–100 по нагрузке CPU, памяти, диску, сбойным службам и обновлениям. Результат нужен перед переключением активного VPS.')
    $toolTip.SetToolTip($btnVpsDiagnose, 'Собирает ОС, kernel, uptime/load, CPU, RAM/swap, диски/inodes, сеть, публичный IP, failed services, listening ports, Docker и количество доступных обновлений. Ничего не меняет.')
    $toolTip.SetToolTip($btnVpsInstallBase, 'После подтверждения установит только базовые CLI-инструменты диагностики (например curl, jq, htop, ncdu, lsof, DNS/route/traceroute/unzip). Обновление ОС не выполняется.')
    $toolTip.SetToolTip($btnVpsInstallMon, 'После подтверждения установит средства наблюдения вроде sysstat/vnstat/iotop, если они есть в пакетном менеджере. Конфигурация firewall/SSH не меняется.')
    $toolTip.SetToolTip($txtVpsKey, 'Поддерживается приватный ключ PuTTY .ppk. Для ключа с passphrase предпочтительно загрузить его в Pageant и выбрать режим Pageant.')
    $toolTip.SetToolTip($txtVpsPassword, 'Пароль никогда не записывается в исходный .ps1 или JSON. При включённой галочке он хранится в отдельном DPAPI-зашифрованном файле текущего Windows-пользователя.')


    # TUNNELS ---------------------------------------------------------------
    $tunnelPanel=New-Object Windows.Forms.Panel
    $tunnelPanel.Dock='Fill'
    $tunnelPanel.AutoScroll=$true
    $tunnelPanel.Padding=New-Object System.Windows.Forms.Padding(24)
    $tunnelPanel.BackColor=[Drawing.Color]::WhiteSmoke
    $tabTunnels.Controls.Add($tunnelPanel)

    $lblTunnelTitle=New-Object Windows.Forms.Label
    $lblTunnelTitle.Text='Dual-tunnel control'
    $lblTunnelTitle.Font=New-Object Drawing.Font('Segoe UI',16,[Drawing.FontStyle]::Bold)
    $lblTunnelTitle.AutoSize=$true
    $lblTunnelTitle.Location=New-Object Drawing.Point(24,20)
    $tunnelPanel.Controls.Add($lblTunnelTitle)

    $lblTunnelContract=New-Object Windows.Forms.Label
    $lblTunnelContract.Text='1081 = PRIMARY_AUTO · автоматический lifecycle. 1080 = RESERVE_MANUAL · резерв, lifecycle только вручную.'
    $lblTunnelContract.AutoSize=$true
    $lblTunnelContract.MaximumSize=New-Object Drawing.Size(950,0)
    $lblTunnelContract.Location=New-Object Drawing.Point(26,58)
    $tunnelPanel.Controls.Add($lblTunnelContract)

    $grpPrimary=New-Object Windows.Forms.GroupBox
    $grpPrimary.Text='Основной туннель · PRIMARY_AUTO'
    $grpPrimary.Location=New-Object Drawing.Point(24,95)
    $grpPrimary.Size=New-Object Drawing.Size(980,135)
    $tunnelPanel.Controls.Add($grpPrimary)
    $lblPrimaryTunnel=New-Object Windows.Forms.Label
    $lblPrimaryTunnel.Location=New-Object Drawing.Point(18,28)
    $lblPrimaryTunnel.Size=New-Object Drawing.Size(930,58)
    $lblPrimaryTunnel.Text='127.0.0.1:1081 · состояние обновляется…'
    $grpPrimary.Controls.Add($lblPrimaryTunnel)
    $btnPrimaryRestart=New-FlatButton 'Перезапустить 1081' 180 34
    $btnPrimaryRestart.Location=New-Object Drawing.Point(18,88)
    $grpPrimary.Controls.Add($btnPrimaryRestart)

    $grpReserve=New-Object Windows.Forms.GroupBox
    $grpReserve.Text='Резервный туннель · RESERVE_MANUAL'
    $grpReserve.Location=New-Object Drawing.Point(24,245)
    $grpReserve.Size=New-Object Drawing.Size(980,175)
    $tunnelPanel.Controls.Add($grpReserve)
    $lblReserveTunnel=New-Object Windows.Forms.Label
    $lblReserveTunnel.Location=New-Object Drawing.Point(18,28)
    $lblReserveTunnel.Size=New-Object Drawing.Size(930,55)
    $lblReserveTunnel.Text='127.0.0.1:1080 · OFF допустим и не считается неисправностью.'
    $grpReserve.Controls.Add($lblReserveTunnel)
    $btnReserveStart=New-FlatButton 'Запустить 1080 вручную' 210 34
    $btnReserveStop=New-FlatButton 'Остановить 1080 вручную' 220 34
    $btnReserveTest=New-FlatButton 'Проверить 1080' 170 34
    $btnReserveStart.Location=New-Object Drawing.Point(18,92)
    $btnReserveStop.Location=New-Object Drawing.Point(240,92)
    $btnReserveTest.Location=New-Object Drawing.Point(472,92)
    foreach($b in @($btnReserveStart,$btnReserveStop,$btnReserveTest)){$grpReserve.Controls.Add($b)}
    $lblReserveLast=New-Object Windows.Forms.Label
    $lblReserveLast.Location=New-Object Drawing.Point(18,135)
    $lblReserveLast.Size=New-Object Drawing.Size(930,24)
    $lblReserveLast.Text='Последнее действие: —'
    $grpReserve.Controls.Add($lblReserveLast)

    $grpTunnelRouting=New-Object Windows.Forms.GroupBox
    $grpTunnelRouting.Text='Какой tunnel используют все правила режима VPS'
    $grpTunnelRouting.Location=New-Object Drawing.Point(24,435)
    $grpTunnelRouting.Size=New-Object Drawing.Size(980,145)
    $tunnelPanel.Controls.Add($grpTunnelRouting)
    $lblTunnelRouting=New-Object Windows.Forms.Label
    $lblTunnelRouting.Location=New-Object Drawing.Point(18,28)
    $lblTunnelRouting.Size=New-Object Drawing.Size(930,40)
    $lblTunnelRouting.Text='Текущий выбор: PRIMARY_AUTO / 1081'
    $grpTunnelRouting.Controls.Add($lblTunnelRouting)
    $btnRoutePrimary=New-FlatButton 'VPS-правила → 1081' 200 34
    $btnRouteReserve=New-FlatButton 'VPS-правила → 1080' 200 34
    $btnRoutePrimary.Location=New-Object Drawing.Point(18,82)
    $btnRouteReserve.Location=New-Object Drawing.Point(230,82)
    $grpTunnelRouting.Controls.Add($btnRoutePrimary)
    $grpTunnelRouting.Controls.Add($btnRouteReserve)
    $lblRoutePolicy=New-Object Windows.Forms.Label
    $lblRoutePolicy.Location=New-Object Drawing.Point(450,82)
    $lblRoutePolicy.Size=New-Object Drawing.Size(500,42)
    $lblRoutePolicy.Text='Выбор только вручную. AUTO никогда сам не переключает маршруты на 1080.'
    $grpTunnelRouting.Controls.Add($lblRoutePolicy)

    $toolTip.SetToolTip($btnReserveStart,'Явная ручная команда: создать 1080 через активный VPS профиль. Автоматически VCC эту кнопку никогда не вызывает.')
    $toolTip.SetToolTip($btnReserveStop,'Явная ручная команда: остановить только доказанный PuTTY/plink с -D 127.0.0.1:1080.')
    $toolTip.SetToolTip($btnReserveTest,'Read-only identity/ownership test 1080.')
    $toolTip.SetToolTip($btnRoutePrimary,'Вручную назначает PRIMARY_AUTO/1081 proxy для всех правил, где выбран режим VPS, затем применяет конфигурацию.')
    $toolTip.SetToolTip($btnRouteReserve,'Доступно только если 1080 уже вручную поднят и identity подтверждена. Автозапуска 1080 не будет.')

    # KEENETIC --------------------------------------------------------------
    $keenTabs=New-Object Windows.Forms.TabControl;$keenTabs.Dock='Fill';$tabKeenetic.Controls.Add($keenTabs)
    $tabKOverview=New-Object Windows.Forms.TabPage;$tabKOverview.Text='Обзор';$tabKOverview.BackColor=[Drawing.Color]::WhiteSmoke;[void]$keenTabs.TabPages.Add($tabKOverview)
    $tabKEntware=New-Object Windows.Forms.TabPage;$tabKEntware.Text='Entware / OPKG';$tabKEntware.BackColor=[Drawing.Color]::WhiteSmoke;[void]$keenTabs.TabPages.Add($tabKEntware)
    $tabKPlan=New-Object Windows.Forms.TabPage;$tabKPlan.Text='Установка / восстановление';$tabKPlan.BackColor=[Drawing.Color]::WhiteSmoke;[void]$keenTabs.TabPages.Add($tabKPlan)
    $keenPanel=New-Object Windows.Forms.Panel;$keenPanel.Dock='Fill';$keenPanel.AutoScroll=$true;$keenPanel.Padding=New-Object System.Windows.Forms.Padding(24);$keenPanel.BackColor=[Drawing.Color]::WhiteSmoke;$tabKEntware.Controls.Add($keenPanel)
    $ko=New-Object Windows.Forms.FlowLayoutPanel;$ko.Dock='Top';$ko.Height=150;$ko.Padding=New-Object System.Windows.Forms.Padding(20);$ko.WrapContents=$false;$tabKOverview.Controls.Add($ko)
    $keeneticCards=@(
        [pscustomobject]@{Title='Роутер';Key='KRouter'},
        [pscustomobject]@{Title='Entware';Key='KEntware'},
        [pscustomobject]@{Title='Пакеты';Key='KPackages'},
        [pscustomobject]@{Title='Хранилище /opt';Key='KStorage'}
    )
    foreach($def in $keeneticCards){$c=New-StatusCard $def.Title;$c.Panel.Width=245;[void]$ko.Controls.Add($c.Panel);switch($def.Key){'KRouter'{$script:KeeneticOverviewRouter=$c.Value;$c.Value.Text='Не проверен';$c.Detail.Text='192.0.2.1'}'KEntware'{$script:KeeneticOverviewEntware=$c.Value;$c.Value.Text='Не проверен';$c.Detail.Text='OPKG / /opt'}'KPackages'{$script:KeeneticOverviewPackages=$c.Value;$c.Value.Text='Пакеты: —';$c.Detail.Text='обновления: —'}'KStorage'{$script:KeeneticOverviewStorage=$c.Value;$c.Value.Text='—';$c.Detail.Text='последняя инвентаризация'}}}
    $lblKOverviewHint=New-Object Windows.Forms.Label;$lblKOverviewHint.Text='Read-only inventory ещё не выполнялся. Probe и Entware evidence теперь накапливаются и не затирают друг друга. Полные mutation-транзакции установки/удаления заблокированы до runtime evidence.';$lblKOverviewHint.Location=New-Object Drawing.Point(24,175);$lblKOverviewHint.Size=New-Object Drawing.Size(1050,55);$lblKOverviewHint.ForeColor=[Drawing.Color]::DimGray;$tabKOverview.Controls.Add($lblKOverviewHint);$script:KeeneticOverviewSummary=$lblKOverviewHint
    $txtKLifecycle=New-Object Windows.Forms.TextBox;$txtKLifecycle.Dock='Fill';$txtKLifecycle.Multiline=$true;$txtKLifecycle.ReadOnly=$true;$txtKLifecycle.ScrollBars='Vertical';$txtKLifecycle.Font=New-Object Drawing.Font('Consolas',10);$txtKLifecycle.BackColor=[Drawing.Color]::White;$txtKLifecycle.Text=Get-V7KeeneticLifecycleText;$tabKPlan.Controls.Add($txtKLifecycle)
    $lblKTitle=New-Object Windows.Forms.Label;$lblKTitle.Text='Keenetic Giga · отдельный режим управления';$lblKTitle.Font=New-Object Drawing.Font('Segoe UI Semibold',14);$lblKTitle.Location=New-Object Drawing.Point(24,20);$lblKTitle.AutoSize=$true;$keenPanel.Controls.Add($lblKTitle)
    $lblKHint=New-Object Windows.Forms.Label;$lblKHint.Text='RC14.12 сохраняет безопасный фундамент: накопительный read-only inventory роутера/Entware, отдельные настройки SSH, OPKG и обновления пакетов. Полная установка/удаление будет разрешена только после RCI-инвентаризации модели, компонентов, накопителя и recovery backup.';$lblKHint.Location=New-Object Drawing.Point(28,55);$lblKHint.Size=New-Object Drawing.Size(1050,58);$lblKHint.ForeColor=[Drawing.Color]::DimGray;$keenPanel.Controls.Add($lblKHint)
    $grpKConn=New-Object Windows.Forms.GroupBox;$grpKConn.Text='Подключение';$grpKConn.Location=New-Object Drawing.Point(24,120);$grpKConn.Size=New-Object Drawing.Size(1080,150);$keenPanel.Controls.Add($grpKConn)
    $lkh=New-Object Windows.Forms.Label;$lkh.Text='Адрес:';$lkh.Location=New-Object Drawing.Point(18,31);$lkh.AutoSize=$true;$grpKConn.Controls.Add($lkh)
    $txtKHost=New-Object Windows.Forms.TextBox;$txtKHost.Location=New-Object Drawing.Point(78,27);$txtKHost.Size=New-Object Drawing.Size(180,26);$txtKHost.Text='192.0.2.1';$grpKConn.Controls.Add($txtKHost)
    $lkp=New-Object Windows.Forms.Label;$lkp.Text='Entware SSH:';$lkp.Location=New-Object Drawing.Point(280,31);$lkp.AutoSize=$true;$grpKConn.Controls.Add($lkp)
    $numKPort=New-Object Windows.Forms.NumericUpDown;$numKPort.Location=New-Object Drawing.Point(375,27);$numKPort.Minimum=1;$numKPort.Maximum=65535;$numKPort.Value=222;$numKPort.Size=New-Object Drawing.Size(80,26);$grpKConn.Controls.Add($numKPort)
    $lku=New-Object Windows.Forms.Label;$lku.Text='Пользователь:';$lku.Location=New-Object Drawing.Point(475,31);$lku.AutoSize=$true;$grpKConn.Controls.Add($lku)
    $txtKUser=New-Object Windows.Forms.TextBox;$txtKUser.Location=New-Object Drawing.Point(570,27);$txtKUser.Size=New-Object Drawing.Size(110,26);$txtKUser.Text='root';$grpKConn.Controls.Add($txtKUser)
    $lkpw=New-Object Windows.Forms.Label;$lkpw.Text='Пароль:';$lkpw.Location=New-Object Drawing.Point(700,31);$lkpw.AutoSize=$true;$grpKConn.Controls.Add($lkpw)
    $txtKPass=New-Object Windows.Forms.TextBox;$txtKPass.Location=New-Object Drawing.Point(760,27);$txtKPass.Size=New-Object Drawing.Size(170,26);$txtKPass.UseSystemPasswordChar=$true;$grpKConn.Controls.Add($txtKPass)
    $chkKRemember=New-Object Windows.Forms.CheckBox;$chkKRemember.Text='Сохранить пароль в DPAPI для SSH-операций';$chkKRemember.Location=New-Object Drawing.Point(18,68);$chkKRemember.Size=New-Object Drawing.Size(315,24);$chkKRemember.Checked=$true;$grpKConn.Controls.Add($chkKRemember)
    $btnKSave=New-FlatButton 'Сохранить' 110 30;$btnKSave.Location=New-Object Drawing.Point(345,65);$grpKConn.Controls.Add($btnKSave)
    $btnKWeb=New-FlatButton 'Открыть веб-интерфейс' 185 30;$btnKWeb.Location=New-Object Drawing.Point(470,65);$grpKConn.Controls.Add($btnKWeb)
    $btnKSsh=New-FlatButton 'Проверить / доверить SSH-ключ' 230 30;$btnKSsh.Location=New-Object Drawing.Point(670,65);$grpKConn.Controls.Add($btnKSsh)
    $lblKSecret=New-Object Windows.Forms.Label;$lblKSecret.Text='Без DPAPI-пароля доступны Probe, проверка SSH-ключа и план. Entware SSH блокируется. Fingerprint сервера хранится отдельно от пароля.';$lblKSecret.Location=New-Object Drawing.Point(18,105);$lblKSecret.Size=New-Object Drawing.Size(1035,24);$lblKSecret.ForeColor=[Drawing.Color]::DimGray;$grpKConn.Controls.Add($lblKSecret)
    $grpEnt=New-Object Windows.Forms.GroupBox;$grpEnt.Text='Entware / OPKG — проверка и обслуживание';$grpEnt.Location=New-Object Drawing.Point(24,285);$grpEnt.Size=New-Object Drawing.Size(1080,500);$keenPanel.Controls.Add($grpEnt)
    $btnKProbe=New-FlatButton 'Статус роутера' 140 32;$btnKProbe.Location=New-Object Drawing.Point(16,30);$grpEnt.Controls.Add($btnKProbe)
    $btnEStatus=New-FlatButton 'Статус Entware' 140 32;$btnEStatus.Location=New-Object Drawing.Point(168,30);$grpEnt.Controls.Add($btnEStatus)
    $btnERefresh=New-FlatButton 'Изменить: обновить индекс' 185 32;$btnERefresh.Location=New-Object Drawing.Point(320,30);$grpEnt.Controls.Add($btnERefresh)
    $btnEUpgrade=New-FlatButton 'Изменить: обновить пакеты' 195 32;$btnEUpgrade.Location=New-Object Drawing.Point(517,30);$grpEnt.Controls.Add($btnEUpgrade)
    $btnEReady=New-FlatButton 'План установки / удаления' 195 32;$btnEReady.Location=New-Object Drawing.Point(724,30);$grpEnt.Controls.Add($btnEReady)
    $lblKStatus=New-Object Windows.Forms.Label;$lblKStatus.Text='Готово. Роутер по умолчанию: 192.0.2.1';$lblKStatus.Location=New-Object Drawing.Point(16,75);$lblKStatus.Size=New-Object Drawing.Size(1035,24);$lblKStatus.ForeColor=[Drawing.Color]::DimGray;$grpEnt.Controls.Add($lblKStatus)
    $txtKOutput=New-Object Windows.Forms.TextBox;$txtKOutput.Location=New-Object Drawing.Point(16,108);$txtKOutput.Size=New-Object Drawing.Size(1045,370);$txtKOutput.Multiline=$true;$txtKOutput.ReadOnly=$true;$txtKOutput.ScrollBars='Both';$txtKOutput.WordWrap=$false;$txtKOutput.Font=New-Object Drawing.Font('Consolas',9);$txtKOutput.BackColor=[Drawing.Color]::White;$txtKOutput.Text='Здесь появятся read-only состояние Keenetic и Entware, а также результаты явных операций обновления.';$grpEnt.Controls.Add($txtKOutput)
    $script:KeeneticOutputControl=$txtKOutput;$script:KeeneticStatusControl=$lblKStatus
    $toolTip.SetToolTip($btnKProbe,'Только чтение: проверяет доступность адреса Keenetic, HTTP/HTTPS и настроенный порт Entware SSH. Конфигурацию роутера не меняет.')
    $toolTip.SetToolTip($btnKSsh,'Без открытия интерактивной консоли получает fingerprint SSH-сервера через plink. После явного подтверждения fingerprint фиксируется локально и используется через -hostkey. Пароль повторно вводить не требуется.')
    $toolTip.SetToolTip($btnEStatus,'Только чтение: подключается к Entware SSH и показывает /opt, opkg, количество пакетов и доступных обновлений. Требуется сохранённый DPAPI-пароль.')
    $toolTip.SetToolTip($btnERefresh,'Изменяющая операция: выполняет только opkg update. Разрешается после подтверждённого состояния Entware=INSTALLED и явного подтверждения пользователя.')
    $toolTip.SetToolTip($btnEUpgrade,'Изменяющая операция: opkg update + opkg upgrade. Требуется сохранённый DPAPI-пароль, свежее Entware evidence и явное подтверждение.')
    $toolTip.SetToolTip($btnEReady,'Показывает transaction/readiness-план. RC14.12 не выполняет install/remove Entware до подтверждённой RCI-инвентаризации модели, накопителя, компонентов и recovery backup.')
    $toolTip.SetToolTip($chkKRemember,'SSH helper работает отдельным процессом и не получает пароль из поля формы напрямую. Для Entware SSH пароль должен быть сохранён в DPAPI. Если снять флажок, сохранённый секрет удаляется, а SSH-действия будут fail-closed заблокированы.')

    # SETTINGS --------------------------------------------------------------
    $settingsPanel = New-Object System.Windows.Forms.Panel
    $settingsPanel.Dock = 'Fill'
    $settingsPanel.Padding = New-Object System.Windows.Forms.Padding(24)
    $settingsPanel.AutoScroll = $true
    $settingsPanel.BackColor = [System.Drawing.Color]::WhiteSmoke
    $tabSettings.Controls.Add($settingsPanel)

    $lblSettingsTitle = New-Object System.Windows.Forms.Label
    $lblSettingsTitle.Text = 'Настройки интерфейса'
    $lblSettingsTitle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 14)
    $lblSettingsTitle.Location = New-Object System.Drawing.Point(24, 24)
    $lblSettingsTitle.AutoSize = $true
    $settingsPanel.Controls.Add($lblSettingsTitle)

    $chkAutostart = New-Object System.Windows.Forms.CheckBox
    $chkAutostart.Text = 'Запускать V7 в области уведомлений при входе в Windows'
    $chkAutostart.Location = New-Object System.Drawing.Point(28, 70)
    $chkAutostart.Size = New-Object System.Drawing.Size(500, 28)
    $chkAutostart.Checked = Test-UiAutostart
    $settingsPanel.Controls.Add($chkAutostart)
    $toolTip.SetToolTip($chkAutostart, 'Автозапускается только интерфейс текущего пользователя. Эта настройка относится только к GUI. Системный autostart сетевого движка управляется отдельно ниже.')

    $chkTrayNotifications = New-Object System.Windows.Forms.CheckBox
    $chkTrayNotifications.Text = 'Показывать уведомления только при изменении состояния или маршрута'
    $chkTrayNotifications.Location = New-Object System.Drawing.Point(28, 105)
    $chkTrayNotifications.Size = New-Object System.Drawing.Size(580, 28)
    $chkTrayNotifications.Checked = [bool]$script:UiSettings.TrayNotifications
    $settingsPanel.Controls.Add($chkTrayNotifications)
    $toolTip.SetToolTip($chkTrayNotifications, 'V7 не показывает уведомления на каждом обновлении. Уведомление появляется только при реальном изменении общего состояния или эффективного маршрута.')

    $lblRefreshInterval = New-Object System.Windows.Forms.Label
    $lblRefreshInterval.Text = 'Интервал автообновления:'
    $lblRefreshInterval.Location = New-Object System.Drawing.Point(28, 145)
    $lblRefreshInterval.AutoSize = $true
    $settingsPanel.Controls.Add($lblRefreshInterval)

    $cmbRefreshInterval = New-Object System.Windows.Forms.ComboBox
    $cmbRefreshInterval.DropDownStyle = 'DropDownList'
    $cmbRefreshInterval.Location = New-Object System.Drawing.Point(205, 141)
    $cmbRefreshInterval.Width = 120
    foreach ($v in @('3 сек','5 сек','10 сек','30 сек')) { [void]$cmbRefreshInterval.Items.Add($v) }
    $cmbRefreshInterval.SelectedItem = "$([int]$script:UiSettings.AutoRefreshSeconds) сек"
    $settingsPanel.Controls.Add($cmbRefreshInterval)
    $toolTip.SetToolTip($cmbRefreshInterval, 'Как часто V7 перечитывает runtime-state.json и обновляет главную страницу. Это не меняет частоту watchdog сетевого движка.')

    $btnEngineAutostart = New-FlatButton 'Обновить autostart движка' 230 30
    $btnEngineAutostart.Location = New-Object System.Drawing.Point(360, 138)
    $settingsPanel.Controls.Add($btnEngineAutostart)
    $toolTip.SetToolTip($btnEngineAutostart, 'Явно и с UAC обновляет/устанавливает Windows Scheduled Task движка так, чтобы после входа в Windows запускался V6.5. Исходный V6.3.1 не удаляется.')

    $lblEngineAutostart = New-Object System.Windows.Forms.Label
    $lblEngineAutostart.Text = 'Проверка системного autostart…'
    $lblEngineAutostart.Location = New-Object System.Drawing.Point(28, 178)
    $lblEngineAutostart.Size = New-Object System.Drawing.Size(850, 38)
    $lblEngineAutostart.ForeColor = [System.Drawing.Color]::DimGray
    $settingsPanel.Controls.Add($lblEngineAutostart)

    $groupInfo = New-Object System.Windows.Forms.GroupBox
    $groupInfo.Text = 'Текущая архитектура'
    $groupInfo.Location = New-Object System.Drawing.Point(24, 225)
    $groupInfo.Size = New-Object System.Drawing.Size(820, 210)
    $settingsPanel.Controls.Add($groupInfo)

    $txtArchitecture = New-Object System.Windows.Forms.TextBox
    $txtArchitecture.Multiline = $true
    $txtArchitecture.ReadOnly = $true
    $txtArchitecture.BorderStyle = 'None'
    $txtArchitecture.BackColor = [System.Drawing.Color]::WhiteSmoke
    $txtArchitecture.Location = New-Object System.Drawing.Point(16, 28)
    $txtArchitecture.Size = New-Object System.Drawing.Size(785, 165)
    $txtArchitecture.Text = @"
V7 — русскоязычный локальный центр управления: маршрутизация, строгий режим браузеров, несколько VPS, SSH-ключи/Pageant и оценка состояния серверов. RC14.12 усиливает сквозную связанность и диагностику runtime: единый Status Center, schema-v2 event envelope, расширенный безопасный snapshot и накопительный read-only inventory Keenetic/Entware без разблокировки install/remove mutation.
Сетевой движок: VPS-Control-v6.5.ps1, локально создаваемый из вашего V6.3.1.
Откат: исходный VPS-Control-v6.3.1.ps1 остаётся без изменений.
Состояние движка: $StateDir
Данные V7: $UiStateDir
Структура: config / secrets / runtime / telemetry / logs / backups / exports / nodes

Принцип маршрутизации: DIRECT для неподходящего под правила Windows-трафика.
VPS используется только для сервисов, которым он нужен по конфигурации/AUTO.
Закрытие интерфейса V7 не останавливает SOCKS, Proxifier или watchdog.
"@
    $groupInfo.Controls.Add($txtArchitecture)

    $groupData = New-Object System.Windows.Forms.GroupBox
    $groupData.Text = 'Источники данных V7'
    $groupData.Location = New-Object System.Drawing.Point(24, 455)
    $groupData.Size = New-Object System.Drawing.Size(820, 170)
    $settingsPanel.Controls.Add($groupData)

    $txtDataSources = New-Object System.Windows.Forms.TextBox
    $txtDataSources.Multiline = $true
    $txtDataSources.ReadOnly = $true
    $txtDataSources.BorderStyle = 'None'
    $txtDataSources.BackColor = [System.Drawing.Color]::WhiteSmoke
    $txtDataSources.Location = New-Object System.Drawing.Point(16, 28)
    $txtDataSources.Size = New-Object System.Drawing.Size(785, 125)
    $txtDataSources.Text = @"
runtime-state.json — фактический маршрут, здоровье, latency, AUTO state.
telemetry.jsonl — временной ряд задержек и состояния (до 14 дней).
operational-stats.json — накопительное активное время DIRECT/VPS и число переключений.
incidents.jsonl / route-decisions.log — история автоматических решений.
selftest-history.jsonl — история самопроверок только для чтения.
events.jsonl — единый журнал действий интерфейса V7, VPS Manager и Keenetic.
"@
    $groupData.Controls.Add($txtDataSources)

    $groupStorage = New-Object System.Windows.Forms.GroupBox
    $groupStorage.Text = 'Хранилище и резервные копии V7'
    $groupStorage.Location = New-Object System.Drawing.Point(24, 645)
    $groupStorage.Size = New-Object System.Drawing.Size(980, 185)
    $settingsPanel.Controls.Add($groupStorage)
    $lblStoragePath = New-Object System.Windows.Forms.Label
    $lblStoragePath.Text = "Текущая папка: $UiStateDir"
    $lblStoragePath.Location = New-Object System.Drawing.Point(16, 30)
    $lblStoragePath.Size = New-Object System.Drawing.Size(940, 38)
    $groupStorage.Controls.Add($lblStoragePath)
    $btnStorageCheck = New-FlatButton 'Проверить хранилище' 175 32; $btnStorageCheck.Location=New-Object Drawing.Point(16,78);$groupStorage.Controls.Add($btnStorageCheck)
    $btnStorageBackup = New-FlatButton 'Безопасная копия' 165 32; $btnStorageBackup.Location=New-Object Drawing.Point(203,78);$groupStorage.Controls.Add($btnStorageBackup)
    $btnStorageChoose = New-FlatButton 'Выбрать другую папку…' 205 32; $btnStorageChoose.Location=New-Object Drawing.Point(380,78);$groupStorage.Controls.Add($btnStorageChoose)
    $btnStorageOpen = New-FlatButton 'Открыть папку' 145 32; $btnStorageOpen.Location=New-Object Drawing.Point(597,78);$groupStorage.Controls.Add($btnStorageOpen)
    $lblStorageState = New-Object System.Windows.Forms.Label;$lblStorageState.Text='Безопасная резервная копия не включает DPAPI-секреты и private/password-файлы.';$lblStorageState.Location=New-Object Drawing.Point(16,125);$lblStorageState.Size=New-Object Drawing.Size(930,42);$lblStorageState.ForeColor=[Drawing.Color]::DimGray;$groupStorage.Controls.Add($lblStorageState)
    $toolTip.SetToolTip($btnStorageChoose,'Выбор новой папки записывается рядом с программой в VPS-Control-Data.location. Текущие данные можно скопировать. Новое расположение применяется после перезапуска V7.')
    $toolTip.SetToolTip($btnStorageBackup,'Создаёт ZIP в каталоге backups. Секреты DPAPI, пароли и приватные ключи намеренно исключаются.')

    # TRAY -----------------------------------------------------------------
    $tray = New-Object System.Windows.Forms.NotifyIcon
    $tray.Icon = [System.Drawing.SystemIcons]::Shield
    $tray.Text = 'VPS Control Center'
    $tray.Visible = $true

    $trayMenu = New-Object System.Windows.Forms.ContextMenuStrip
    $miOpen = $trayMenu.Items.Add('Открыть центр управления')
    $miRefresh = $trayMenu.Items.Add('Обновить состояние')
    [void]$trayMenu.Items.Add('-')
    $miApply = $trayMenu.Items.Add('Применить сохранённую маршрутизацию')
    $miDirect = $trayMenu.Items.Add('Временно всё напрямую')
    $miRestart = $trayMenu.Items.Add('Перезапустить VCC SOCKS 1081')
    [void]$trayMenu.Items.Add('-')
    $miSelfTest = $trayMenu.Items.Add('Самопроверка только для чтения')
    $miState = $trayMenu.Items.Add('Открыть runtime V6.3')
    [void]$trayMenu.Items.Add('-')
    $miExit = $trayMenu.Items.Add('Закрыть интерфейс (маршрутизация останется)')
    $tray.ContextMenuStrip = $trayMenu

    function Set-ConfigDirty([bool]$Dirty) {
        $script:ConfigDirty = $Dirty
        if ($lblConfigState) {
            if ($Dirty) { $lblConfigState.Text = '● Есть несохранённые изменения'; $lblConfigState.ForeColor = [System.Drawing.Color]::DarkOrange }
            else { $lblConfigState.Text = 'Настройки сохранены'; $lblConfigState.ForeColor = [System.Drawing.Color]::DarkGreen }
        }
        try {
            $suffix = if ($Dirty) { ' *' } else { '' }
            $form.Text = "VPS Control Center v$UiVersion$(if($Demo){' · ДЕМО'}else{''})$suffix"
        } catch { }
    }

    function Load-ConfigIntoGrid {
        $script:LoadingConfig = $true
        try {
            $cfg = Get-ConfigSnapshot
            $script:LastConfig = $cfg
            foreach ($row in $gridRoutes.Rows) {
                $module = [string]$row.Tag
                $code = Normalize-Mode ([string]$cfg.$module) 'DIRECT'
                $row.Cells['Режим'].Value = Get-ModeUiName $code
            }
            if ($chkYandexVps) { $chkYandexVps.Checked = ([string]$cfg.YandexBrowser -eq 'VPS') }
            if ($chkEdgeVps) { $chkEdgeVps.Checked = ([string]$cfg.Edge -eq 'VPS') }
            Set-ConfigDirty $false
        }
        finally { $script:LoadingConfig = $false }
    }

    function Get-ConfigFromGrid {
        # DataGridView ComboBox can still be in edit mode when the user immediately
        # presses Save/Apply. Commit it here so the visible value is the saved value.
        try { [void]$gridRoutes.EndEdit() } catch { }
        try { [void]$gridRoutes.CommitEdit([System.Windows.Forms.DataGridViewDataErrorContexts]::Commit) } catch { }
        $h = [ordered]@{ Version=$EngineVersion }
        foreach ($module in $ModuleNames) { $h[$module] = [string]$ModuleDefaultModes[$module] }
        $result = [pscustomobject]$h
        foreach ($row in $gridRoutes.Rows) {
            $module = [string]$row.Tag
            $ui = [string]$row.Cells['Режим'].Value
            if ($ModeUiToCode.ContainsKey($ui)) { $result.$module = [string]$ModeUiToCode[$ui] }
        }
        return $result
    }

    function Set-CardState($Card, [string]$Value, [string]$Detail, [string]$State) {
        $Card.Value.Text = $Value
        $Card.Detail.Text = $Detail
        switch ($State) {
            'GOOD' { $Card.Value.ForeColor = [System.Drawing.Color]::DarkGreen }
            'WARN' { $Card.Value.ForeColor = [System.Drawing.Color]::DarkOrange }
            'BAD' { $Card.Value.ForeColor = [System.Drawing.Color]::DarkRed }
            default { $Card.Value.ForeColor = [System.Drawing.Color]::DimGray }
        }
    }

    function Refresh-UiStatus {
        $runtime = Read-JsonFile $RuntimeFile
        $config = Get-ConfigSnapshot
        $script:LastRuntime = $runtime
        $script:LastConfig = $config
        try {
            $activeVps = Get-ActiveVpsProfile
            if ($activeVps) { $lblActiveVpsTop.Text = "Активный VPS: $([string]$activeVps.Name) · $([string]$activeVps.ExpectedExitIp)" }
            else { $lblActiveVpsTop.Text = 'Активный VPS: не выбран' }
        } catch { $lblActiveVpsTop.Text = 'Активный VPS: состояние недоступно' }
        $watch = Get-WatchdogUiStatus
        $socksUp = Test-TcpListener $VccSocksHost $VccSocksPort 250
        $reserveSocksUp = Test-TcpListener $ReserveSocksHost $ReserveSocksPort 180
        $prox = Get-ProxifierUiStatus
        $runtimeAge = Get-V7RuntimeEvidenceAgeSeconds -Path $RuntimeFile
        $runtimeFresh = Test-V7RuntimeEvidenceFresh -AgeSeconds $runtimeAge
        $overall = Get-UiOverallState -Runtime $runtime -Watchdog $watch -SocksUp $socksUp -ProxifierStatus $prox -Config $config -RuntimeAgeSeconds $runtimeAge

        $lastKnownVpsCount = 0
        if($runtime){$lastKnownVpsCount=@($ModuleNames|Where-Object{[string]$runtime.Effective.$_ -eq 'VPS'}).Count}
        $effectiveVpsCount = if($runtimeFresh){$lastKnownVpsCount}else{0}
        $configuredVpsCapable = @($ModuleNames|Where-Object{(Normalize-Mode ([string]$config.$_) 'DIRECT') -in @('AUTO','VPS')}).Count
        if ($socksUp) { Set-CardState $cardSocks 'Работает' "$VccSocksHost`:$VccSocksPort · управляется VCC" 'GOOD' }
        elseif($effectiveVpsCount -gt 0) { Set-CardState $cardSocks 'Не работает' "VPS сейчас используется: VCC SOCKS $VccSocksPort обязателен" 'BAD' }
        elseif($configuredVpsCapable -gt 0) { Set-CardState $cardSocks 'Не готов' $(if(-not $runtimeFresh -and $runtime){'runtime устарел; для AUTO/VPS нужен рабочий SOCKS после восстановления VPS-контура'}else{'сейчас VPS не используется, но SOCKS нужен для AUTO/VPS'}) 'WARN' }
        else { Set-CardState $cardSocks 'Не требуется' 'все сохранённые маршруты DIRECT' 'NEUTRAL' }
        if($reserveSocksUp){Set-CardState $cardReserveSocks 'Работает' '127.0.0.1:1080 · резерв включён вручную' 'GOOD'}
        else{Set-CardState $cardReserveSocks 'Выключен' '127.0.0.1:1080 · это допустимо; автозапуск запрещён' 'NEUTRAL'}
        if($lblPrimaryTunnel){$lblPrimaryTunnel.Text=$(if($socksUp){'127.0.0.1:1081 · LISTEN · AUTO start/recovery разрешены'}else{'127.0.0.1:1081 · OFF · автоматический recovery применяется по policy'})}
        if($lblReserveTunnel){$lblReserveTunnel.Text=$(if($reserveSocksUp){'127.0.0.1:1080 · LISTEN · MANUAL_ONLY'}else{'127.0.0.1:1080 · OFF · допустимое состояние MANUAL_ONLY'})}
        $tm=Get-V7TunnelManagerStatus
        if($tm -and $lblReserveLast){
            $ownerMode=$(if($tm.Reserve -and $tm.Reserve.OwnershipMode){[string]$tm.Reserve.OwnershipMode}else{'—'})
            $lblReserveLast.Text=('Последнее действие: '+[string]$tm.LastAction+' · '+[string]$tm.LastResult+' · owner='+$ownerMode+' · '+[string]$tm.Timestamp)
        }
        $routeTunnel=Get-V7RoutingTunnelSelection
        if($lblTunnelRouting){$lblTunnelRouting.Text=$(if($routeTunnel -eq 'RESERVE_MANUAL'){'Текущий выбор для всех VPS-правил: RESERVE_MANUAL / 127.0.0.1:1080'}else{'Текущий выбор для всех VPS-правил: PRIMARY_AUTO / 127.0.0.1:1081'})}


        if ($prox.Running) { Set-CardState $cardProxifier 'Работает' "PID $($prox.Pid)" 'GOOD' }
        elseif($effectiveVpsCount -gt 0) { Set-CardState $cardProxifier 'Не запущен' 'VPS сейчас используется: Proxifier обязателен' 'BAD' }
        elseif($configuredVpsCapable -gt 0) { Set-CardState $cardProxifier 'Не готов' $(if(-not $runtimeFresh -and $runtime){'runtime устарел; готовность AUTO/VPS будет подтверждена после свежего цикла'}else{'нужен для сохранённых AUTO/VPS-маршрутов'}) 'WARN' }
        else { Set-CardState $cardProxifier 'Не требуется' 'все сохранённые маршруты DIRECT' 'NEUTRAL' }

        if ($watch.State -eq 'RUNNING') { Set-CardState $cardWatchdog 'Работает' $watch.Detail 'GOOD' }
        elseif($configuredVpsCapable -eq 0 -and $effectiveVpsCount -eq 0) { Set-CardState $cardWatchdog 'Не требуется' 'все сохранённые маршруты DIRECT' 'NEUTRAL' }
        elseif ($watch.State -eq 'STALE') { Set-CardState $cardWatchdog 'Сигнал устарел' $watch.Detail 'WARN' }
        else { Set-CardState $cardWatchdog 'Не работает' $watch.Detail 'BAD' }

        if (Test-Path -LiteralPath $LastGoodProfilePath) { Set-CardState $cardLkg 'Есть' 'готов для отката' 'GOOD' }
        else { Set-CardState $cardLkg 'Нет' 'резервный профиль не найден' 'WARN' }

        $self = Get-LastSelfTestUi
        if ($self.State -eq 'PASS') { Set-CardState $cardSelfTest $self.Text 'только чтение' 'GOOD' }
        elseif ($self.State -eq 'WARN') { Set-CardState $cardSelfTest $self.Text 'только чтение' 'WARN' }
        elseif ($self.State -eq 'FAIL') { Set-CardState $cardSelfTest $self.Text 'только чтение' 'BAD' }
        else { Set-CardState $cardSelfTest $self.Text 'только чтение' 'NEUTRAL' }

        $vpsModules = @()
        if ($runtime) { $vpsModules = @($ModuleNames | Where-Object { [string]$runtime.Effective.$_ -eq 'VPS' }) }
        if($runtimeFresh){
            $vpsDetail = if ($vpsModules.Count -gt 0) { (($vpsModules | ForEach-Object { Get-ModuleUiName $_ }) -join ', ') } else { 'управляемые сервисы идут напрямую' }
            Set-CardState $cardVpsUse "$($vpsModules.Count) из $($ModuleNames.Count)" $vpsDetail $(if ($vpsModules.Count -eq $ModuleNames.Count) { 'WARN' } else { 'GOOD' })
        } elseif($runtime) {
            Set-CardState $cardVpsUse 'Данные устарели' "последнее: $($vpsModules.Count) из $($ModuleNames.Count); текущее использование VPS неизвестно" 'WARN'
        } else {
            Set-CardState $cardVpsUse 'Нет данных' 'фактическое использование VPS ещё не определено' 'NEUTRAL'
        }

        if ($runtimeAge -ge 0) {
            if ($runtimeAge -le 120) { Set-CardState $cardFreshness 'Свежие' "$runtimeAge с назад" 'GOOD' }
            elseif ($runtimeAge -le 300) { Set-CardState $cardFreshness 'Устаревают' "$runtimeAge с назад" 'WARN' }
            else { Set-CardState $cardFreshness 'Устарели' "$runtimeAge с назад; значения маршрутов ниже показаны только как последнее evidence" 'WARN' }
        }
        else { Set-CardState $cardFreshness 'Нет данных' 'runtime-state.json отсутствует' 'BAD' }

        if($script:Consistency){
            if($script:Consistency.Ok -and [int]$script:Consistency.Summary.Warnings -eq 0){Set-CardState $cardConsistency 'PASS' "$([int]$script:Consistency.Summary.Passed)/$([int]$script:Consistency.Summary.Checks) проверок" 'GOOD'}
            elseif($script:Consistency.Ok){Set-CardState $cardConsistency 'PASS с предупреждениями' "warnings=$([int]$script:Consistency.Summary.Warnings)" 'WARN'}
            else{Set-CardState $cardConsistency 'FAIL' "errors=$([int]$script:Consistency.Summary.Errors)" 'BAD'}
        } else { Set-CardState $cardConsistency 'Не проверено' 'consistency model отсутствует' 'WARN' }

        foreach ($row in $gridRoutes.Rows) {
            $module = [string]$row.Tag
            $code = Normalize-Mode ([string]$config.$module) 'DIRECT'
            # RC9: фактическое автообновление не перезаписывает несохранённый выбор пользователя в колонке «Режим».

            if ($runtime) {
                $effective = [string]$runtime.Effective.$module
                $health = [string]$runtime.Health.$module
                $metric = $runtime.Metrics.$module
                $lat = 0
                $failure = 'NONE'
                $detail = ''
                if ($metric) {
                    if ($metric.LatencyMs) { $lat = [int]$metric.LatencyMs }
                    if ($metric.FailureClass) { $failure = [string]$metric.FailureClass }
                    if ($metric.Detail) { $detail = [string]$metric.Detail }
                }
                if(-not $runtimeFresh){
                    $lastEffective = if($effective -eq 'VPS'){'через VPS'}elseif($effective -eq 'DIRECT'){'напрямую'}else{'неизвестно'}
                    $lastHealth = Get-HealthUiName $health
                    $row.Cells['Сейчас'].Value = '—'
                    $row.Cells['Состояние'].Value = 'Устарело'
                    $row.Cells['Задержка'].Value = '—'
                    $why = "Фактические данные устарели: $runtimeAge с. Текущее состояние неизвестно. Последнее evidence: $lastEffective, состояние «$lastHealth»."
                    $row.Cells['Почему'].Value = $why
                    $row.Cells['Состояние'].Style.ForeColor = [System.Drawing.Color]::DarkOrange
                } else {
                    $row.Cells['Сейчас'].Value = if ($effective -eq 'VPS') { 'Через VPS' } elseif($effective -eq 'DIRECT') { 'Напрямую' } else { '—' }
                    $row.Cells['Состояние'].Value = Get-HealthUiName $health
                    $row.Cells['Задержка'].Value = if ($lat -gt 0) { "$lat мс" } else { '—' }
                    $why = Get-AutoExplanation -Config $config -Runtime $runtime -Module $module
                    $row.Cells['Почему'].Value = $why
                    if ($health -eq 'HEALTHY') { $row.Cells['Состояние'].Style.ForeColor = [System.Drawing.Color]::DarkGreen }
                    elseif ($health -eq 'DEGRADED') { $row.Cells['Состояние'].Style.ForeColor = [System.Drawing.Color]::DarkOrange }
                    elseif ($health -eq 'FAILED') { $row.Cells['Состояние'].Style.ForeColor = [System.Drawing.Color]::DarkRed }
                    else { $row.Cells['Состояние'].Style.ForeColor = [System.Drawing.Color]::DimGray }
                }

                $tip = $why
                if ($failure -and $failure -ne 'NONE') { $tip += "`r`nПоследняя техническая отметка: $(Get-FailureUiName $failure)." }
                if ($detail) { $tip += "`r`n$detail" }
                $row.Cells['Почему'].ToolTipText = $tip
                $row.Cells['Состояние'].ToolTipText = $tip
            }
            else {
                $row.Cells['Сейчас'].Value = '—'
                $row.Cells['Состояние'].Value = 'Неизвестно'
                $row.Cells['Задержка'].Value = '—'
                $row.Cells['Почему'].Value = 'Фактическое состояние ещё не прочитано.'
            }
        }

        try {
            $statusModel=Get-V7StatusCenterModel -Runtime $runtime -Watchdog $watch -SocksUp $socksUp -ProxifierStatus $prox -StorageHealth (Test-V7StorageHealth -Layout $StorageLayout) -ModuleNames $ModuleNames -OverallState $overall -RuntimeAgeSeconds $runtimeAge -KeeneticInventory (Read-JsonFile $KeeneticInventoryFile) -Consistency $script:Consistency -Tunnels (Get-V7TunnelLightMatrix) -RoutingTunnelId (Get-V7RoutingTunnelSelection)
            $lblHealthTree.Text=Format-V7StatusCenterLine $statusModel
            $lblHealthTree.ForeColor=$(if($statusModel.ControlState -eq 'GOOD'){[Drawing.Color]::DarkGreen}elseif($statusModel.ControlState -eq 'BAD'){[Drawing.Color]::DarkRed}else{[Drawing.Color]::DarkOrange})
            $toolTip.SetToolTip($lblHealthTree,(Format-V7StatusCenterDetails $statusModel))
        } catch {
            $statusModel=$null
            $lblHealthTree.Text='Status Center: не удалось собрать единую сводку.';$lblHealthTree.ForeColor=[Drawing.Color]::DarkRed
        }

        $displayOverall=$overall
        if($statusModel){
            if([string]$statusModel.ControlState -eq 'BAD'){$displayOverall='FAILED'}
            elseif([string]$statusModel.ControlState -eq 'WARN' -and $overall -eq 'HEALTHY'){$displayOverall='DEGRADED'}
        }
        $lblOverall.Text = Get-OverallUiName $displayOverall
        switch ($displayOverall) {
            'HEALTHY' { $lblOverall.ForeColor = [System.Drawing.Color]::DarkGreen; $tray.Icon = [System.Drawing.SystemIcons]::Shield }
            'DEGRADED' { $lblOverall.ForeColor = [System.Drawing.Color]::DarkOrange; $tray.Icon = [System.Drawing.SystemIcons]::Warning }
            'ATTENTION' { $lblOverall.ForeColor = [System.Drawing.Color]::DarkOrange; $tray.Icon = [System.Drawing.SystemIcons]::Warning }
            'STALE_RUNTIME' { $lblOverall.ForeColor = [System.Drawing.Color]::DarkOrange; $tray.Icon = [System.Drawing.SystemIcons]::Warning }
            default { $lblOverall.ForeColor = [System.Drawing.Color]::DarkRed; $tray.Icon = [System.Drawing.SystemIcons]::Error }
        }

        $reason = if ($runtime -and $runtime.LastReason) { Get-LastReasonUiText ([string]$runtime.LastReason) } else { 'нет runtime' }
        $lblUpdated.Text = "Обновлено $(Get-Date -Format 'HH:mm:ss') · $reason"
        $trayText = "VPS Control: $(Get-OverallUiName $displayOverall)"
        if ($trayText.Length -gt 63) { $trayText = $trayText.Substring(0,63) }
        $tray.Text = $trayText

        $effectiveSignature = ''
        if ($runtime) { $effectiveSignature = (($ModuleNames | ForEach-Object { "$_=$([string]$runtime.Effective.$_)" }) -join ';') }
        if ([bool]$script:UiSettings.TrayNotifications) {
            if ($script:LastOverallState -and $script:LastOverallState -ne $displayOverall) {
                $tray.ShowBalloonTip(2500, 'VPS Control Center', "Общее состояние изменилось: $(Get-OverallUiName $script:LastOverallState) → $(Get-OverallUiName $displayOverall).", $(if ($displayOverall -eq 'HEALTHY') { [Windows.Forms.ToolTipIcon]::Info } else { [Windows.Forms.ToolTipIcon]::Warning }))
            }
            elseif ($script:LastEffectiveSignature -and $effectiveSignature -and $script:LastEffectiveSignature -ne $effectiveSignature) {
                $routeText = ($ModuleNames | ForEach-Object { "$(Get-ModuleUiName $_): $([string]$runtime.Effective.$_)" }) -join '; '
                $tray.ShowBalloonTip(2500, 'VPS Control Center', "Изменился эффективный маршрут. $routeText", [Windows.Forms.ToolTipIcon]::Info)
            }
        }
        $script:LastOverallState = $displayOverall
        $script:LastEffectiveSignature = $effectiveSignature
    }

    function Get-SelectedObservationModule {
        $ui = [string]$cmbObsModule.SelectedItem
        foreach ($m in $ModuleNames) { if ((Get-ModuleUiName $m) -eq $ui) { return $m } }
        return 'GitHub'
    }

    function Get-ObservationHours {
        switch ([string]$cmbObsPeriod.SelectedItem) {
            '1 час' { return 1 }
            '6 часов' { return 6 }
            '7 дней' { return 168 }
            default { return 24 }
        }
    }

    function Refresh-HistoryGrid([string]$Module) {
        $gridHistory.Rows.Clear()
        $history = Get-AutoHistory
        $count = 0
        for ($i = $history.Count - 1; $i -ge 0 -and $count -lt 80; $i--) {
            $h = $history[$i]
            if ($Module -and [string]$h.Module -ne $Module) { continue }
            $when = [string]$h.Timestamp
            try { if ($when) { $when = ([datetime]$when).ToString('dd.MM HH:mm:ss') } } catch { }
            $from = if ([string]$h.From -eq 'VPS') { 'VPS' } else { 'DIRECT' }
            $to = if ([string]$h.To -eq 'VPS') { 'VPS' } else { 'DIRECT' }
            $idx = $gridHistory.Rows.Add()
            $row = $gridHistory.Rows[$idx]
            $row.Cells['Время'].Value = $when
            $row.Cells['Сервис'].Value = Get-ModuleUiName ([string]$h.Module)
            $row.Cells['Переход'].Value = "$from → $to"
            $row.Cells['Причина'].Value = Get-DecisionUiText ([string]$h.Reason)
            $row.Cells['Причина'].ToolTipText = if ($h.Detail) { [string]$h.Detail } else { [string]$h.Reason }
            $count++
        }
        if ($count -eq 0) {
            $idx = $gridHistory.Rows.Add()
            $gridHistory.Rows[$idx].Cells['Время'].Value = '—'
            $gridHistory.Rows[$idx].Cells['Сервис'].Value = Get-ModuleUiName $Module
            $gridHistory.Rows[$idx].Cells['Переход'].Value = '—'
            $gridHistory.Rows[$idx].Cells['Причина'].Value = 'Автоматических переключений для выбранного сервиса пока не зафиксировано.'
        }
    }

    function Refresh-LatencyChart([string]$Module, [int]$Hours) {
        if (-not $script:ChartsAvailable -or -not $chartLatency) { return }
        $chartLatency.Series.Clear()
        $chartLatency.Titles.Clear()
        [void]$chartLatency.Titles.Add("Задержка: $(Get-ModuleUiName $Module) · последние $Hours ч")

        $seriesDirect = New-Object System.Windows.Forms.DataVisualization.Charting.Series 'Напрямую'
        $seriesDirect.ChartType = 'Line'
        $seriesDirect.BorderWidth = 2
        $seriesDirect.XValueType = 'DateTime'
        $seriesDirect.ChartArea = 'Задержка'
        [void]$chartLatency.Series.Add($seriesDirect)

        $seriesVps = New-Object System.Windows.Forms.DataVisualization.Charting.Series 'Через VPS'
        $seriesVps.ChartType = 'Line'
        $seriesVps.BorderWidth = 2
        $seriesVps.XValueType = 'DateTime'
        $seriesVps.ChartArea = 'Задержка'
        [void]$chartLatency.Series.Add($seriesVps)

        $cutoff = (Get-Date).AddHours(-1 * $Hours)
        $samples = Read-JsonLines -Path $TelemetryFile -Tail 25000
        $points = 0
        foreach ($s in $samples) {
            if ([string]$s.Module -ne $Module) { continue }
            $dt = $null
            try { $dt = [datetime]$s.Timestamp } catch { continue }
            if ($dt -lt $cutoff) { continue }
            $lat = 0
            try { $lat = [double]$s.LatencyMs } catch { continue }
            if ($lat -le 0) { continue }
            if ([string]$s.Route -eq 'VPS') { [void]$seriesVps.Points.AddXY($dt, $lat) }
            else { [void]$seriesDirect.Points.AddXY($dt, $lat) }
            $points++
        }
        $chartLatency.Legends.Clear()
        $legend = New-Object System.Windows.Forms.DataVisualization.Charting.Legend
        $legend.Docking = 'Top'
        [void]$chartLatency.Legends.Add($legend)
        if ($points -eq 0) {
            [void]$chartLatency.Titles.Add('За выбранный период ещё нет telemetry samples.')
        }
        if ($Hours -gt 24) { $chartLatency.ChartAreas['Задержка'].AxisX.LabelStyle.Format = 'dd.MM HH:mm' }
        else { $chartLatency.ChartAreas['Задержка'].AxisX.LabelStyle.Format = 'HH:mm' }
    }

    function Refresh-UptimeChart {
        if (-not $script:ChartsAvailable -or -not $chartUptime) { return }
        $chartUptime.Series.Clear()
        $chartUptime.Titles.Clear()
        [void]$chartUptime.Titles.Add('Накопительная доля маршрутов за активное время контроллера')
        $directSeries = New-Object System.Windows.Forms.DataVisualization.Charting.Series 'Напрямую'
        $directSeries.ChartType = 'StackedBar100'
        $directSeries.ChartArea = 'ДоляМаршрутов'
        $vpsSeries = New-Object System.Windows.Forms.DataVisualization.Charting.Series 'Через VPS'
        $vpsSeries.ChartType = 'StackedBar100'
        $vpsSeries.ChartArea = 'ДоляМаршрутов'
        [void]$chartUptime.Series.Add($directSeries)
        [void]$chartUptime.Series.Add($vpsSeries)
        $stats = Read-JsonFile $OperationalStatsFile
        foreach ($module in $ModuleNames) {
            $direct = 0.0; $vps = 0.0
            if ($stats -and $stats.Modules -and $stats.Modules.$module) {
                try { $direct = [double]$stats.Modules.$module.DirectSeconds } catch { }
                try { $vps = [double]$stats.Modules.$module.VpsSeconds } catch { }
            }
            $idx1 = $directSeries.Points.AddY($direct)
            $directSeries.Points[$idx1].AxisLabel = Get-ModuleUiName $module
            [void]$vpsSeries.Points.AddY($vps)
        }
        $chartUptime.Legends.Clear()
        $legend = New-Object System.Windows.Forms.DataVisualization.Charting.Legend
        $legend.Docking = 'Top'
        [void]$chartUptime.Legends.Add($legend)
    }

    function Refresh-Observation {
        if (-not $cmbObsModule -or -not $cmbObsPeriod) { return }
        $module = Get-SelectedObservationModule
        $hours = Get-ObservationHours
        $cfg = Get-ConfigSnapshot
        $runtime = Read-JsonFile $RuntimeFile
        $stats = Read-JsonFile $OperationalStatsFile
        $explanation = Get-QuantitativeAutoExplanation -Module $module -Hours $hours -Config $cfg -Runtime $runtime
        $share = Get-RouteShareText -Stats $stats -Module $module
        $txtWhy.Text = "$explanation`r`n`r`nНакопительная статистика активного контроллера: $share."
        Refresh-HistoryGrid $module
        Refresh-LatencyChart $module $hours
        Refresh-UptimeChart
        $newPeriod = [string]$cmbObsPeriod.SelectedItem
        if ([string]$script:UiSettings.ObservationModule -ne $module -or [string]$script:UiSettings.ObservationPeriod -ne $newPeriod) {
            $script:UiSettings.ObservationModule = $module
            $script:UiSettings.ObservationPeriod = $newPeriod
            [void](Save-UiSettings $script:UiSettings)
        }
        $script:LastObservationRefresh = Get-Date
    }

    function Refresh-Events {
        $gridEvents.Rows.Clear()
        $filter = [string]$cmbEventsFilter.SelectedItem
        $events = Get-CombinedEvents -Limit 300
        $count = 0
        foreach ($ev in $events) {
            if ($filter -eq 'Операции V7' -and [string]$ev.Type -ne 'V7') { continue }
            if ($filter -eq 'Автоматические переключения' -and [string]$ev.Type -ne 'AUTO') { continue }
            if ($filter -eq 'Самопроверки' -and [string]$ev.Type -ne 'SELFTEST') { continue }
            $when = [string]$ev.Timestamp
            try { if ($when) { $when = ([datetime]$when).ToString('dd.MM.yyyy HH:mm:ss') } } catch { }
            $idx = $gridEvents.Rows.Add()
            $row = $gridEvents.Rows[$idx]
            $row.Tag = $ev
            $row.Cells['Время'].Value = if ($when) { $when } else { '—' }
            $row.Cells['Тип'].Value = if ([string]$ev.Type -eq 'AUTO') { 'Автоматический маршрут' } elseif([string]$ev.Type -eq 'SELFTEST'){ 'Самопроверка' } else { 'Операция V7' }
            $row.Cells['Сервис'].Value = if ($ev.Module) { Get-ModuleUiName ([string]$ev.Module) } else { '—' }
            $row.Cells['Событие'].Value = [string]$ev.Summary
            $row.Cells['Подробности'].Value = [string]$ev.Detail
            $row.Cells['Подробности'].ToolTipText = [string]$ev.Detail
            $count++
            if ($count -ge 200) { break }
        }
        if ($count -eq 0) {
            $idx = $gridEvents.Rows.Add()
            $gridEvents.Rows[$idx].Cells['Время'].Value = '—'
            $gridEvents.Rows[$idx].Cells['Тип'].Value = '—'
            $gridEvents.Rows[$idx].Cells['Сервис'].Value = '—'
            $gridEvents.Rows[$idx].Cells['Событие'].Value = 'Событий выбранного типа пока нет.'
            $gridEvents.Rows[$idx].Cells['Подробности'].Value = 'Журнал заполняется из evidence движка V6.5.'
        }
        $script:LastEventsRefresh = Get-Date
    }

    function Refresh-EngineAutostartStatus {
        $st = Get-EngineAutostartStatus
        $lblEngineAutostart.Text = [string]$st.Detail
        if ($st.Exists -and $st.Enabled -and -not $st.UsesV65) { $lblEngineAutostart.ForeColor = [System.Drawing.Color]::DarkOrange }
        elseif ($st.UsesV65) { $lblEngineAutostart.ForeColor = [System.Drawing.Color]::DarkGreen }
        else { $lblEngineAutostart.ForeColor = [System.Drawing.Color]::DimGray }
    }

    function Refresh-VmAdapterList {
        $cmbVmAdapter.Items.Clear()
        $script:VmChoicesByDisplay = @{}
        $choices = Get-HyperVAdapterChoices
        foreach ($choice in $choices) {
            $display = [string]$choice.Display
            $script:VmChoicesByDisplay[$display] = $choice
            [void]$cmbVmAdapter.Items.Add($display)
            if ([string]$script:CustomSettings.VmInterfaceAlias -eq [string]$choice.Alias -and [string]$script:CustomSettings.VmListenAddress -eq [string]$choice.Address) {
                $cmbVmAdapter.SelectedItem = $display
            }
        }
        if ($cmbVmAdapter.SelectedIndex -lt 0 -and $cmbVmAdapter.Items.Count -gt 0) { $cmbVmAdapter.SelectedIndex = 0 }
        if ($cmbVmAdapter.Items.Count -eq 0) { $lblVmStatus.Text = 'vEthernet IPv4 не найден. Запустите/создайте Hyper-V virtual switch или VM и обновите список.' }
    }

    function Get-SelectedVmChoice {
        $display = [string]$cmbVmAdapter.SelectedItem
        if (-not $display -or -not $script:VmChoicesByDisplay.ContainsKey($display)) { return $null }
        return $script:VmChoicesByDisplay[$display]
    }

    function Refresh-VmGatewayStatus {
        $choice = Get-SelectedVmChoice
        if (-not $choice) { return }
        try {
            $r = Invoke-VmGatewayChild -Action Status -InterfaceAlias ([string]$choice.Alias) -ListenAddress ([string]$choice.Address) -ListenPort ([int]$numVmPort.Value) -ConnectPort (Get-V7RoutingTunnelPort)
            if ($r.ExitCode -ne 0 -or -not $r.Output) { throw "Проверка шлюза завершилась кодом $($r.ExitCode). $($r.Output)" }
            $status = $r.Output | ConvertFrom-Json
            if ($status.Ready) {
                $lblVmStatus.Text = "ГОТОВ: в VM укажите SOCKS5 $($status.ListenAddress):$($status.ListenPort). Источник: 127.0.0.1:$($status.ConnectPort) / $(Get-V7RoutingTunnelSelection)."
                $lblVmStatus.ForeColor = [System.Drawing.Color]::DarkGreen
            }
            elseif ($status.PortProxyInstalled -or $status.FirewallRuleInstalled) {
                $lblVmStatus.Text = "НЕПОЛНОЕ СОСТОЯНИЕ: portproxy=$($status.PortProxyInstalled), firewall=$($status.FirewallRuleInstalled), локальный SOCKS=$($status.LocalSocksListening)."
                $lblVmStatus.ForeColor = [System.Drawing.Color]::DarkOrange
            }
            else {
                $lblVmStatus.Text = "Шлюз выключен. После включения VM сможет выборочно использовать SOCKS5 $($choice.Address):$([int]$numVmPort.Value)."
                $lblVmStatus.ForeColor = [System.Drawing.Color]::DimGray
            }
        }
        catch {
            $lblVmStatus.Text = "Не удалось проверить шлюз VM: $($_.Exception.Message)"
            $lblVmStatus.ForeColor = [System.Drawing.Color]::DarkRed
        }
    }

    function Save-CustomRulesFromUi([switch]$Silent) {
        try {
            $exe = ([string]$txtCustomExe.Text).Trim()
            $site = ([string]$txtCustomSite.Text).Trim()
            [void](Update-CustomModuleCatalog -ExePath $exe -SiteUrl $site)
            $script:CustomSettings.CustomExePath = $exe
            $script:CustomSettings.CustomSiteUrl = $site
            Save-CustomSettings $script:CustomSettings
            $lblOperation.Text = 'Пользовательские правила сохранены. Для изменения фактического маршрута нажмите «Сохранить и применить» на Главной.'
            $lblOperation.ForeColor = [System.Drawing.Color]::DarkGreen
            if (-not $Silent) { [System.Windows.Forms.MessageBox]::Show('Правила «Свой EXE» и «Свой сайт» сохранены. Текущий Proxifier-профиль пока не менялся.', 'VPS Control Center', 'OK', 'Information') | Out-Null }
            return $true
        }
        catch {
            [System.Windows.Forms.MessageBox]::Show("Не удалось сохранить пользовательские правила.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', 'OK', 'Error') | Out-Null
            return $false
        }
    }

    function Get-SelectedVpsProfileId {
        if (-not $lstVpsProfiles.SelectedItem) { return '' }
        return [string]$lstVpsProfiles.SelectedItem.Id
    }

    function Refresh-VpsProfileList([string]$SelectId = '') {
        $doc = Get-VpsProfileDocument
        $lstVpsProfiles.Items.Clear()
        foreach ($p in @($doc.Profiles)) {
            $display = if ([string]$p.Id -eq [string]$doc.ActiveId) { "★ $([string]$p.Name)" } else { [string]$p.Name }
            $obj = [pscustomobject]@{ Id=[string]$p.Id; Display=$display }
            Add-Member -InputObject $obj -MemberType ScriptMethod -Name ToString -Value { return $this.Display } -Force
            [void]$lstVpsProfiles.Items.Add($obj)
        }
        $active = Get-ActiveVpsProfile
        if ($active) { $lblVpsActive.Text = "Активный VPS: $([string]$active.Name) · exit $([string]$active.ExpectedExitIp)" }
        if (-not $SelectId -and $active) { $SelectId = [string]$active.Id }
        for ($i=0; $i -lt $lstVpsProfiles.Items.Count; $i++) { if ([string]$lstVpsProfiles.Items[$i].Id -eq $SelectId) { $lstVpsProfiles.SelectedIndex=$i; break } }
        if ($lstVpsProfiles.SelectedIndex -lt 0 -and $lstVpsProfiles.Items.Count -gt 0) { $lstVpsProfiles.SelectedIndex=0 }
    }

    function Refresh-VpsHealthUi([string]$ProfileId) {
        if (-not $lblVpsHealth) { return }
        $h=Get-VpsHealthResult $ProfileId
        if (-not $h) { $lblVpsHealth.Text='Оценка состояния: ещё не рассчитана · перед переключением VPS выполните предпроверку'; $lblVpsHealth.ForeColor=[System.Drawing.Color]::DimGray; return }
        $fresh=$false; try { $fresh=((([datetimeoffset]::Now-[datetimeoffset]::Parse([string]$h.GeneratedAt)).TotalMinutes) -le 15) } catch { }
        $prefix=if($fresh){'СВЕЖАЯ'}else{'УСТАРЕЛА'}
        $lblVpsHealth.Text="Оценка состояния: $([int]$h.Score)/100 · $([string]$h.Rating) · SSH=$([bool]$h.SshOk) · внешний IP=$([bool]$h.ExitIpOk) · $prefix"
        if (-not [bool]$h.ExitIpOk -or -not [bool]$h.SshOk) { $lblVpsHealth.ForeColor=[System.Drawing.Color]::DarkRed }
        elseif ([int]$h.Score -ge 90 -and $fresh) { $lblVpsHealth.ForeColor=[System.Drawing.Color]::DarkGreen }
        else { $lblVpsHealth.ForeColor=[System.Drawing.Color]::DarkOrange }
    }

    function Load-VpsProfileEditor([string]$ProfileId) {
        $p = Get-VpsProfileById $ProfileId
        if (-not $p) { return }
        $txtVpsName.Text=[string]$p.Name; $txtVpsHost.Text=[string]$p.Host; $numVpsPort.Value=[decimal][int]$p.SshPort; $txtVpsUser.Text=[string]$p.User; $txtVpsExit.Text=[string]$p.ExpectedExitIp; $txtVpsSession.Text=[string]$p.SavedSession; $txtVpsKey.Text=[string]$p.KeyFile; $txtVpsPassword.Text=''
        switch ([string]$p.AuthMode) { 'Password' { $cmbVpsAuth.SelectedItem='IP / логин / пароль' }; 'PrivateKey' { $cmbVpsAuth.SelectedItem='IP / SSH-ключ PuTTY (.ppk)' }; 'Pageant' { $cmbVpsAuth.SelectedItem='IP / Pageant (SSH Agent)' }; default { $cmbVpsAuth.SelectedItem='Сохранённая сессия PuTTY' } }
        if (Test-VpsSecretStored $ProfileId) { $lblVpsSecretState.Text='Пароль сохранён локально и зашифрован DPAPI.'; $lblVpsSecretState.ForeColor=[System.Drawing.Color]::DarkGreen; $chkRememberVpsPassword.Checked=$true }
        else { $lblVpsSecretState.Text='Сохранённого пароля нет (возможна ключевая/PuTTY-аутентификация).'; $lblVpsSecretState.ForeColor=[System.Drawing.Color]::DimGray }
        $txtVpsName.Tag=$ProfileId
        Update-VpsAuthUi
        Refresh-VpsHealthUi $ProfileId
    }

    function Get-VpsProfileFromEditor {
        $id=[string]$txtVpsName.Tag
        if (-not $id) { $id=('vps-' + [guid]::NewGuid().ToString('N')) }
        $auth=switch ([string]$cmbVpsAuth.SelectedItem) { 'IP / логин / пароль' { 'Password' }; 'IP / SSH-ключ PuTTY (.ppk)' { 'PrivateKey' }; 'IP / Pageant (SSH Agent)' { 'Pageant' }; default { 'SavedSession' } }
        return [pscustomobject]@{ Id=$id; Name=([string]$txtVpsName.Text).Trim(); Host=([string]$txtVpsHost.Text).Trim(); SshPort=[int]$numVpsPort.Value; User=([string]$txtVpsUser.Text).Trim(); ExpectedExitIp=([string]$txtVpsExit.Text).Trim(); AuthMode=$auth; SavedSession=([string]$txtVpsSession.Text).Trim(); KeyFile=([string]$txtVpsKey.Text).Trim() }
    }

    function Update-VpsAuthUi {
        $mode = [string]$cmbVpsAuth.SelectedItem
        $isSession = ($mode -eq 'Сохранённая сессия PuTTY')
        $isPassword = ($mode -eq 'IP / логин / пароль')
        $isKey = ($mode -eq 'IP / SSH-ключ PuTTY (.ppk)')
        $isPageant = ($mode -eq 'IP / Pageant (SSH Agent)')
        $txtVpsSession.Enabled = $isSession
        $txtVpsPassword.Enabled = $isPassword -or $isSession
        $chkRememberVpsPassword.Enabled = $isPassword -or $isSession
        $txtVpsKey.Enabled = $isKey -or $isPageant
        $btnVpsKeyBrowse.Enabled = $isKey -or $isPageant
        $btnPageantStart.Enabled = $isPageant
        $btnPageantLoad.Enabled = $isPageant
        if ($isSession) {
            $profileId=[string]$txtVpsName.Tag
            if($profileId -and (Test-VpsSecretStored $profileId)){$lblVpsSecretState.Text='SavedSession: DPAPI-пароль сохранён; автоматический SOCKS может запускаться без prompt.';$lblVpsSecretState.ForeColor=[System.Drawing.Color]::DarkGreen}
            else{$lblVpsSecretState.Text='SavedSession: DPAPI-пароля нет. Если ExampleVPS использует пароль, введите его один раз и сохраните; ключ/Pageant также допустимы.';$lblVpsSecretState.ForeColor=[System.Drawing.Color]::DarkOrange}
        }
        elseif ($isKey) { $lblVpsSecretState.Text = 'Режим SSH-ключа: пароль VPS не используется.' }
        elseif ($isPageant) { $lblVpsSecretState.Text = 'Режим Pageant: ключ должен быть загружен в SSH Agent.' }
    }

    function Save-VpsEditor {
        try {
            $p=Get-VpsProfileFromEditor
            $remember=[bool]$chkRememberVpsPassword.Checked
            if ([string]$p.AuthMode -in @('PrivateKey','Pageant')) { $remember=$false }
            Save-OrUpdateVpsProfile -Profile $p -Password ([string]$txtVpsPassword.Text) -RememberPassword $remember | Out-Null
            Refresh-VpsProfileList ([string]$p.Id)
            Load-VpsProfileEditor ([string]$p.Id)
            $lblVpsOpStatus.Text='Профиль VPS сохранён.'; $lblVpsOpStatus.ForeColor=[System.Drawing.Color]::DarkGreen
            return $p
        } catch { [System.Windows.Forms.MessageBox]::Show("Не удалось сохранить профиль VPS.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null; return $null }
    }

    function Set-BrowserQuickGrid([string]$Module, [bool]$UseVps) {
        foreach ($row in $gridRoutes.Rows) { if ([string]$row.Tag -eq $Module) { $row.Cells['Режим'].Value = if ($UseVps) { 'Через VPS' } else { 'Напрямую' }; Set-ConfigDirty $true; break } }
    }

    function Show-ControlCenter {
        $form.Show()
        $form.WindowState = 'Normal'
        $form.Activate()
        Refresh-UiStatus
    }

    function Save-KeeneticSettingsFromUi {
        $keeneticSecret=$null
        try {
            if(-not [string]::IsNullOrEmpty([string]$txtKPass.Text)){
                $keeneticSecret=ConvertTo-V7SecureStringFromText -Text ([string]$txtKPass.Text)
            }
            [void](Save-KeeneticConfig $txtKHost.Text ([int]$numKPort.Value) $txtKUser.Text $keeneticSecret ([bool]$chkKRemember.Checked))
            $lblKStatus.Text='Настройки Keenetic сохранены.';$lblKStatus.ForeColor=[Drawing.Color]::DarkGreen
            if(Test-Path -LiteralPath $KeeneticSecretFile){
                $savedK=Get-KeeneticConfig
                $lblKSecret.Text="DPAPI-пароль сохранён. SSH fingerprint: $(if($savedK.EntwareHostKey){'закреплён'}else{'не подтверждён — нажмите «Проверить / доверить SSH-ключ»'})."
                $lblKSecret.ForeColor=$(if($savedK.EntwareHostKey){[Drawing.Color]::DarkGreen}else{[Drawing.Color]::DarkOrange})
                $txtKPass.Clear()
            } else {
                $lblKSecret.Text='DPAPI-пароль не сохранён. Probe и план доступны; SSH-действия Entware будут заблокированы.';$lblKSecret.ForeColor=[Drawing.Color]::DarkOrange
            }
            return $true
        } catch {
            $lblKStatus.Text='Настройки Keenetic не сохранены.';$lblKStatus.ForeColor=[Drawing.Color]::DarkRed
            [Windows.Forms.MessageBox]::Show("Не удалось сохранить настройки Keenetic.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null
            return $false
        }
        finally {
            if($keeneticSecret){try{$keeneticSecret.Dispose()}catch{}}
        }
    }

    function Test-KeeneticActionPrecondition([string]$Action) {
        if(-not (Save-KeeneticSettingsFromUi)){return $false}
        if($Action -in @('EntwareStatus','EntwareRefresh','EntwareUpgrade')){
            if(-not(Test-Path -LiteralPath $KeeneticSecretFile -PathType Leaf)){
                [Windows.Forms.MessageBox]::Show('Для SSH-действий Entware нужен сохранённый DPAPI-пароль. Введите пароль, оставьте включённым «Сохранить пароль в DPAPI для SSH-операций» и сохраните настройки. Probe роутера и план установки/удаления доступны без этого секрета.','VPS Control Center','OK','Warning')|Out-Null
                return $false
            }
        }
        if($Action -in @('EntwareStatus','EntwareRefresh','EntwareUpgrade')){
            $trustCfg=Get-KeeneticConfig
            if(-not ([string]$trustCfg.EntwareHostKey)){
                [Windows.Forms.MessageBox]::Show('SSH fingerprint Keenetic ещё не подтверждён. Нажмите «Проверить / доверить SSH-ключ», сверьте fingerprint и подтвердите его. После этого сохранённый DPAPI-пароль будет использоваться без повторного ввода.','VPS Control Center','OK','Warning')|Out-Null
                return $false
            }
        }
        if($Action -in @('EntwareRefresh','EntwareUpgrade')){
            $inventory=Read-JsonFile $KeeneticInventoryFile
            if(-not $inventory -or [string]$inventory.EntwareState -ne 'INSTALLED'){
                [Windows.Forms.MessageBox]::Show('Изменяющая операция заблокирована: сначала выполните «Статус Entware» и получите evidence ENTWARE=INSTALLED.','VPS Control Center','OK','Warning')|Out-Null
                return $false
            }
            $fresh=$false;$ageHours=-1
            try{if($inventory.LastEntwareAt){$ageHours=((Get-Date)-([datetime]$inventory.LastEntwareAt)).TotalHours;$fresh=($ageHours -ge 0 -and $ageHours -le 24)}}catch{}
            if(-not $fresh){
                [Windows.Forms.MessageBox]::Show('Изменяющая операция заблокирована: последнее Entware evidence старше 24 часов или его время неизвестно. Сначала повторите «Статус Entware».','VPS Control Center','OK','Warning')|Out-Null
                return $false
            }
        }
        return $true
    }

    $kc=Get-KeeneticConfig
    $txtKHost.Text=[string]$kc.Host;$numKPort.Value=[decimal][int]$kc.EntwareSshPort;$txtKUser.Text=[string]$kc.EntwareUser
    if(Test-Path -LiteralPath $KeeneticSecretFile){$lblKSecret.Text="DPAPI-пароль сохранён. SSH fingerprint: $(if($kc.EntwareHostKey){'закреплён'}else{'не подтверждён'}).";$lblKSecret.ForeColor=$(if($kc.EntwareHostKey){[Drawing.Color]::DarkGreen}else{[Drawing.Color]::DarkOrange})}
    try{$ki=Read-JsonFile $KeeneticInventoryFile;if($ki){$script:KeeneticOverviewRouter.Text=Get-V7KeeneticRouterUi $ki;$script:KeeneticOverviewEntware.Text=Get-V7KeeneticEntwareUi $ki;$script:KeeneticOverviewPackages.Text=("Пакеты: $(if($ki.Packages){$ki.Packages}else{'—'}) · обновления: $(if($ki.Updates){$ki.Updates}else{'—'})");if($ki.OptFs){$script:KeeneticOverviewStorage.Text=[string]$ki.OptFs};$script:KeeneticOverviewSummary.Text=Format-V7KeeneticInventorySummary $ki}}catch{}
    $btnKSave.Add_Click({[void](Save-KeeneticSettingsFromUi)})
    $btnKWeb.Add_Click({try{$h=$txtKHost.Text.Trim();if(-not $h){[Windows.Forms.MessageBox]::Show('Укажите адрес Keenetic.','VPS Control Center','OK','Information')|Out-Null;return};Start-Process ("http://"+$h)}catch{[Windows.Forms.MessageBox]::Show("Не удалось открыть веб-интерфейс Keenetic.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null}})
    $btnKSsh.Add_Click({if(Test-KeeneticActionPrecondition 'HostKeyProbe'){[void](Start-KeeneticAction 'HostKeyProbe')}})
    $btnKProbe.Add_Click({if(Test-KeeneticActionPrecondition 'Probe'){[void](Start-KeeneticAction 'Probe')}})
    $btnEStatus.Add_Click({if(Test-KeeneticActionPrecondition 'EntwareStatus'){[void](Start-KeeneticAction 'EntwareStatus')}})
    $btnERefresh.Add_Click({
        if(-not(Test-KeeneticActionPrecondition 'EntwareRefresh')){return}
        $inventory=Read-JsonFile $KeeneticInventoryFile
        $detail="Последнее evidence: пакетов=$([string]$inventory.Packages), обновлений=$([string]$inventory.Updates).`r`n`r`nВыполнить opkg update? Установленные пакеты не обновляются."
        if([Windows.Forms.MessageBox]::Show($detail,'VPS Control Center','YesNo','Warning') -eq [Windows.Forms.DialogResult]::Yes){[void](Start-KeeneticAction 'EntwareRefresh')}
    })
    $btnEUpgrade.Add_Click({
        if(-not(Test-KeeneticActionPrecondition 'EntwareUpgrade')){return}
        $inventory=Read-JsonFile $KeeneticInventoryFile
        $detail="Последнее свежее evidence: пакетов=$([string]$inventory.Packages), доступно обновлений=$([string]$inventory.Updates).`r`n`r`nВыполнить opkg update + opkg upgrade? Это изменит установленные Entware-пакеты."
        if([Windows.Forms.MessageBox]::Show($detail,'VPS Control Center','YesNo','Warning') -eq [Windows.Forms.DialogResult]::Yes){[void](Start-KeeneticAction 'EntwareUpgrade')}
    })
    $btnEReady.Add_Click({if(Test-KeeneticActionPrecondition 'InstallReadiness'){[void](Start-KeeneticAction 'InstallReadiness')}})

    $btnStorageCheck.Add_Click({
        try{$sh=Test-V7StorageHealth -Layout $StorageLayout;if($sh.Ok){$lblStorageState.Text='Хранилище исправно: структура, запись и JSON-проверки PASS.';$lblStorageState.ForeColor=[Drawing.Color]::DarkGreen;Write-UiEvent 'STORAGE' 'Проверка хранилища PASS' $UiStateDir}else{$lblStorageState.Text='Найдены проблемы: '+(@($sh.Issues)-join '; ');$lblStorageState.ForeColor=[Drawing.Color]::DarkRed;Write-UiEvent 'STORAGE' 'Проверка хранилища FAIL' (@($sh.Issues)-join '; ') 'ERROR'}}catch{$lblStorageState.Text=$_.Exception.Message;$lblStorageState.ForeColor=[Drawing.Color]::DarkRed}
    })
    $btnStorageBackup.Add_Click({
        try{$zip=New-V7SafeBackup -BaseDir $PSScriptRoot -Layout $StorageLayout;$lblStorageState.Text="Создана безопасная копия: $zip";$lblStorageState.ForeColor=[Drawing.Color]::DarkGreen;Write-UiEvent 'BACKUP' 'Создана безопасная резервная копия' $zip}catch{[Windows.Forms.MessageBox]::Show("Не удалось создать backup.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null}
    })
    $btnStorageOpen.Add_Click({try{Start-Process explorer.exe -ArgumentList @($UiStateDir)}catch{}})
    $btnStorageChoose.Add_Click({
        if($Demo){[Windows.Forms.MessageBox]::Show('В демо-режиме расположение рабочего хранилища не изменяется.','VPS Control Center','OK','Information')|Out-Null;return}
        $dlg=New-Object Windows.Forms.FolderBrowserDialog;$dlg.Description='Выберите папку для данных VPS Control Center';$dlg.SelectedPath=$UiStateDir
        if($dlg.ShowDialog() -eq [Windows.Forms.DialogResult]::OK){
            $copy=[Windows.Forms.MessageBox]::Show('Скопировать текущие данные V7 в новую папку? Старые данные не будут удалены.','VPS Control Center','YesNo','Question') -eq [Windows.Forms.DialogResult]::Yes
            try{$new=Set-V7DataRootPreference -BaseDir $PSScriptRoot -NewRoot $dlg.SelectedPath -CurrentRoot $UiStateDir -CopyExisting:$copy;Write-UiEvent 'STORAGE' 'Изменено расположение данных' $new;[Windows.Forms.MessageBox]::Show("Новое расположение сохранено:`r`n$new`r`n`r`nПерезапустите V7, чтобы применить его.",'VPS Control Center','OK','Information')|Out-Null}catch{[Windows.Forms.MessageBox]::Show("Не удалось изменить папку данных.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null}
        }
        $dlg.Dispose()
    })

    $btnSave.Add_Click({
        if (-not (Save-CustomRulesFromUi -Silent)) { return }
        $cfg = Get-ConfigFromGrid
        if (Save-ConfigSnapshot $cfg) {
            $script:LastConfig = $cfg
            Set-ConfigDirty $false
            $lblOperation.Text = 'Настройки сохранены. Текущая маршрутизация не менялась.'
            $lblOperation.ForeColor = [System.Drawing.Color]::DarkGreen
            Refresh-UiStatus
        }
    })
    $btnSaveApply.Add_Click({
        if (-not (Save-CustomRulesFromUi -Silent)) { return }
        $cfg = Get-ConfigFromGrid
        if (Save-ConfigSnapshot $cfg) { Set-ConfigDirty $false; [void](Start-EngineAction 'Apply') }
    })
    $btnReload.Add_Click({ Refresh-UiStatus; Refresh-Observation })
    $btnReloadConfig.Add_Click({
        if ($script:ConfigDirty) {
            $answer=[System.Windows.Forms.MessageBox]::Show('В таблице есть несохранённые изменения. Перечитать routing-config.json и отбросить их?','VPS Control Center','YesNo','Warning')
            if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }
        }
        Load-ConfigIntoGrid; Refresh-UiStatus
    })
    $btnApply.Add_Click({
        if($script:ConfigDirty){
            $answer=[Windows.Forms.MessageBox]::Show('В таблице есть несохранённые изменения. Кнопка «Применить сохранённое» применит прежний routing-config.json, а не текущие значения таблицы.`r`n`r`nПрименить именно ранее сохранённую конфигурацию?','VPS Control Center','YesNo','Warning')
            if($answer -ne [Windows.Forms.DialogResult]::Yes){return}
        }
        [void](Start-EngineAction 'Apply')
    })
    $btnDirect.Add_Click({
        $answer=[System.Windows.Forms.MessageBox]::Show('Временно перевести все управляемые сервисы на DIRECT? Сохранённая конфигурация не будет стёрта.','VPS Control Center','YesNo','Question')
        if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) { [void](Start-EngineAction 'Direct') }
    })
    $btnRestart.Add_Click({ Write-V7SocksTrace 'USER_ACTION' 'Нажата кнопка Перезапустить VCC SOCKS 1081'; Write-V7SocksSnapshot 'manual-restart-click'; Start-EngineAction 'RestartTunnel' })
    $btnPrimaryRestart.Add_Click({Write-V7SocksTrace 'USER_ACTION' 'Туннели: ручной restart PRIMARY_AUTO 1081';[void](Start-EngineAction 'RestartTunnel')})
    $btnReserveStart.Add_Click({
        Write-V7SocksTrace 'USER_ACTION' 'Туннели: ручной StartReserve 1080'
        [void](Start-V7TunnelManagerAction 'StartReserve')
    })
    $btnReserveStop.Add_Click({
        if([Windows.Forms.MessageBox]::Show('Остановить резервный ручной SOCKS 1080? Автоматически VCC его после этого не восстановит.','VPS Control Center','YesNo','Question') -eq [Windows.Forms.DialogResult]::Yes){
            Write-V7SocksTrace 'USER_ACTION' 'Туннели: ручной StopReserve 1080'
            [void](Start-V7TunnelManagerAction 'StopReserve')
        }
    })
    $btnReserveTest.Add_Click({Write-V7SocksTrace 'USER_ACTION' 'Туннели: TestReserve 1080';[void](Start-V7TunnelManagerAction 'TestReserve')})
    $btnRoutePrimary.Add_Click({
        $r=Invoke-V7TunnelManagerSync 'SelectPrimaryRoute'
        if($r.ExitCode -eq 0){
            Write-V7SocksTrace 'USER_ACTION' 'Routing tunnel manually selected PRIMARY_AUTO/1081'
            [void](Start-EngineAction 'Apply')
        }else{[Windows.Forms.MessageBox]::Show("Не удалось выбрать 1081.`r`n`r`n$($r.Output)",'Туннели','OK','Error')|Out-Null}
    })
    $btnRouteReserve.Add_Click({
        $r=Invoke-V7TunnelManagerSync 'SelectReserveRoute'
        if($r.ExitCode -eq 0){
            Write-V7SocksTrace 'USER_ACTION' 'Routing tunnel manually selected RESERVE_MANUAL/1080'
            [void](Start-EngineAction 'Apply')
        }else{[Windows.Forms.MessageBox]::Show("1080 нельзя выбрать для VPS-правил.`r`n`r`nСначала вручную запустите и проверьте резервный tunnel.`r`n`r`n$($r.Output)",'Туннели','OK','Warning')|Out-Null}
    })


    $btnCopySnapshot.Add_Click({
        try {
            $runtime = Read-JsonFile $RuntimeFile
            $config = Get-ConfigSnapshot
            $watch = Get-WatchdogUiStatus
            $socksUp = Test-TcpListener $VccSocksHost $VccSocksPort 250
            $prox = Get-ProxifierUiStatus
            $snapshotRuntimeAge = Get-V7RuntimeEvidenceAgeSeconds -Path $RuntimeFile
            $overall = Get-UiOverallState -Runtime $runtime -Watchdog $watch -SocksUp $socksUp -ProxifierStatus $prox -Config $config -RuntimeAgeSeconds $snapshotRuntimeAge
            [System.Windows.Forms.Clipboard]::SetText((Get-SafeSnapshotText -Config $config -Runtime $runtime -Overall $overall -Watchdog $watch -SocksUp $socksUp -ReserveSocksUp (Test-TcpListener $ReserveSocksHost $ReserveSocksPort 180) -RoutingTunnelId (Get-V7RoutingTunnelSelection) -ProxifierStatus $prox))
            $lblOperation.Text = 'Безопасный снимок состояния скопирован в буфер обмена.'
            $lblOperation.ForeColor = [System.Drawing.Color]::DarkGreen
        }
        catch {
            [System.Windows.Forms.MessageBox]::Show("Не удалось скопировать снимок.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
        }
    })
    $btnCopyOutput.Add_Click({
        try { if ($txtOutput.Text) { [System.Windows.Forms.Clipboard]::SetText($txtOutput.Text); $lblOperation.Text='Технический вывод скопирован.'; $lblOperation.ForeColor=[System.Drawing.Color]::DarkGreen } } catch { }
    })
    $btnOpenUiLog.Add_Click({
        try {
            if (-not (Test-Path -LiteralPath $UiLogFile)) { [IO.File]::WriteAllText($UiLogFile,'',[Text.Encoding]::UTF8) }
            Start-Process notepad.exe -ArgumentList "`"$UiLogFile`"" | Out-Null
        } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Журнал V7','OK','Error')|Out-Null }
    })
    $btnObsRefresh.Add_Click({ Refresh-Observation })
    $btnObsCopy.Add_Click({
        try {
            if ($txtWhy.Text) { [System.Windows.Forms.Clipboard]::SetText($txtWhy.Text) }
        }
        catch { }
    })
    $btnObsExport.Add_Click({
        $module = Get-SelectedObservationModule
        $hours = Get-ObservationHours
        $dlg = New-Object System.Windows.Forms.SaveFileDialog
        $dlg.Filter = 'CSV (*.csv)|*.csv|Все файлы (*.*)|*.*'
        $dlg.FileName = "VPS-Control-$module-telemetry-$(Get-Date -Format 'yyyyMMdd-HHmmss').csv"
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            try {
                $count = Export-TelemetryCsv -Module $module -Hours $hours -Path $dlg.FileName
                if ($count -gt 0) {
                    [System.Windows.Forms.MessageBox]::Show("Экспортировано записей: $count`r`n`r`n$($dlg.FileName)", 'VPS Control Center', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
                }
                else {
                    [System.Windows.Forms.MessageBox]::Show('За выбранный период нет telemetry samples для экспорта.', 'VPS Control Center', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
                }
            }
            catch {
                [System.Windows.Forms.MessageBox]::Show("Ошибка экспорта CSV.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
            }
        }
        $dlg.Dispose()
    })
    $cmbObsModule.Add_SelectedIndexChanged({ if (-not $script:LoadingConfig) { Refresh-Observation } })
    $cmbObsPeriod.Add_SelectedIndexChanged({ if (-not $script:LoadingConfig) { Refresh-Observation } })
    $btnEventsRefresh.Add_Click({ Refresh-Events })
    $cmbEventsFilter.Add_SelectedIndexChanged({ Refresh-Events })
    $btnEventsCopy.Add_Click({
        try {
            if ($gridEvents.SelectedRows.Count -gt 0) {
                $r = $gridEvents.SelectedRows[0]
                $text = "Время: $($r.Cells['Время'].Value)`r`nТип: $($r.Cells['Тип'].Value)`r`nСервис: $($r.Cells['Сервис'].Value)`r`nСобытие: $($r.Cells['Событие'].Value)`r`nПодробности: $($r.Cells['Подробности'].Value)"
                [System.Windows.Forms.Clipboard]::SetText($text)
            }
        }
        catch { }
    })

    $btnBrowsersApply.Add_Click({
        Set-BrowserQuickGrid 'YandexBrowser' ([bool]$chkYandexVps.Checked)
        Set-BrowserQuickGrid 'Edge' ([bool]$chkEdgeVps.Checked)
        $cfg=Get-ConfigFromGrid
        if (Save-ConfigSnapshot $cfg) { Start-EngineAction 'Apply' }
    })

    $btnStrictApply.Add_Click({
        try {
            foreach ($item in @(@{Module='YandexBrowser';Check=$chkYandexStrict},@{Module='Edge';Check=$chkEdgeStrict})) {
                $desired=[bool]$item.Check.Checked; $module=[string]$item.Module
                $status=Invoke-StrictBrowserHelper 'Status' $module; $healthy=($status.Output -match 'Healthy=True'); $exists=($status.Output -match 'Exists=True')
                if (($desired -and -not $healthy) -or (-not $desired -and $exists)) {
                    $strictAction=if($desired){'Enable'}else{'Disable'}; $rc=Invoke-StrictBrowserHelper $strictAction $module
                    if ($rc -ne 0) { throw "Не удалось изменить строгий режим $module (код $rc)." }
                }
                if ($desired) { Set-BrowserQuickGrid $module $true; if($module -eq 'YandexBrowser'){$chkYandexVps.Checked=$true}else{$chkEdgeVps.Checked=$true} }
            }
            $script:CustomSettings.StrictYandex=[bool]$chkYandexStrict.Checked; $script:CustomSettings.StrictEdge=[bool]$chkEdgeStrict.Checked; Save-CustomSettings $script:CustomSettings
            $cfg=Get-ConfigFromGrid; if(Save-ConfigSnapshot $cfg){ Set-ConfigDirty $false; [void](Start-EngineAction 'Apply') }
            $lblStrictStatus.Text='Строгая защита применена. Для включённых браузеров исходящий UDP заблокирован отдельным firewall-правилом; TCP направляется через VPS.'; $lblStrictStatus.ForeColor=[System.Drawing.Color]::DarkGreen
        } catch { [System.Windows.Forms.MessageBox]::Show("Не удалось применить строгий режим.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null }
    })
    $btnYandexStrictLaunch.Add_Click({ try { Start-StrictBrowser 'YandexBrowser' } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Строгий запуск Яндекс Браузера','OK','Warning')|Out-Null } })
    $btnEdgeStrictLaunch.Add_Click({ try { Start-StrictBrowser 'Edge' } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Строгий запуск Microsoft Edge','OK','Warning')|Out-Null } })

    $lstVpsProfiles.Add_SelectedIndexChanged({ $id=Get-SelectedVpsProfileId; if ($id) { Load-VpsProfileEditor $id } })
    $btnVpsNew.Add_Click({
        $txtVpsName.Tag=''; $txtVpsName.Text='Новый VPS'; $txtVpsHost.Text=''; $numVpsPort.Value=22; $txtVpsUser.Text='root'; $txtVpsExit.Text=''; $cmbVpsAuth.SelectedItem='IP / логин / пароль'; $txtVpsSession.Text=''; $txtVpsKey.Text=''; $txtVpsPassword.Text=''; $chkRememberVpsPassword.Checked=$true; $lblVpsSecretState.Text='Введите пароль и сохраните профиль.'; $lblVpsSecretState.ForeColor=[System.Drawing.Color]::DimGray; Update-VpsAuthUi
    })
    $btnVpsSave.Add_Click({ [void](Save-VpsEditor) })
    $btnVpsDelete.Add_Click({
        $id=Get-SelectedVpsProfileId; if (-not $id) { return }
        $p=Get-VpsProfileById $id
        if ([System.Windows.Forms.MessageBox]::Show("Удалить профиль «$([string]$p.Name)»? Зашифрованный пароль этого профиля также будет удалён.",'VPS Control Center','YesNo','Warning') -eq [System.Windows.Forms.DialogResult]::Yes) {
            try { Remove-VpsProfile $id; Refresh-VpsProfileList } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'VPS Control Center','OK','Error')|Out-Null }
        }
    })
    $btnVpsActivate.Add_Click({
        $p=Save-VpsEditor; if (-not $p) { return }
        try {
            if (-not (Test-VpsPreflightReady ([string]$p.Id))) { throw 'Нужна свежая предпроверка PASS именно для текущих параметров этого профиля (не старше 15 минут).' }
            $current = Get-ActiveVpsProfile
            $previousId = if ($current) { [string]$current.Id } else { '' }
            if ($previousId -eq [string]$p.Id) {
                $answer=[System.Windows.Forms.MessageBox]::Show("«$([string]$p.Name)» уже активен. Повторно применить его SOCKS/маршрутизацию?",'VPS Control Center','YesNo','Question')
            } else {
                $answer=[System.Windows.Forms.MessageBox]::Show("Предпроверка PASS. Переключить активный VPS на «$([string]$p.Name)» и сейчас переподнять SOCKS/маршрутизацию?`r`n`r`nПри ошибке Apply V7 вернёт метаданные активного VPS к предыдущему профилю. Unmatched traffic Windows остаётся DIRECT.",'VPS Control Center','YesNo','Question')
            }
            if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }
            if ($previousId -ne [string]$p.Id) {
                [void](Set-ActiveVpsProfile ([string]$p.Id))
                $script:PendingVpsSwitch=[pscustomobject]@{PreviousId=$previousId;NewId=[string]$p.Id;Name=[string]$p.Name}
            }
            Refresh-VpsProfileList ([string]$p.Id)
            if (-not (Start-EngineAction 'Apply')) {
                if ($script:PendingVpsSwitch -and $previousId) { Restore-ActiveVpsProfile $previousId; $script:PendingVpsSwitch=$null; Refresh-VpsProfileList $previousId }
            }
        } catch { [System.Windows.Forms.MessageBox]::Show("Не удалось активировать VPS.`r`n`r`n$($_.Exception.Message)",'VPS Control Center','OK','Error')|Out-Null }
    })
    $btnVpsKeyBrowse.Add_Click({
        $dlg=New-Object System.Windows.Forms.OpenFileDialog; $dlg.Filter='PuTTY private key (*.ppk)|*.ppk|Все файлы (*.*)|*.*'; $dlg.CheckFileExists=$true
        if($txtVpsKey.Text -and (Test-Path -LiteralPath $txtVpsKey.Text)){ $dlg.InitialDirectory=Split-Path -Parent $txtVpsKey.Text }
        if($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$txtVpsKey.Text=$dlg.FileName}; $dlg.Dispose()
    })
    $btnPageantStart.Add_Click({
        if($Demo){ [System.Windows.Forms.MessageBox]::Show('Демо-режим: запуск Pageant отключён.','VPS Control Center','OK','Information')|Out-Null; return }
        try { $pageant=Get-PageantPath; if(-not $pageant){throw 'pageant.exe не найден рядом с PuTTY или в PATH.'}; Start-Process -FilePath $pageant|Out-Null; $lblPageantState.Text='Pageant запущен/уже доступен.'; $lblPageantState.ForeColor=[System.Drawing.Color]::DarkGreen } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Pageant','OK','Error')|Out-Null }
    })
    $btnPageantLoad.Add_Click({
        if($Demo){ [System.Windows.Forms.MessageBox]::Show('Демо-режим: загрузка ключа в Pageant отключена.','VPS Control Center','OK','Information')|Out-Null; return }
        try { $pageant=Get-PageantPath; if(-not $pageant){throw 'pageant.exe не найден.'}; $key=([string]$txtVpsKey.Text).Trim(); if(-not $key -or -not(Test-Path -LiteralPath $key)){throw 'Сначала выберите существующий .ppk-файл.'}; Start-Process -FilePath $pageant -ArgumentList @($key)|Out-Null; $lblPageantState.Text='Команда загрузки ключа передана Pageant. Для ключа с passphrase подтвердите её в окне Pageant.'; $lblPageantState.ForeColor=[System.Drawing.Color]::DarkGreen } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Pageant','OK','Error')|Out-Null }
    })
    $btnVpsOpenSsh.Add_Click({ $p=Save-VpsEditor; if ($p) { Start-VpsManagerAction 'OpenSsh' ([string]$p.Id) } })
    $btnVpsTest.Add_Click({ $p=Save-VpsEditor; if ($p) { [void](Start-VpsManagerAction 'Test' ([string]$p.Id)) } })
    $btnVpsHealth.Add_Click({ $p=Save-VpsEditor; if($p){ Start-VpsManagerAction 'Health' ([string]$p.Id) } })
    $btnVpsDiagnose.Add_Click({ $p=Save-VpsEditor; if ($p) { [void](Start-VpsManagerAction 'Diagnose' ([string]$p.Id)) } })
    $btnVpsPlan.Add_Click({ $p=Save-VpsEditor; if ($p) { [void](Start-VpsManagerAction 'PlanPackages' ([string]$p.Id)) } })
    $btnVpsInstallBase.Add_Click({
        $p=Save-VpsEditor; if (-not $p) { return }; $id=[string]$p.Id
        if ([System.Windows.Forms.MessageBox]::Show('Установить на выбранный VPS только базовые диагностические пакеты?`r`n`r`nБудет обновлён индекс пакетов, но upgrade ОС, SSH/firewall/sysctl и маршруты не изменяются. Требуется root или passwordless sudo.','VPS Control Center','YesNo','Warning') -eq [System.Windows.Forms.DialogResult]::Yes) { Start-VpsManagerAction 'InstallBaseline' $id }
    })
    $btnVpsInstallMon.Add_Click({
        $p=Save-VpsEditor; if (-not $p) { return }; $id=[string]$p.Id
        if ([System.Windows.Forms.MessageBox]::Show('Добавить пакеты наблюдения sysstat/vnstat/iotop, если они доступны?`r`n`r`nСетевые и SSH-настройки не меняются. Требуется root или passwordless sudo.','VPS Control Center','YesNo','Warning') -eq [System.Windows.Forms.DialogResult]::Yes) { Start-VpsManagerAction 'InstallMonitoring' $id }
    })

    $btnBrowseExe.Add_Click({
        $dlg = New-Object System.Windows.Forms.OpenFileDialog
        $dlg.Filter = 'Исполняемые файлы (*.exe)|*.exe|Все файлы (*.*)|*.*'
        $dlg.CheckFileExists = $true
        $dlg.Multiselect = $false
        if ($txtCustomExe.Text -and (Test-Path -LiteralPath $txtCustomExe.Text)) { $dlg.InitialDirectory = Split-Path -Parent $txtCustomExe.Text }
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $txtCustomExe.Text = $dlg.FileName }
        $dlg.Dispose()
    })
    $btnSaveCustom.Add_Click({ [void](Save-CustomRulesFromUi) })
    $btnVmRefresh.Add_Click({ Refresh-VmAdapterList; Refresh-VmGatewayStatus })
    $cmbVmAdapter.Add_SelectedIndexChanged({ Refresh-VmGatewayStatus })
    $numVmPort.Add_ValueChanged({ Refresh-VmGatewayStatus })
    $btnVmEnable.Add_Click({
        $choice = Get-SelectedVmChoice
        if (-not $choice) { [System.Windows.Forms.MessageBox]::Show('Не выбран vEthernet IPv4.', 'VPS Control Center', 'OK', 'Warning') | Out-Null; return }
        $vmPort=[int]$numVmPort.Value
        $connectPort=Get-V7RoutingTunnelPort;$connectId=Get-V7RoutingTunnelSelection;$confirm="Будет изменена конфигурация Windows:`r`n`r`n• TCP portproxy: $([string]$choice.Address):$vmPort → 127.0.0.1:$connectPort ($connectId)`r`n• входящее firewall-правило только для $([string]$choice.Alias) / LocalSubnet`r`n• default route Windows и VM не меняется`r`n`r`nПродолжить?"
        if([System.Windows.Forms.MessageBox]::Show($confirm,'VPS Control Center','YesNo','Warning') -ne [System.Windows.Forms.DialogResult]::Yes){return}
        try {
            $script:CustomSettings.VmInterfaceAlias = [string]$choice.Alias
            $script:CustomSettings.VmListenAddress = [string]$choice.Address
            $script:CustomSettings.VmListenPort = [int]$numVmPort.Value
            Save-CustomSettings $script:CustomSettings
            $r = Invoke-VmGatewayChild -Action Install -InterfaceAlias ([string]$choice.Alias) -ListenAddress ([string]$choice.Address) -ListenPort ([int]$numVmPort.Value) -ConnectPort $connectPort -Elevated
            if ($r.ExitCode -ne 0) { throw "Elevated helper завершился кодом $($r.ExitCode)." }
            Refresh-VmGatewayStatus
        }
        catch { [System.Windows.Forms.MessageBox]::Show("Не удалось включить шлюз VM.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', 'OK', 'Error') | Out-Null }
    })
    $btnVmDisable.Add_Click({
        $choice = Get-SelectedVmChoice
        if (-not $choice) { return }
        $vmPort=[int]$numVmPort.Value
        $confirm="Удалить только созданные VPS Control V7 portproxy/firewall для $([string]$choice.Address):$vmPort?`r`n`r`nДругие правила и маршруты Windows не изменяются."
        if([System.Windows.Forms.MessageBox]::Show($confirm,'VPS Control Center','YesNo','Question') -ne [System.Windows.Forms.DialogResult]::Yes){return}
        try {
            $r = Invoke-VmGatewayChild -Action Remove -InterfaceAlias ([string]$choice.Alias) -ListenAddress ([string]$choice.Address) -ListenPort $vmPort -ConnectPort (Get-V7RoutingTunnelPort) -Elevated
            if ($r.ExitCode -ne 0) { throw "Elevated helper завершился кодом $($r.ExitCode)." }
            Refresh-VmGatewayStatus
        }
        catch { [System.Windows.Forms.MessageBox]::Show("Не удалось отключить шлюз VM.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', 'OK', 'Error') | Out-Null }
    })
    $btnVmCopy.Add_Click({
        $choice = Get-SelectedVmChoice
        if ($choice) {
            [System.Windows.Forms.Clipboard]::SetText("SOCKS5 $($choice.Address):$([int]$numVmPort.Value)")
            $lblVmStatus.Text = "Адрес SOCKS5 $($choice.Address):$([int]$numVmPort.Value) скопирован. В VM задайте его только тем приложениям, которым нужен VPS."
        }
    })

    $btnEngineAutostart.Add_Click({
        try {
            $answer = [System.Windows.Forms.MessageBox]::Show(
                'Обновить системный autostart движка на V6.5? Появится UAC-запрос. Если задача уже существует, она будет обновлена тем же именем.',
                'VPS Control Center',
                [System.Windows.Forms.MessageBoxButtons]::YesNo,
                [System.Windows.Forms.MessageBoxIcon]::Question
            )
            if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }
            $rc = Invoke-EngineElevatedAction 'InstallAutostart'
            if ($rc -ne 0) { throw "Установка autostart завершилась кодом $rc." }
            Refresh-EngineAutostartStatus
        }
        catch { [System.Windows.Forms.MessageBox]::Show("Не удалось обновить autostart движка.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', 'OK', 'Error') | Out-Null }
    })

    foreach ($control in @(
        $btnSave,$btnSaveApply,$btnReloadConfig,$btnApply,$btnDirect,$btnRestart,
        $btnBrowsersApply,$btnStrictApply,$btnYandexStrictLaunch,$btnEdgeStrictLaunch,
        $btnVpsNew,$btnVpsDelete,$btnVpsSave,$btnVpsActivate,$btnVpsOpenSsh,$btnVpsTest,$btnVpsHealth,$btnVpsDiagnose,$btnVpsPlan,$btnVpsInstallBase,$btnVpsInstallMon,
        $gridRoutes,$chkYandexVps,$chkEdgeVps,$chkYandexStrict,$chkEdgeStrict,
        $lstVpsProfiles,$txtVpsName,$txtVpsHost,$numVpsPort,$txtVpsUser,$txtVpsExit,$cmbVpsAuth,$txtVpsSession,$txtVpsPassword,$chkRememberVpsPassword,$txtVpsKey,$btnVpsKeyBrowse,$btnPageantStart,$btnPageantLoad,
        $btnVmEnable,$btnVmDisable,$btnEngineAutostart,$btnKSave,$btnKSsh,$btnKProbe,$btnEStatus,$btnERefresh,$btnEUpgrade,$btnEReady,$btnConsistency
    )) { if ($control) { [void]$script:BusyControls.Add($control) } }
    Update-UiBusyState

    $gridRoutes.Add_CurrentCellDirtyStateChanged({
        if ($gridRoutes.IsCurrentCellDirty) { [void]$gridRoutes.CommitEdit([System.Windows.Forms.DataGridViewDataErrorContexts]::Commit) }
    })
    $gridRoutes.Add_CellValueChanged({ param($sender,$e)
        if ($script:LoadingConfig -or $e.RowIndex -lt 0 -or $e.ColumnIndex -lt 0) { return }
        try { if ($gridRoutes.Columns[$e.ColumnIndex].Name -eq 'Режим') { Set-ConfigDirty $true } } catch { }
    })
    $cmbVpsAuth.Add_SelectedIndexChanged({ if (-not $script:LoadingConfig) { Update-VpsAuthUi } })
    $gridRoutes.Add_DataError({ param($sender,$e) $e.ThrowException = $false })

    $chkAutostart.Add_CheckedChanged({
        if ($script:LoadingConfig) { return }
        [void](Set-UiAutostart -Enabled ([bool]$chkAutostart.Checked) -BaseDir $PSScriptRoot)
    })

    $chkTrayNotifications.Add_CheckedChanged({
        if ($script:SuppressSettingsEvents) { return }
        $script:UiSettings.TrayNotifications = [bool]$chkTrayNotifications.Checked
        [void](Save-UiSettings $script:UiSettings)
    })

    $cmbRefreshInterval.Add_SelectedIndexChanged({
        if ($script:SuppressSettingsEvents) { return }
        $seconds = switch ([string]$cmbRefreshInterval.SelectedItem) {
            '5 сек' { 5 }
            '10 сек' { 10 }
            '30 сек' { 30 }
            default { 3 }
        }
        $script:UiSettings.AutoRefreshSeconds = $seconds
        if ($timer) { $timer.Interval = $seconds * 1000 }
        [void](Save-UiSettings $script:UiSettings)
    })

    $tabs.Add_SelectedIndexChanged({
        if ($tabs.SelectedTab -eq $tabObs) { Refresh-Observation }
        elseif ($tabs.SelectedTab -eq $tabEvents) { Refresh-Events }
        elseif ($tabs.SelectedTab -eq $tabVps) { Refresh-VpsProfileList (Get-SelectedVpsProfileId) }
    })

    $miOpen.Add_Click({ Show-ControlCenter })
    $miRefresh.Add_Click({ Refresh-UiStatus })
    $miApply.Add_Click({
        if($script:ConfigDirty){
            $answer=[Windows.Forms.MessageBox]::Show('Есть несохранённые изменения в открытом интерфейсе. Из tray будет применена ранее сохранённая конфигурация, не текущая таблица. Продолжить?','VPS Control Center','YesNo','Warning')
            if($answer -ne [Windows.Forms.DialogResult]::Yes){return}
        }
        [void](Start-EngineAction 'Apply')
    })
    $miDirect.Add_Click({ if([System.Windows.Forms.MessageBox]::Show('Временно перевести управляемые сервисы на DIRECT?','VPS Control Center','YesNo','Question') -eq [System.Windows.Forms.DialogResult]::Yes){[void](Start-EngineAction 'Direct')} })
    $miRestart.Add_Click({ Write-V7SocksTrace 'USER_ACTION' 'Tray: Перезапустить VCC SOCKS 1081'; Write-V7SocksSnapshot 'tray-restart-click'; [void](Start-EngineAction 'RestartTunnel') })
    $miSelfTest.Add_Click({ [void](Start-EngineAction 'SelfTest') })
    $miState.Add_Click({ Start-Process explorer.exe -ArgumentList "`"$StateDir`"" })
    $miExit.Add_Click({
        if (Test-UiOperationBusy) { [System.Windows.Forms.MessageBox]::Show('Дождитесь завершения текущей операции перед закрытием интерфейса. Маршрутизация продолжает работать независимо.', 'VPS Control Center', 'OK', 'Information')|Out-Null; return }
        if ($script:ConfigDirty) {
            $answer=[System.Windows.Forms.MessageBox]::Show('Есть несохранённые изменения маршрутов. Закрыть интерфейс и отбросить их? Сохранённая маршрутизация продолжит работать.','VPS Control Center','YesNo','Warning')
            if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }
        }
        $script:AllowExit = $true
        $tray.Visible = $false
        $form.Close()
    })
    $tray.Add_DoubleClick({ Show-ControlCenter })

    $form.KeyPreview = $true
    $form.Add_KeyDown({ param($sender,$e)
        if ($e.KeyCode -eq [System.Windows.Forms.Keys]::F5) { Refresh-UiStatus; $e.SuppressKeyPress=$true }
        elseif ($e.Control -and $e.KeyCode -eq [System.Windows.Forms.Keys]::S) { $btnSave.PerformClick(); $e.SuppressKeyPress=$true }
        elseif ($e.Control -and $e.KeyCode -eq [System.Windows.Forms.Keys]::Enter) { $btnSaveApply.PerformClick(); $e.SuppressKeyPress=$true }
    })

    $form.Add_FormClosing({
        param($sender, $e)
        if (-not $script:AllowExit) {
            $e.Cancel = $true
            $form.Hide()
            $tray.ShowBalloonTip(1600, 'VPS Control Center', 'Интерфейс скрыт. Маршрутизация продолжает работать.', [Windows.Forms.ToolTipIcon]::Info)
        }
    })

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = [int]$script:UiSettings.AutoRefreshSeconds * 1000
    $timer.Add_Tick({
        try {
            Complete-EngineActionIfNeeded
            Complete-VpsManagerActionIfNeeded
            Complete-KeeneticActionIfNeeded
            Refresh-UiStatus
            Invoke-V7RuntimeRecoveryIfNeeded
            Invoke-V7DeepTelemetryTick
            if ($tabs.SelectedTab -eq $tabObs) {
                if (((Get-Date) - $script:LastObservationRefresh).TotalSeconds -ge 15) { Refresh-Observation }
            }
            elseif ($tabs.SelectedTab -eq $tabEvents) {
                if (((Get-Date) - $script:LastEventsRefresh).TotalSeconds -ge 15) { Refresh-Events }
            }
            if (-not $script:LongOperationWarned) {
                $started = if ($script:EngineProcess) { $script:EngineStartedAt } elseif ($script:VpsProcess) { $script:VpsStartedAt } else { $null }
                if ($started -and ((Get-Date)-$started).TotalMinutes -ge 10) {
                    $script:LongOperationWarned=$true
                    Write-UiLog 'Operation has been running for >=10 minutes; process is left intact.'
                    $lblOperation.Text='Операция выполняется более 10 минут. Она не прервана; подробности смотрите в соответствующей вкладке.'
                    $lblOperation.ForeColor=[System.Drawing.Color]::DarkOrange
                }
            }
        }
        catch { Write-UiLog "UI timer tick failed but UI remains alive: $($_.Exception.Message)" }
    })
    $timer.Start()

    $script:LoadingConfig = $true
    try {
        Refresh-VmAdapterList
        Refresh-VmGatewayStatus
        Refresh-VpsProfileList
        Update-VpsAuthUi
        Refresh-EngineAutostartStatus
        Load-ConfigIntoGrid
        Refresh-UiStatus
        Refresh-Observation
        Refresh-Events
    }
    finally { $script:LoadingConfig = $false }
    Write-UiLog "V7 UI start version=$UiVersion engine=$EngineVersion charts=$script:ChartsAvailable packageIntegrity=PASS"
    Write-V7SocksTrace 'UI_START' ("version=$UiVersion engine=$EngineVersion dataRoot=$([string]$StorageLayout.Root) stateDir=$StateDir")
    Write-V7SocksSnapshot 'ui-start'
    Initialize-V7DeepTelemetry

    if ($StartHidden) { $form.Add_Shown({ $form.Hide() }) }
    $startupRecoveryTimer=New-Object System.Windows.Forms.Timer
    $startupRecoveryTimer.Interval=1500
    $startupRecoveryTimer.Add_Tick({$startupRecoveryTimer.Stop();try{Invoke-V7RuntimeRecoveryIfNeeded -Startup}finally{$startupRecoveryTimer.Dispose()}})
    $startupRecoveryTimer.Start()
    [System.Windows.Forms.Application]::Run($form)
}
finally {
    try { if ($tray) { $tray.Visible = $false; $tray.Dispose() } } catch { }
    try { if ($uiAcquired -and $uiMutex) { $uiMutex.ReleaseMutex() } } catch { }
    try { if ($uiMutex) { $uiMutex.Dispose() } } catch { }
}
