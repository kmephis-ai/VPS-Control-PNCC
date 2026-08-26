#requires -Version 5.1
# VPS Control Center dynamic internal consistency module. Static declaration <-> implementation consistency model.

function Get-V7CapabilityRegistry {
    return @(
        [pscustomobject]@{Id='DUAL_TUNNEL_CONTROL';Name='Dual-tunnel control';State='IMPLEMENTED';Ui='Статус / Туннели';Safety='GUARDED';Truth='1081 PRIMARY_AUTO; 1080 RESERVE_MANUAL. Shared visibility/diagnostics; automatic lifecycle only for 1081.'},
        [pscustomobject]@{Id='SELECTIVE_ROUTING';Name='Выборочная маршрутизация Windows';State='IMPLEMENTED';Ui='Статус';Safety='GUARDED';Truth='V6.5 генерируется из внешнего V6.3.1; unmatched traffic остаётся DIRECT.'},
        [pscustomobject]@{Id='STATUS_CENTER';Name='Единый Status Center';State='IMPLEMENTED';Ui='Статус';Safety='READ_ONLY';Truth='Агрегирует runtime/evidence; не выполняет mutation.'},
        [pscustomobject]@{Id='OBSERVABILITY';Name='Наблюдение и события';State='IMPLEMENTED';Ui='Наблюдение / События';Safety='READ_ONLY';Truth='Telemetry/history/events без изменения маршрута.'},
        [pscustomobject]@{Id='DIAGNOSTICS';Name='Диагностика и support snapshot';State='IMPLEMENTED';Ui='Диагностика';Safety='READ_ONLY';Truth='Readiness, self-test, sanitized snapshot и consistency check.'},
        [pscustomobject]@{Id='DEEP_TELEMETRY';Name='Continuous Evidence / deep telemetry';State='IMPLEMENTED';Ui='Диагностика';Safety='READ_ONLY';Truth='30-second lightweight UI telemetry + asynchronous background forensic evidence; heavy CIM/socket/hash/EventLog collection never runs on WinForms timer.'},
        [pscustomobject]@{Id='FUNCTIONAL_CONSISTENCY';Name='Проверка заявлено ↔ реализовано';State='IMPLEMENTED';Ui='Диагностика';Safety='READ_ONLY';Truth='Сверяет version/docs/manifest/module wiring/helper actions и fail-closed блокирует startup при обязательной ошибке.'},
        [pscustomobject]@{Id='STRICT_BROWSER';Name='Строгая маршрутизация браузеров';State='IMPLEMENTED';Ui='Дополнительно';Safety='GUARDED_MUTATION';Truth='Process-scoped TCP + firewall UDP block + --disable-quic; требует UAC для firewall.'},
        [pscustomobject]@{Id='MULTI_VPS';Name='Multi-VPS manager';State='IMPLEMENTED';Ui='VPS-серверы';Safety='GUARDED_MUTATION';Truth='Профили, health/preflight, switch rollback metadata, SSH operations.'},
        [pscustomobject]@{Id='VM_GATEWAY';Name='Выборочный SOCKS-шлюз Hyper-V';State='IMPLEMENTED';Ui='Дополнительно';Safety='GUARDED_MUTATION';Truth='Конкретный vEthernet address; no default-route/full VPN.'},
        [pscustomobject]@{Id='KEENETIC_PROBE';Name='Keenetic router probe';State='IMPLEMENTED';Ui='Keenetic';Safety='READ_ONLY';Truth='ICMP/TCP/HTTP probe, cumulative evidence.'},
        [pscustomobject]@{Id='ENTWARE_STATUS';Name='Entware inventory/status';State='IMPLEMENTED';Ui='Keenetic';Safety='READ_ONLY';Truth='SSH read-only inventory; DPAPI credential required for password auth.'},
        [pscustomobject]@{Id='ENTWARE_REFRESH';Name='Entware repository refresh';State='IMPLEMENTED';Ui='Keenetic';Safety='CONFIRMED_MUTATION';Truth='opkg update only, guarded by saved credential and inventory precondition.'},
        [pscustomobject]@{Id='ENTWARE_UPGRADE';Name='Entware package upgrade';State='IMPLEMENTED';Ui='Keenetic';Safety='CONFIRMED_MUTATION';Truth='opkg update + upgrade, guarded by confirmation and fresh installed-state evidence.'},
        [pscustomobject]@{Id='ENTWARE_INSTALL_REMOVE';Name='Entware install/remove';State='BLOCKED';Ui='Keenetic / План';Safety='FAIL_CLOSED';Truth='Readiness/transaction plan only; mutation intentionally absent until runtime evidence.'},
        [pscustomobject]@{Id='PORTABLE_STORAGE';Name='Portable V7 storage';State='IMPLEMENTED';Ui='Настройки';Safety='GUARDED';Truth='Расположение можно менять с copy-forward; старые данные автоматически не удаляются.'},
        [pscustomobject]@{Id='SAFE_BACKUP';Name='Безопасная резервная копия';State='IMPLEMENTED';Ui='Настройки';Safety='GUARDED';Truth='DPAPI secrets, password/private-key-like files исключаются из обычной backup/support копии.'},
        [pscustomobject]@{Id='DEMO';Name='Изолированный demo mode';State='IMPLEMENTED';Ui='VPS-Control-v7-demo.cmd';Safety='NO_REAL_MUTATION';Truth='Synthetic evidence; network/system mutations blocked.'}
    )
}

function Get-V7TextSafe([string]$Path) {
    try { if(Test-Path -LiteralPath $Path -PathType Leaf){ return [IO.File]::ReadAllText($Path) } } catch { }
    return ''
}


function Get-V7FirstNonEmptyLine([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return '' }
    foreach ($line in @($Text -split "`r?`n")) {
        if (-not [string]::IsNullOrWhiteSpace([string]$line)) {
            return ([string]$line).Trim()
        }
    }
    return ''
}

function Test-V7FunctionalConsistency {
    param(
        [Parameter(Mandatory=$true)][string]$BaseDir,
        [Parameter(Mandatory=$true)][string]$UiVersion,
        [Parameter(Mandatory=$true)][string[]]$ModuleNames
    )
    $errors=New-Object Collections.ArrayList
    $warnings=New-Object Collections.ArrayList
    $checks=New-Object Collections.ArrayList
    function Add-Check([string]$Id,[bool]$Pass,[string]$Detail,[bool]$Required=$true){
        [void]$checks.Add([pscustomobject]@{Id=$Id;Pass=$Pass;Required=$Required;Detail=$Detail})
        if(-not $Pass){ if($Required){[void]$errors.Add("${Id}: $Detail")}else{[void]$warnings.Add("${Id}: $Detail")} }
    }

    $main=Join-Path $BaseDir 'VPS-Control-v7.ps1'
    $launcher=Join-Path $BaseDir 'VPS-Control-v7-launch.ps1'
    $keen=Join-Path $BaseDir 'VPS-Control-v7-keenetic.ps1'
    $vps=Join-Path $BaseDir 'VPS-Control-v7-vps-manager.ps1'
    $strict=Join-Path $BaseDir 'VPS-Control-v7-browser-strict.ps1'
    $vm=Join-Path $BaseDir 'VPS-Control-v7-vm-gateway.ps1'
    $manifest=Join-Path $BaseDir 'VPS-Control-v7-SHA256.txt'
    $readme=Join-Path $BaseDir 'VPS-Control-v7-README.txt'
    $arch=Join-Path $BaseDir 'VPS-Control-v7-ARCHITECTURE.md'
    $truth=Join-Path $BaseDir 'VPS-Control-v7-CAPABILITY-TRUTH.md'
    $tunnelContract=Join-Path $BaseDir 'VPS-Control-v7-TUNNEL-CONTRACT.json'
    $tunnelManager=Join-Path $BaseDir 'VPS-Control-v7-tunnel-manager.ps1'
    $tunnelModule=Join-Path $BaseDir 'modules\V7-Tunnels.ps1'
    $requiredFiles = @(
        [pscustomobject]@{ Id='MAIN'; Path=$main },
        [pscustomobject]@{ Id='LAUNCHER'; Path=$launcher },
        [pscustomobject]@{ Id='EVIDENCE_WORKER'; Path=(Join-Path $BaseDir 'VPS-Control-v7-evidence-worker.ps1') },
        [pscustomobject]@{ Id='KEENETIC_HELPER'; Path=$keen },
        [pscustomobject]@{ Id='VPS_HELPER'; Path=$vps },
        [pscustomobject]@{ Id='STRICT_BROWSER_HELPER'; Path=$strict },
        [pscustomobject]@{ Id='VM_GATEWAY_HELPER'; Path=$vm },
        [pscustomobject]@{ Id='MANIFEST'; Path=$manifest },
        [pscustomobject]@{ Id='README'; Path=$readme },
        [pscustomobject]@{ Id='ARCHITECTURE'; Path=$arch },
        [pscustomobject]@{ Id='CAPABILITY_TRUTH'; Path=$truth },
        [pscustomobject]@{ Id='TUNNEL_CONTRACT'; Path=$tunnelContract },
        [pscustomobject]@{ Id='TUNNEL_MANAGER'; Path=$tunnelManager },
        [pscustomobject]@{ Id='TUNNEL_MODEL'; Path=$tunnelModule }
    )
    foreach($pair in $requiredFiles){
        Add-Check ('FILE_'+$pair.Id) (Test-Path -LiteralPath $pair.Path -PathType Leaf) $pair.Path $true
    }
    $mainText=Get-V7TextSafe $main;$launchText=Get-V7TextSafe $launcher;$keenText=Get-V7TextSafe $keen;$vpsText=Get-V7TextSafe $vps;$strictText=Get-V7TextSafe $strict;$vmText=Get-V7TextSafe $vm;$readmeText=Get-V7TextSafe $readme;$archText=Get-V7TextSafe $arch;$truthText=Get-V7TextSafe $truth;$maintenanceText=Get-V7TextSafe (Join-Path $BaseDir 'modules\V7-Maintenance.ps1');$runtimeText=Get-V7TextSafe (Join-Path $BaseDir 'modules\V7-Runtime.ps1');$readinessText=Get-V7TextSafe (Join-Path $BaseDir 'modules\V7-Readiness.ps1');$keenModelText=Get-V7TextSafe (Join-Path $BaseDir 'modules\V7-KeeneticModel.ps1');$engineUpgradeText=Get-V7TextSafe (Join-Path $BaseDir 'VPS-Control-v7-engine-upgrade.ps1');$deepTelemetryText=Get-V7TextSafe (Join-Path $BaseDir 'modules\V7-DeepTelemetry.ps1');$observabilityText=Get-V7TextSafe (Join-Path $BaseDir 'modules\V7-Observability.ps1');$evidenceWorkerText=Get-V7TextSafe (Join-Path $BaseDir 'VPS-Control-v7-evidence-worker.ps1');$tunnelManagerText=Get-V7TextSafe $tunnelManager;$tunnelModuleText=Get-V7TextSafe $tunnelModule;$tunnelContractText=Get-V7TextSafe $tunnelContract;$consistencyText=Get-V7TextSafe (Join-Path $BaseDir 'modules\V7-Consistency.ps1')
    $versionUpper = $UiVersion.ToUpperInvariant()
    $readmeFirst = Get-V7FirstNonEmptyLine $readmeText
    $archFirst = Get-V7FirstNonEmptyLine $archText
    $truthFirst = Get-V7FirstNonEmptyLine $truthText
    Add-Check 'VERSION_MAIN' ($mainText -match [regex]::Escape("`$UiVersion = '$UiVersion'")) "main должен объявлять $UiVersion" $true
    Add-Check 'VERSION_LAUNCHER' ($launchText -match [regex]::Escape("`$LauncherVersion = '$UiVersion'")) "launcher должен объявлять LauncherVersion=$UiVersion" $true
    Add-Check 'VERSION_README' (($readmeFirst.ToUpperInvariant()).Contains($versionUpper)) "первая непустая строка README должна объявлять текущий $UiVersion" $true
    Add-Check 'VERSION_ARCH' (($archFirst.ToUpperInvariant()).Contains($versionUpper)) "первая непустая строка Architecture должна объявлять текущий $UiVersion" $true
    Add-Check 'VERSION_TRUTH' (($truthFirst.ToUpperInvariant()).Contains($versionUpper)) "первая непустая строка Capability Truth должна объявлять текущий $UiVersion" $true
    Add-Check 'TRUTH_INSTALL_BLOCKED' (($truthText -match 'ENTWARE_INSTALL_REMOVE') -and ($truthText -match 'BLOCKED')) 'Capability Truth должен явно фиксировать install/remove как BLOCKED' $true
    # These are literal source-wiring checks, not regex problems.  Using Contains avoids
    # drive-letter/backslash interpolation (for example X:\Example) leaking into a regex.
    $packageIntegrityWiring = $maintenanceText.Contains('function Test-PackageIntegrity') -and $maintenanceText.Contains("Join-Path `$BaseDir 'VPS-Control-v7-SHA256.txt'") -and $mainText.Contains('Test-PackageIntegrity -BaseDir $PSScriptRoot')
    Add-Check 'PACKAGE_INTEGRITY_BASEDIR' $packageIntegrityWiring 'package integrity должна получать корень пакета явно, а не использовать PSScriptRoot модуля' $true
    $autostartWiring = $runtimeText.Contains('Get-RunCommand([string]$BaseDir)') -and $runtimeText.Contains("Join-Path `$BaseDir 'VPS-Control-v7-launch.ps1'") -and $mainText.Contains('-BaseDir $PSScriptRoot')
    Add-Check 'AUTOSTART_BASEDIR' $autostartWiring 'автозапуск должен ссылаться на launcher в корне пакета, а не в modules' $true
    $hasNestedTupleArrays = (($mainText -match '@\s*\(\s*@\s*\(') -or ($maintenanceText -match '@\s*\(\s*@\s*\('))
    Add-Check 'NO_NESTED_TUPLE_ARRAYS' (-not $hasNestedTupleArrays) 'nested tuple arrays не должны использоваться там, где ожидается список записей; используйте PSCustomObject' $true
    $paddingTypeOk = (-not $mainText.Contains('Drawing.Padding')) -and $mainText.Contains('System.Windows.Forms.Padding')
    Add-Check 'UI_PADDING_NAMESPACE' $paddingTypeOk 'Padding относится к System.Windows.Forms; Drawing.Padding недопустим и ломает WinForms runtime' $true
    $allPsText = (@(Get-ChildItem -LiteralPath $BaseDir -Recurse -Filter '*.ps1' -File -ErrorAction SilentlyContinue | ForEach-Object { Get-V7TextSafe $_.FullName }) -join "`n")
    $hostCollision = (($allPsText -match '(?im)^\s*\$Host\s*=') -or ($allPsText -match '(?im)\[[A-Za-z0-9_.]+\]\s*\$Host\b'))
    Add-Check 'NO_HOST_AUTOMATIC_VARIABLE_COLLISION' (-not $hostCollision) 'PowerShell $Host — read-only automatic variable; параметры/присваивания с именем Host запрещены' $true
    $freshnessWiring = $runtimeText.Contains('Get-V7RuntimeEvidenceAgeSeconds') -and $runtimeText.Contains('STALE_RUNTIME') -and $mainText.Contains('-RuntimeAgeSeconds $runtimeAge')
    Add-Check 'RUNTIME_FRESHNESS_TRUTH' $freshnessWiring 'устаревший runtime должен маркироваться как evidence, а не отображаться как текущее состояние маршрутов' $true
    $puttyDiscoveryOk=$readinessText.Contains('Get-V7LegacyPuttyPath') -and $readinessText.Contains("Join-Path `$legacyPuttyDir 'plink.exe'")
    Add-Check 'READINESS_LEGACY_PUTTY_DISCOVERY' $puttyDiscoveryOk 'readiness должна видеть portable PuTTY/plink из неизменяемого V6.3.1 так же, как runtime helpers' $true
    $localPuttyFirst=$readinessText.Contains("PuTTY PORTABLE\putty_portable.exe") -and $engineUpgradeText.Contains('V7PuttyDiscoveryCandidates') -and $engineUpgradeText.Contains('PUTTY_DISCOVERY') -and $vpsText.Contains("PuTTY PORTABLE\putty_portable.exe") -and $keenText.Contains("PuTTY PORTABLE\putty_portable.exe")
    Add-Check 'LOCAL_PUTTY_FIRST' $localPuttyFirst 'colocated PuTTY PORTABLE рядом с V7 должен иметь приоритет над историческим абсолютным PuttyPath' $true
    $deepTelemetryWiring=$mainText.Contains('V7-DeepTelemetry.ps1') -and $mainText.Contains('Invoke-V7DeepTelemetryTick') -and $mainText.Contains('Полный лог / метрики') -and $mainText.Contains('operation-evidence.jsonl') -and $deepTelemetryText.Contains('Write-V7OperationEvidence') -and $deepTelemetryText.Contains('Start-V7EvidenceWorker') -and $evidenceWorkerText.Contains('BACKGROUND FORENSIC EVIDENCE')
    Add-Check 'DEEP_TELEMETRY_WIRING' $deepTelemetryWiring 'lightweight runtime metrics + async background forensic evidence должны быть подключены к main UI' $true
    $utf8Tail=$runtimeText.Contains('Read-TextFileSmart $Path')
    Add-Check 'DEBUG_EXPORT_UTF8' $utf8Tail 'diagnostic exports должны читать UTF-8 logs через smart decoder без mojibake PowerShell 5.1' $true
    $inventorySnapshotOk=$keenModelText.Contains('foreach($p in @($obj.Keys))')
    Add-Check 'KEENETIC_INVENTORY_KEY_SNAPSHOT' $inventorySnapshotOk 'накопительный inventory должен перечислять snapshot ключей, иначе OrderedDictionary может падать «Коллекция была изменена»' $true
    $nativePlinkTruthOk=$vpsText.Contains("`$ErrorActionPreference='Continue'") -and $keenText.Contains("`$ErrorActionPreference='Continue'") -and $vpsText.Contains('$rc=[int]$LASTEXITCODE') -and $keenText.Contains('$rc=[int]$LASTEXITCODE')
    Add-Check 'NATIVE_PLINK_EXIT_TRUTH' $nativePlinkTruthOk 'VPS/Keenetic helpers должны читать реальный LASTEXITCODE plink и не выдавать NativeCommandError за rc=0' $true
    Add-Check 'VPS_SAVED_SESSION_CREDENTIAL_TRUTH' ($vpsText.Contains('Test-SavedSessionNonPasswordAuth') -and $vpsText.Contains('SavedSession не имеет сохранённого DPAPI-пароля')) 'VPS helper SavedSession не должен молча уходить в password prompt/неясный plink failure без credential truth' $true
    $runtimeRecoveryOk=$mainText.Contains('function Invoke-V7RuntimeRecoveryIfNeeded') -and $mainText.Contains('function Schedule-V7RuntimeRecovery') -and $mainText.Contains('$delays=@(30,60,120,300)') -and $mainText.Contains('Invoke-V7RuntimeRecoveryIfNeeded -Startup') -and $mainText.Contains('Invoke-V7RuntimeRecoveryIfNeeded')
    Add-Check 'BOUNDED_RUNTIME_RECOVERY_BACKOFF' $runtimeRecoveryOk 'при сохранённых AUTO/VPS отсутствующий SOCKS/watchdog должен восстанавливаться повторяемо, но с ограниченным backoff без tight loop' $true
    $savedSessionContract=$engineUpgradeText.Contains('Get-V7SavedSessionEndpoint') -and $engineUpgradeText.Contains('SAVED_SESSION_METADATA') -and $engineUpgradeText.Contains('CREDENTIAL_REQUIRED') -and $engineUpgradeText.Contains('Get-EffectivePuttyPassword')
    Add-Check 'PORTABLE_PUTTY_SLASH_SESSION_FORMAT' (
        $engineUpgradeText.Contains('Get-V7PortableSlashValue') -and
        $engineUpgradeText.Contains("Name 'PortNumber'") -and
        $engineUpgradeText.Contains("SLASH_FILE")
    ) 'portable PuTTY session parser должен поддерживать file backend Name\value\ для HostName/PortNumber/Protocol/PublicKeyFile' $true

    Add-Check 'ENGINE_SAVED_SESSION_SOCKS_CONTRACT' $savedSessionContract 'SavedSession должен использоваться как источник endpoint/auth metadata для explicit tunnel; automatic lifecycle остаётся только у PRIMARY_AUTO 1081' $true
    $portableSavedSessionCompat = ($engineUpgradeText.Contains('Get-V7PortablePuttySessionInfo') -and $engineUpgradeText.Contains('Get-V7ManagedPuttyExecutable') -and $engineUpgradeText.Contains("'-D'") -and $engineUpgradeText.Contains('${SocksHost}:$SocksPort') -and -not $engineUpgradeText.Contains('arguments = @(''-load'',$PuttySession)'))
    Add-Check 'PORTABLE_PUTTY_SAVED_SESSION_COMPAT' $portableSavedSessionCompat 'portable SavedSession не должен запускаться через -load; VCC создаёт explicit D1081' $true
    Add-Check 'GUI_PUTTY_NO_BATCH' (-not $engineUpgradeText.Contains('$arguments += ''-batch''') -and $engineUpgradeText.Contains('guiPuttyBatch=false')) 'GUI PuTTY/putty_portable никогда не должен получать Plink-only -batch' $true
    Add-Check 'DEEP_TELEMETRY_ASYNC_WORKER' ($deepTelemetryText.Contains('Start-V7EvidenceWorker') -and $evidenceWorkerText.Contains('VPSControlV7EvidenceWorker') -and $mainText.Contains('Фоновый сбор полного диагностического лога запущен')) 'тяжёлый forensic evidence должен выполняться вне WinForms timer в отдельном worker' $true
    Add-Check 'PERIODIC_TELEMETRY_LIGHTWEIGHT' ($deepTelemetryText.Contains("DetailLevel='LIGHT'") -and $deepTelemetryText.Contains('TotalSeconds -lt 30') -and -not $deepTelemetryText.Contains('Save-V7EnvironmentEvidence -Reason')) 'периодическая UI telemetry должна быть лёгкой и не выполнять environment/CIM/socket forensic scan' $true
    Add-Check 'EVIDENCE_WORKER_AST' ($launchText.Contains('VPS-Control-v7-evidence-worker.ps1')) 'evidence worker должен входить в launcher AST preflight' $true

    Add-Check 'UI_OPERATION_COMPLETION_LEASE' ($mainText.Contains('$engineBusy = [bool]$script:EngineProcess') -and $mainText.Contains('reason=RECOVERY_IN_FLIGHT')) 'operation lease должен жить до обработки результата child process и запрещать overlapping Apply/recovery' $true
    Add-Check 'PROXIFIER_APPLICATION_LIST_GRAMMAR' (
        $engineUpgradeText.Contains('<Applications>putty.exe;putty_portable.exe;plink.exe;proxifier.exe</Applications>') -and
        $engineUpgradeText.Contains("}) -join ';'") -and
        $engineUpgradeText.Contains(".Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;')") -and
        -not $engineUpgradeText.Contains('[System.Security.SecurityElement]::Escape($appToken)')
    ) 'generated Proxifier Applications lists должны использовать semicolon без surrounding whitespace и literal quotes для whitespace filenames' $true

    Add-Check 'PROXIFIER_LOAD_LIFECYCLE_OWNERSHIP' (
        $engineUpgradeText.Contains('$replacements[''Invoke-ProxifierRawLoad'']') -and
        $engineUpgradeText.Contains('WaitForExit(3500)') -and
        $engineUpgradeText.Contains('PROXIFIER_LOAD_HELPER_STUCK_CLEANUP') -and
        $engineUpgradeText.Contains('primaryBefore') -and
        $engineUpgradeText.Contains('ParentProcessId -eq $PID')
    ) 'silent-load helper lifecycle должен быть bounded и ownership-verified' $true

    $dualContractOk=$false
    try{
        $dc=$tunnelContractText|ConvertFrom-Json
        $p=@($dc.Tunnels|Where-Object{[string]$_.Id -eq 'PRIMARY_AUTO'}|Select-Object -First 1)
        $r=@($dc.Tunnels|Where-Object{[string]$_.Id -eq 'RESERVE_MANUAL'}|Select-Object -First 1)
        $dualContractOk=(
            $p.Count -eq 1 -and $r.Count -eq 1 -and
            [int]$p[0].Port -eq 1081 -and [string]$p[0].LifecycleMode -eq 'AUTO' -and [bool]$p[0].AutoStart -and [bool]$p[0].AutoRecovery -and
            [int]$r[0].Port -eq 1080 -and [string]$r[0].LifecycleMode -eq 'MANUAL_ONLY' -and
            -not [bool]$r[0].AutoStart -and -not [bool]$r[0].AutoRecovery -and -not [bool]$r[0].AutoStop -and
            [bool]$dc.AllCurrentAndFutureCapabilitiesApplyToBothTunnels -and
            [bool]$dc.ReserveManualOwnershipPolicy.ExternallyStartedReserveMayBeAdopted -and
            [bool]$dc.ReserveManualOwnershipPolicy.RouteSelectionRequiresExpectedIdentity -and
            [bool]$dc.ReserveManualOwnershipPolicy.AutomaticLifecycleRemainsForbidden -and
            [string]$dc.ManagedPuttyHostKeyTrust.Mode -eq 'PORTABLE_TRUST_TO_OFFICIAL_REGISTRY' -and
            [string]$dc.ManagedPuttyHostKeyTrust.RegistryConflict -eq 'FAIL_CLOSED_NO_OVERWRITE' -and
            -not [bool]$dc.ManagedPuttyHostKeyTrust.UnknownHostKeyAcceptanceAllowed -and
            -not [bool]$dc.ManagedPuttyHostKeyTrust.HostKeyVerificationDisableAllowed -and
            [string]$dc.CredentialTransport.PuttyArgument -eq '-pwfile' -and
            -not [bool]$dc.CredentialTransport.PlaintextPwArgumentAllowed -and
            [string]$dc.CredentialTransport.AclApplication -eq 'FILE_SECURITY_AT_CREATION' -and
            -not [bool]$dc.CredentialTransport.SetAclPostCreationAllowed -and
            -not [bool]$dc.CredentialTransport.CloudSyncedTemporaryStorageAllowed
        )
    }catch{}
    Add-Check 'DUAL_TUNNEL_ARCHITECTURE_CONTRACT' $dualContractOk 'machine-readable contract: 1081=PRIMARY_AUTO; 1080=RESERVE_MANUAL; shared capability scope with lifecycle exception' $true

    Add-Check 'DUAL_TUNNEL_UI_VISIBILITY' (
        $mainText.Contains("SOCKS 1081 · основной AUTO") -and
        $mainText.Contains("SOCKS 1080 · резерв ручной") -and
        $mainText.Contains('$tabTunnels.Text = ''Туннели''') -and
        $mainText.Contains('Start-V7TunnelManagerAction')
    ) 'UI должен постоянно отображать оба tunnel и иметь явные manual controls для 1080' $true

    Add-Check 'RESERVE_1080_MANUAL_ONLY_LIFECYCLE' (
        $tunnelManagerText.Contains("[ValidateSet('Status','StartReserve','StopReserve','TestReserve','SelectPrimaryRoute','SelectReserveRoute')]") -and
        $tunnelManagerText.Contains('$ReservePort=1080') -and
        $tunnelManagerText.Contains('$ReserveId=''RESERVE_MANUAL''') -and
        -not $runtimeText.Contains('StartReserve') -and
        -not $engineUpgradeText.Contains('StartReserve')
    ) '1080 start/stop должны существовать только как явные manual actions; watchdog/recovery engine не должен иметь StartReserve' $true

    Add-Check 'RESERVE_EXTERNAL_MANUAL_ADOPTION' (
        $tunnelManagerText.Contains('function Get-ReserveOwnership') -and
        $tunnelManagerText.Contains("Mode='VCC_MANUAL_EXPLICIT'") -and
        $tunnelManagerText.Contains("Mode='USER_MANUAL_SAVEDSESSION'") -and
        $tunnelManagerText.Contains("Mode='USER_MANUAL_EXTERNAL_VERIFIED'") -and
        $tunnelManagerText.Contains("matching-saved-session") -and
        $tunnelManagerText.Contains("putty-family+expected-identity") -and
        $tunnelManagerText.Contains("ownershipMode=")
    ) 'already running user-managed PuTTY reserve 1080 must be safely adoptable without granting automatic lifecycle authority' $true

    Add-Check 'DUAL_TUNNEL_TELEMETRY' (
        $deepTelemetryText.Contains('$tunnels=Get-V7TunnelLightMatrix') -and
        $deepTelemetryText.Contains('Tunnels=@($tunnels)') -and
        $deepTelemetryText.Contains('RoutingTunnelId=$routingTunnelId') -and
        $runtimeText.Contains('tunnel.primary.id=PRIMARY_AUTO') -and
        $runtimeText.Contains('tunnel.reserve.id=RESERVE_MANUAL') -and
        $runtimeText.Contains("Source='PORTABLE_SLASH_FILE'") -and
        $evidenceWorkerText.Contains('@(1080,1081,3000)') -and
        $tunnelModuleText.Contains("Id='PRIMARY_AUTO'") -and
        $tunnelModuleText.Contains("Id='RESERVE_MANUAL'")
    ) 'telemetry/diagnostics/evidence должны учитывать оба endpoint, routing selection и portable SavedSession metadata' $true

    Add-Check 'MANUAL_TUNNEL_ROUTE_SELECTION' (
        $tunnelManagerText.Contains('SelectPrimaryRoute') -and
        $tunnelManagerText.Contains('SelectReserveRoute') -and
        $tunnelManagerText.Contains("AutomaticFailoverAllowed=`$false") -and
        $engineUpgradeText.Contains('function Get-V7RoutingProxyId') -and
        $engineUpgradeText.Contains("if(`$id -eq 'RESERVE_MANUAL')") -and
        $engineUpgradeText.Contains('return 101') -and
        $engineUpgradeText.Contains('return 100') -and
        $mainText.Contains("'SelectReserveRoute'") -and
        $mainText.Contains("'SelectPrimaryRoute'")
    ) 'все VPS routing rules должны вручную выбирать proxy 100/1081 или 101/1080; automatic failover запрещён' $true

    Add-Check 'VM_GATEWAY_DUAL_TUNNEL_SOURCE' (
        $mainText.Contains('ConnectPort=(Get-V7RoutingTunnelPort)') -and
        $mainText.Contains('-ConnectPort (Get-V7RoutingTunnelPort)') -and
        $vmText.Contains('[int]$ConnectPort = 1081')
    ) 'VM gateway должен подключаться к вручную выбранному tunnel 1081/1080, не меняя его lifecycle' $true

    Add-Check 'PROXIFIER_DUAL_TUNNEL_PROXY_REGISTRY' (
        $engineUpgradeText.Contains('<Proxy id="100" type="SOCKS5">') -and
        $engineUpgradeText.Contains('<Port>1081</Port>') -and
        $engineUpgradeText.Contains('<Proxy id="101" type="SOCKS5">') -and
        $engineUpgradeText.Contains('<Port>1080</Port>')
    ) 'generated Proxifier profile должен объявлять primary proxy 100/1081 и reserve proxy 101/1080; default rules остаются на primary до явного manual route selection' $true

    Add-Check 'MANAGED_PUTTY_HOSTKEY_TRUST_BRIDGE' (
        $engineUpgradeText.Contains('function Ensure-V7OfficialPuttyHostKeyTrust') -and
        $engineUpgradeText.Contains("HKCU:\Software\SimonTatham\PuTTY\SshHostKeys") -and
        $engineUpgradeText.Contains("FAIL conflict=true") -and
        $engineUpgradeText.Contains("ABORT hostkey-trust-not-proven") -and
        $tunnelManagerText.Contains('function Ensure-V7OfficialPuttyHostKeyTrust') -and
        $tunnelManagerText.Contains("Trusted SSH host key for active VPS is not available in official PuTTY store.") -and
        -not $engineUpgradeText.Contains('-hostkey *') -and
        -not $engineUpgradeText.Contains('accept-new') -and
        -not $engineUpgradeText.Contains('hostkey verification disabled')
    ) 'official PuTTY must receive only already-trusted active-VPS host keys from portable cache; conflicts fail closed; verification is never disabled' $true

    Add-Check 'PUTTY_PWFILE_ACL_AT_CREATION' (
        $engineUpgradeText.Contains("Join-Path `$env:LOCALAPPDATA 'VPS-Control-v6.3\secure-credentials'") -and
        $engineUpgradeText.Contains('New-Object -TypeName IO.FileStream -ArgumentList $streamArgs') -and
        $engineUpgradeText.Contains('[Security.AccessControl.FileSystemRights]::Modify') -and
        $engineUpgradeText.Contains('$fileSecurity.SetAccessRuleProtection($true,$false)') -and
        $engineUpgradeText.Contains("New-Object Security.Principal.SecurityIdentifier('S-1-5-18')") -and
        $engineUpgradeText.Contains('AreAccessRulesProtected') -and
        -not $engineUpgradeText.Contains('Set-Acl -LiteralPath $dir') -and
        -not $engineUpgradeText.Contains('Set-Acl -LiteralPath $path') -and
        -not $engineUpgradeText.Contains('.SetOwner(') -and
        $tunnelManagerText.Contains("Join-Path `$env:LOCALAPPDATA 'VPS-Control-v6.3\secure-credentials'") -and
        $tunnelManagerText.Contains('New-Object -TypeName IO.FileStream -ArgumentList $streamArgs') -and
        -not $tunnelManagerText.Contains('Set-Acl -LiteralPath $dir') -and
        -not $tunnelManagerText.Contains('Set-Acl -LiteralPath $path')
    ) 'temporary PuTTY password files must use creation-time FileSecurity in LOCALAPPDATA; post-create Set-Acl/SetOwner and cloud temp storage are forbidden' $true

    Add-Check 'PUTTY_PASSWORD_NOT_IN_COMMAND_LINE' (
        $engineUpgradeText.Contains("'-pwfile'") -and
        $engineUpgradeText.Contains('Test-V7PuttyPwFileSupport') -and
        $engineUpgradeText.Contains('New-V7SecurePuttyPasswordFile') -and
        $engineUpgradeText.Contains('Remove-V7SecurePuttyPasswordFile') -and
        -not $engineUpgradeText.Contains('$arguments+=@(''-pw'',$password)') -and
        $tunnelManagerText.Contains("'-pwfile'") -and
        -not $tunnelManagerText.Contains('''-pw'',$password')
    ) 'DPAPI password должен передаваться PuTTY через ACL-protected temporary -pwfile; plaintext -pw fallback запрещён' $true

    Add-Check 'VCC_SOCKS_STOP_OWNERSHIP' (
        $engineUpgradeText.Contains('$replacements[''Stop-TunnelProcess'']') -and
        $engineUpgradeText.Contains('STOP_VCC_SOCKS') -and
        $engineUpgradeText.Contains('LocalPort $SocksPort') -and
        $engineUpgradeText.Contains('не доказанным как VCC-managed tunnel')
    ) 'Stop/restart должен иметь ownership guard и работать только с `$SocksPort` generated as 1081' $true

    $unsafeMarkerInterpolation=$false
    foreach($line in @($consistencyText -split "`r?`n")){
        if($line -match '\.Contains\(".*\$[A-Za-z_][A-Za-z0-9_]*.*"\)'){
            # Existing intentionally escaped markers use backtick before the variable.
            $candidate=$Matches[0]
            if($candidate -match '(?<!`)\$[A-Za-z_][A-Za-z0-9_]*'){$unsafeMarkerInterpolation=$true;break}
        }
    }
    Add-Check 'CONSISTENCY_MARKER_STRICTMODE_SAFE' (-not $unsafeMarkerInterpolation) 'V7-Consistency marker strings must not expand undefined variables under Set-StrictMode' $true

    $unsafeGeneratedVariableColon = [regex]::IsMatch(
        $engineUpgradeText,
        '\$(?!(?:env|script|global|local|private|using):)[A-Za-z_][A-Za-z0-9_]*:'
    )
    Add-Check 'GENERATED_ENGINE_VARIABLE_COLON_SAFE' (
        -not $unsafeGeneratedVariableColon
    ) 'generated-engine templates не должны содержать bare `$Variable:`; перед colon требуется `${Variable}`' $true

    $automaticVariableAssignmentUnsafe=[regex]::IsMatch(
        $engineUpgradeText,
        '(?im)^\s*\$(?:PID|Host)\s*='
    )
    Add-Check 'GENERATED_ENGINE_AUTOMATIC_VARIABLE_ASSIGNMENT_SAFE' (
        -not $automaticVariableAssignmentUnsafe -and
        $engineUpgradeText.Contains('$listenerPid=[int]$conn.OwningProcess')
    ) 'generated-engine templates не должны присваивать read-only automatic variables `$PID/`$Host; listener owner использует `$listenerPid`' $true

    Add-Check 'VCC_SOCKS_CROSS_PROCESS_MUTATION_MUTEX' (
        $engineUpgradeText.Contains("VccSocksMutationMutexName = 'Local\VPSControl-VCC-SOCKS-1081'") -and
        $engineUpgradeText.Contains("Write-V7SocksEngineTrace 'MUTATION_LOCK'") -and
        $engineUpgradeText.Contains('WaitOne([TimeSpan]::FromSeconds(60))') -and
        $engineUpgradeText.Contains('Critical re-check INSIDE the cross-process lock')
    ) 'UI recovery и watchdog repair должны сериализовать mutation 1081 через один named mutex и повторно проверять identity внутри lock' $true

    Add-Check 'ENGINE_LOGICAL_FAIL_TRUTH' ($mainText.Contains('ENGINE_LOGICAL_FAILURE') -and $mainText.Contains('$logicalFailure')) 'native rc=0 не должен считаться успехом, если engine output содержит явный [FAIL]' $true
    $diagLayoutOk=$mainText.Contains('$diagStatus = New-Object System.Windows.Forms.TableLayoutPanel') -and $mainText.Contains('$diagStatus.Controls.Add($btnCopyOutput,2,0)')
    Add-Check 'DIAGNOSTICS_ACTION_BAR_LAYOUT' $diagLayoutOk 'кнопки «Журнал V7» и «Копировать вывод» должны иметь отдельные layout-ячейки и не перекрываться' $true
    $engineTunnelTraceOk=$engineUpgradeText.Contains("'PUTTY_START'") -and $engineUpgradeText.Contains('transport=PuTTY') -and $engineUpgradeText.Contains('source=$source') -and $engineUpgradeText.Contains('vccSocks=${SocksHost}:$SocksPort')
    Add-Check 'ENGINE_TUNNEL_START_TRACE' $engineTunnelTraceOk 'сгенерированный V6.5 должен явно сообщать transport, source/profile и VCC SOCKS endpoint при запуске' $true
    $detailedSocksTraceOk=$runtimeText.Contains('function Write-V7SocksTrace') -and $runtimeText.Contains('function New-V7SocksDebugReport') -and $mainText.Contains('Собрать лог SOCKS') -and $mainText.Contains('Write-V7SocksSnapshot')
    Add-Check 'DETAILED_SOCKS_RUNTIME_TRACE' $detailedSocksTraceOk 'V7 должен автоматически писать подробный sanitized trace и иметь кнопку экспорта единого SOCKS debug report' $true
    $engineDetailedTraceOk=$engineUpgradeText.Contains('Write-V7SocksEngineTrace') -and $engineUpgradeText.Contains('$replacements[''Ensure-SocksTunnel'']') -and $engineUpgradeText.Contains('PUTTY_PROCESS') -and $engineUpgradeText.Contains('ENSURE_WAIT')
    Add-Check 'DETAILED_SOCKS_ENGINE_TRACE' $engineDetailedTraceOk 'генерируемый V6.5 должен трассировать credential source, saved session, PuTTY process lifecycle, listener wait и итог Ensure-SocksTunnel без секретов' $true
    $traceRedactionOk=$runtimeText.Contains('<redacted>') -and $engineUpgradeText.Contains('<redacted>') -and $runtimeText.Contains('SecretsIncluded=false')
    Add-Check 'SOCKS_TRACE_SECRET_REDACTION' $traceRedactionOk 'SOCKS diagnostics должны редактировать credential arguments (-pw legacy/-pwfile path) и не включать DPAPI/private key contents' $true
    $recoveryDecisionTraceOk=$mainText.Contains('RECOVERY_EVAL') -and $mainText.Contains('RECOVERY_SKIP') -and $mainText.Contains('RECOVERY_HEALTH') -and $mainText.Contains('RECOVERY_TRIGGER')
    Add-Check 'SOCKS_RECOVERY_DECISION_TRACE' $recoveryDecisionTraceOk 'каждое решение автоподъёма SOCKS должно оставлять explainable trace: eval/skip/health/trigger' $true
    $remoteEndpointTraceOk=$engineUpgradeText.Contains('SSH_ENDPOINT') -and $engineUpgradeText.Contains('Test-V7RemoteTcpEndpoint') -and $engineUpgradeText.Contains('PUTTY_BINARY')
    Add-Check 'SOCKS_REMOTE_ENDPOINT_TRACE' $remoteEndpointTraceOk 'generated V6.5 должен логировать доступность SSH endpoint и идентичность запускаемого PuTTY binary' $true

    $registryIds=@(Get-V7CapabilityRegistry | ForEach-Object {[string]$_.Id})
    # Capability Truth supports both the canonical table and an explicit current-RC delta declaration
    # (`CAPABILITY_ID` — ...). This prevents a newly introduced capability from being invisible merely
    # because its current declaration lives above the preserved historical table.
    $truthIdMatches = New-Object Collections.ArrayList
    foreach($m in [regex]::Matches($truthText,'(?m)^\|\s*`([A-Z0-9_]+)`\s*\|')){[void]$truthIdMatches.Add($m.Groups[1].Value)}
    foreach($m in [regex]::Matches($truthText,'(?m)^`([A-Z0-9_]+)`\s+—')){[void]$truthIdMatches.Add($m.Groups[1].Value)}
    $truthIds=@($truthIdMatches | Select-Object -Unique)
    foreach($id in $registryIds){Add-Check ('TRUTH_CAP_'+$id) ($truthIds -contains $id) "Capability Truth не содержит registry capability $id" $true}
    foreach($id in $truthIds){Add-Check ('REGISTRY_CAP_'+$id) ($registryIds -contains $id) "Capability Truth заявляет $id, которого нет в runtime registry" $true}

    $moduleFiles=@(Get-ChildItem -LiteralPath (Join-Path $BaseDir 'modules') -Filter '*.ps1' -File -ErrorAction SilentlyContinue)
    foreach($mf in $moduleFiles){
        $rel='modules\'+$mf.Name
        Add-Check ('LAUNCH_AST_'+$mf.BaseName) ($launchText -match [regex]::Escape($rel)) "launcher AST-list не содержит $rel" $true
        Add-Check ('MAIN_MODULE_'+$mf.BaseName) ($mainText -match [regex]::Escape($rel)) "main helper-list/path не содержит $rel" $true
    }

    $keenAllowed=@()
    if($keenText -match "ValidateSet\(([^\)]*)\)"){$keenAllowed=@([regex]::Matches($Matches[1],"'([^']+)'")|ForEach-Object{$_.Groups[1].Value})}
    $keenCalls=@([regex]::Matches($mainText,"Start-KeeneticAction\s+'([^']+)'")|ForEach-Object{$_.Groups[1].Value}|Select-Object -Unique)
    foreach($a in $keenCalls){Add-Check ('KEENETIC_ACTION_'+$a) ($keenAllowed -contains $a) "GUI вызывает '$a', которого нет в helper ValidateSet" $true}
    Add-Check 'KEENETIC_NO_INSTALL_MUTATION' (-not (@($keenAllowed) -contains 'Install') -and -not (@($keenAllowed) -contains 'Remove')) 'Keenetic helper не должен содержать Install/Remove mutation actions' $true
    $hostKeyFlow=((@($keenAllowed) -contains 'HostKeyProbe') -and ($mainText -match "Start-KeeneticAction\s+'HostKeyProbe'") -and $keenText.Contains('HOSTKEY_FINGERPRINT=') -and $keenText.Contains("'-hostkey'") -and $mainText.Contains('Save-KeeneticHostKey'))
    Add-Check 'KEENETIC_HOSTKEY_TRUST_FLOW' $hostKeyFlow 'Keenetic automation должна получать fingerprint без password prompt, явно подтверждать его в UI и использовать pinned -hostkey' $true
    Add-Check 'KEENETIC_PLAN_MARKER' ($keenText -match 'MUTATION=BLOCKED_RUNTIME_EVIDENCE_REQUIRED') 'readiness helper должен выводить fail-closed marker' $true
    Add-Check 'LEGACY_FALLBACK_STABLE' (($mainText -match 'EngineSourcePath.*Action Menu') -and ($mainText -match 'Открыть консоль V6\.3\.1')) 'кнопка fallback должна запускать внешний stable EngineSourcePath, а не generated V6.5' $true

    $vpsAllowed=@()
    if($vpsText -match "ValidateSet\(([^\)]*)\)"){$vpsAllowed=@([regex]::Matches($Matches[1],"'([^']+)'")|ForEach-Object{$_.Groups[1].Value})}
    $vpsCalls=@([regex]::Matches($mainText,"Start-VpsManagerAction\s+'([^']+)'")|ForEach-Object{$_.Groups[1].Value}|Select-Object -Unique)
    foreach($a in $vpsCalls){Add-Check ('VPS_ACTION_'+$a) ($vpsAllowed -contains $a) "GUI вызывает '$a', которого нет в VPS helper ValidateSet" $true}

    $strictAllowed=@()
    if($strictText -match "ValidateSet\(([^\)]*)\)"){$strictAllowed=@([regex]::Matches($Matches[1],"'([^']+)'")|ForEach-Object{$_.Groups[1].Value})}
    foreach($a in @('Status','Enable','Disable')){
        Add-Check ('STRICT_ACTION_'+$a) ($strictAllowed -contains $a) "Strict Browser helper не содержит обязательное действие $a" $true
    }
    Add-Check 'STRICT_GUI_WIRING' ($mainText.Contains("Invoke-StrictBrowserHelper 'Status'") -and $mainText.Contains("if(`$desired){'Enable'}else{'Disable'}")) 'GUI строгого режима должен быть связан с Status/Enable/Disable helper actions' $true

    $vmAllowed=@()
    if($vmText -match "ValidateSet\(([^\)]*)\)"){$vmAllowed=@([regex]::Matches($Matches[1],"'([^']+)'")|ForEach-Object{$_.Groups[1].Value})}
    foreach($a in @('Status','Install','Remove')){
        Add-Check ('VM_ACTION_'+$a) (($vmAllowed -contains $a) -and ($mainText -match ("Invoke-VmGatewayChild\s+-Action\s+"+[regex]::Escape($a)))) "VM Gateway UI/helper contract не содержит действие $a" $true
    }

    Add-Check 'KEENETIC_DPAPI_GUARD' (($mainText -match "EntwareStatus','EntwareRefresh','EntwareUpgrade") -and ($mainText -match 'KeeneticSecretFile')) 'автоматические Entware SSH actions должны требовать сохранённый DPAPI secret' $true
    Add-Check 'KEENETIC_PINNED_HOSTKEY_GUARD' ($keenText.Contains('EntwareHostKey') -and $keenText.Contains("'-hostkey'")) 'автоматический Entware SSH должен быть привязан к подтверждённому fingerprint, а не зависеть от интерактивного registry cache PuTTY' $true
    Add-Check 'KEENETIC_FRESH_EVIDENCE_GUARD' (($mainText -match 'LastEntwareAt') -and ($mainText -match 'TotalHours') -and ($mainText -match '24')) 'Entware mutations должны требовать свежий installed-state evidence' $true
    Add-Check 'KEENETIC_NOT_INSTALLED_IS_STATE' ($keenText -match "echo 'ENTWARE=NOT_DETECTED'[\s\S]{0,80}exit 0") 'EntwareStatus: NOT_DETECTED должен быть валидным состоянием, а не техническим failure' $true

    foreach($m in @($ModuleNames)){
        Add-Check ('ROUTE_MODULE_'+$m) ($mainText -match ("'"+[regex]::Escape($m)+"'")) "main не содержит routing module $m" $true
    }

    # Manifest coverage: only immutable distributable files are checked. Runtime data, external V6.3.1 and generated V6.5 are intentionally outside the package manifest.
    $manifestText=Get-V7TextSafe $manifest
    $packageFiles=New-Object Collections.ArrayList
    foreach($f in @(Get-ChildItem -LiteralPath $BaseDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'VPS-Control-v7*' -or $_.Name -eq 'VPS-Control-v6.5-modules.json' })){
        if($f.FullName -ne $manifest){[void]$packageFiles.Add($f)}
    }
    foreach($f in @(Get-ChildItem -LiteralPath (Join-Path $BaseDir 'modules') -Filter '*.ps1' -File -ErrorAction SilentlyContinue)){[void]$packageFiles.Add($f)}
    foreach($f in @($packageFiles)){
        $rel=$f.FullName.Substring($BaseDir.Length).TrimStart([char[]]@('\','/')).Replace('/','\')
        Add-Check ('MANIFEST_'+($rel -replace '[^A-Za-z0-9]','_')) ($manifestText -match [regex]::Escape($rel)) "manifest не содержит $rel" $true
    }

    $caps=@(Get-V7CapabilityRegistry)
    return [pscustomobject]@{
        SchemaVersion=1;GeneratedAt=(Get-Date).ToString('o');UiVersion=$UiVersion;
        Ok=($errors.Count -eq 0);Errors=@($errors);Warnings=@($warnings);Checks=@($checks);Capabilities=$caps;
        Summary=[pscustomobject]@{Checks=$checks.Count;Passed=@($checks|Where-Object{$_.Pass}).Count;Errors=$errors.Count;Warnings=$warnings.Count;Implemented=@($caps|Where-Object{$_.State -eq 'IMPLEMENTED'}).Count;Blocked=@($caps|Where-Object{$_.State -eq 'BLOCKED'}).Count}
    }
}

function Format-V7FunctionalConsistencyText($Result) {
    if(-not $Result){return 'Проверка связанности недоступна.'}
    $lines=New-Object Collections.ArrayList
    [void]$lines.Add('=== ПРОВЕРКА СВЯЗАННОСТИ VPS CONTROL CENTER ===')
    [void]$lines.Add("Версия: $([string]$Result.UiVersion)")
    [void]$lines.Add("Результат: $(if($Result.Ok){'PASS'}else{'FAIL'}) · checks=$([int]$Result.Summary.Passed)/$([int]$Result.Summary.Checks) · errors=$([int]$Result.Summary.Errors) · warnings=$([int]$Result.Summary.Warnings)")
    [void]$lines.Add('')
    if(@($Result.Errors).Count -gt 0){[void]$lines.Add('ОШИБКИ:');foreach($x in @($Result.Errors)){[void]$lines.Add(' - '+[string]$x)};[void]$lines.Add('')}
    if(@($Result.Warnings).Count -gt 0){[void]$lines.Add('ПРЕДУПРЕЖДЕНИЯ:');foreach($x in @($Result.Warnings)){[void]$lines.Add(' - '+[string]$x)};[void]$lines.Add('')}
    [void]$lines.Add('CAPABILITY TRUTH:')
    foreach($c in @($Result.Capabilities)){[void]$lines.Add((' - {0}: {1} · {2} · UI: {3}' -f [string]$c.Name,[string]$c.State,[string]$c.Safety,[string]$c.Ui))}
    return (@($lines)-join "`r`n")
}
