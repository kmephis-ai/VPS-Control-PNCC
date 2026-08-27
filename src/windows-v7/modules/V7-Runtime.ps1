#requires -Version 5.1
# VPS Control Center RC14.11 internal module. Dot-sourced by VPS-Control-v7.ps1.

function Test-TcpListener([string]$HostName, [int]$Port, [int]$TimeoutMs = 250) {
    if($Demo -and $HostName -eq '127.0.0.1' -and $Port -eq 1081){ return $true }
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) { return $false }
        $client.EndConnect($iar)
        return $true
    }
    catch { return $false }
    finally { try { $client.Close() } catch { } }
}

function Get-WatchdogUiStatus {
    if($Demo){ return [pscustomobject]@{State='RUNNING';Detail='ДЕМО · PID 4242 · сигнал 8 с назад';Fresh=$true;Pid=4242;HeartbeatAge=8} }
    $result = [pscustomobject]@{ State = 'OFF'; Detail = 'PID отсутствует'; Fresh = $false; Pid = 0; HeartbeatAge = -1 }
    if (-not (Test-Path -LiteralPath $WatchdogPidFile)) { return $result }
    try {
        $watchPid = [int](Get-Content -LiteralPath $WatchdogPidFile -Raw).Trim()
        $result.Pid = $watchPid
        $process = Get-Process -Id $watchPid -ErrorAction SilentlyContinue
        if (-not $process) {
            $result.Detail = "устаревший PID $watchPid"
            return $result
        }
        $result.State = 'RUNNING'
        $result.Detail = "PID=$watchPid"
        if (Test-Path -LiteralPath $WatchdogHeartbeatFile) {
            $age = [int]((Get-Date) - (Get-Item -LiteralPath $WatchdogHeartbeatFile).LastWriteTime).TotalSeconds
            $result.HeartbeatAge = $age
            if ($age -le 240) {
                $result.Fresh = $true
                $result.Detail += ", сигнал ${age} с назад"
            }
            else {
                $result.State = 'STALE'
                $result.Detail += ", сигнал устарел: ${age} с"
            }
        }
        else {
            $result.State = 'STALE'
            $result.Detail += ', нет файла heartbeat'
        }
    }
    catch {
        $result.State = 'UNKNOWN'
        $result.Detail = $_.Exception.Message
    }
    return $result
}

function Get-ProxifierUiStatus {
    if($Demo){ return [pscustomobject]@{Running=$true;Pid=4343;Text='ДЕМО · запущен'} }
    try {
        $p = Get-Process -Name Proxifier -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($p) { return [pscustomobject]@{ Running = $true; Pid = $p.Id; Text = "Запущен · PID=$($p.Id)" } }
        return [pscustomobject]@{ Running = $false; Pid = 0; Text = 'Не запущен' }
    }
    catch { return [pscustomobject]@{ Running = $false; Pid = 0; Text = 'Состояние неизвестно' } }
}


function Get-V7RuntimeEvidenceAgeSeconds([string]$Path) {
    if(-not(Test-Path -LiteralPath $Path -PathType Leaf)){ return -1 }
    try { return [math]::Max(0,[int]((Get-Date)-(Get-Item -LiteralPath $Path -ErrorAction Stop).LastWriteTime).TotalSeconds) }
    catch { return -1 }
}

function Test-V7RuntimeEvidenceFresh([int]$AgeSeconds,[int]$MaxAgeSeconds=300) {
    return ($AgeSeconds -ge 0 -and $AgeSeconds -le $MaxAgeSeconds)
}

function Get-UiOverallState($Runtime, $Watchdog, [bool]$SocksUp, $ProxifierStatus, $Config=$null, [int]$RuntimeAgeSeconds=-1) {
    if (-not $Demo -and -not (Test-Path -LiteralPath $EnginePath)) { return 'ENGINE_MISSING' }
    if (-not $Runtime) { return 'NO_RUNTIME' }
    if (Test-Path -LiteralPath $AttentionFile) { return 'ATTENTION' }
    $effectiveVpsCount = @($ModuleNames | Where-Object { [string]$Runtime.Effective.$_ -eq 'VPS' }).Count
    $configuredVpsCapable=0
    if($Config){
        foreach($module in $ModuleNames){
            $mode='DIRECT';try{$mode=Normalize-Mode ([string]$Config.$module) 'DIRECT'}catch{}
            if($mode -in @('AUTO','VPS')){$configuredVpsCapable++}
        }
    }else{$configuredVpsCapable=$effectiveVpsCount}
    $runtimeEvidenceUsable=($RuntimeAgeSeconds -lt 0 -or $RuntimeAgeSeconds -le 300)
    $watchdogRequired=($configuredVpsCapable -gt 0 -or ($runtimeEvidenceUsable -and $effectiveVpsCount -gt 0))
    # Current local-control failures remain current even when route evidence is stale.
    if ($Watchdog.State -eq 'OFF' -and $watchdogRequired) { return 'FAILED' }
    if (($Watchdog.State -eq 'STALE' -or $Watchdog.State -eq 'UNKNOWN') -and $watchdogRequired) { return 'DEGRADED' }
    # Route health older than five minutes is evidence, not current truth. Do not promote stale FAILED rows to a current failure.
    if ($RuntimeAgeSeconds -gt 300) { return 'STALE_RUNTIME' }
    foreach ($module in $ModuleNames) {
        if ([string]$Runtime.Health.$module -eq 'FAILED') { return 'FAILED' }
    }
    if (-not $SocksUp -and $effectiveVpsCount -gt 0) { return 'FAILED' }
    if (-not $ProxifierStatus.Running -and $effectiveVpsCount -gt 0) { return 'FAILED' }
    foreach ($module in $ModuleNames) {
        if ([string]$Runtime.Health.$module -eq 'DEGRADED') { return 'DEGRADED' }
    }
    return 'HEALTHY'
}

function Get-OverallUiName([string]$State) {
    switch ($State) {
        'HEALTHY' { return 'ИСПРАВНО' }
        'DEGRADED' { return 'УХУДШЕНО' }
        'ATTENTION' { return 'ТРЕБУЕТ ВНИМАНИЯ' }
        'STALE_RUNTIME' { return 'ДАННЫЕ УСТАРЕЛИ' }
        'FAILED' { return 'ОШИБКА' }
        'ENGINE_MISSING' { return 'НЕТ ДВИЖКА' }
        'NO_RUNTIME' { return 'НЕТ ДАННЫХ' }
        default { return 'НЕИЗВЕСТНО' }
    }
}

function Get-RunCommand([string]$BaseDir) {
    if([string]::IsNullOrWhiteSpace($BaseDir)){ throw 'BaseDir пакета V7 не задан для автозапуска.' }
    $launch = Join-Path $BaseDir 'VPS-Control-v7-launch.ps1'
    return "`"$PowerShellExe`" -NoLogo -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File `"$launch`" -StartHidden"
}

function Test-UiAutostart {
    try {
        $value = (Get-ItemProperty -Path $RunKey -Name $RunValueName -ErrorAction SilentlyContinue).$RunValueName
        return [bool]$value
    }
    catch { return $false }
}

function Set-UiAutostart([bool]$Enabled,[string]$BaseDir) {
    if($Demo){ return $false }
    try {
        if (-not (Test-Path -LiteralPath $RunKey)) { New-Item -Path $RunKey -Force | Out-Null }
        if ($Enabled) {
            New-ItemProperty -Path $RunKey -Name $RunValueName -Value (Get-RunCommand -BaseDir $BaseDir) -PropertyType String -Force | Out-Null
            Write-UiLog 'UI autostart enabled.'
        }
        else {
            Remove-ItemProperty -Path $RunKey -Name $RunValueName -ErrorAction SilentlyContinue
            Write-UiLog 'UI autostart disabled.'
        }
        return $true
    }
    catch {
        [System.Windows.Forms.MessageBox]::Show(
            "Не удалось изменить автозапуск интерфейса.`r`n`r`n$($_.Exception.Message)",
            'VPS Control Center',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
        return $false
    }
}

# ---------------------------------------------------------------------------
# RC14.11 detailed SOCKS/recovery diagnostics.  These routines are read-only
# except for writing sanitized logs/exports under VPS-Control-Data.
# ---------------------------------------------------------------------------
function ConvertTo-V7TraceSafeText([string]$Text) {
    if($null -eq $Text){return ''}
    $safe=[string]$Text
    # Never persist common command-line/password forms.
    $safe=[regex]::Replace($safe,'(?i)(-pw\s+)("[^"]*"|\S+)','$1<redacted>')
    $safe=[regex]::Replace($safe,'(?i)(password\s*[=:]\s*)("[^"]*"|\S+)','$1<redacted>')
    $safe=[regex]::Replace($safe,'(?i)(PuttyPassword\s*=\s*)[^;\r\n]+','$1<redacted>')
    $safe=[regex]::Replace($safe,'(?i)(authorization\s*:\s*bearer\s+)\S+','$1<redacted>')
    $safe=[regex]::Replace($safe,'(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret)\s*[=:]\s*)("[^"]*"|\S+)','$1<redacted>')
    $safe=[regex]::Replace($safe,'(?is)-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----.*?-----END (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----','<private-key-redacted>')
    return $safe
}

function Write-V7SocksTrace([string]$Phase,[string]$Message='') {
    try {
        if(-not $SocksTraceFile){return}
        $dir=Split-Path -Parent $SocksTraceFile
        if($dir -and -not(Test-Path -LiteralPath $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
        $safe=ConvertTo-V7TraceSafeText $Message
        if(Test-Path -LiteralPath $SocksTraceFile -PathType Leaf){
            try{
                $f=Get-Item -LiteralPath $SocksTraceFile -ErrorAction Stop
                if($f.Length -gt 2MB){Move-Item -LiteralPath $SocksTraceFile -Destination ($SocksTraceFile+'.1') -Force -ErrorAction SilentlyContinue}
            }catch{}
        }
        $line='{0:yyyy-MM-dd HH:mm:ss.fff}  [{1}]  {2}' -f (Get-Date),$Phase,$safe
        Add-Content -LiteralPath $SocksTraceFile -Value $line -Encoding UTF8
    } catch { }
}

function Write-V7SocksMultiline([string]$Phase,[string]$Text) {
    if(-not $Text){return}
    try {
        foreach($line in ([string]$Text -split "`r?`n")){
            if($line){Write-V7SocksTrace $Phase $line}
        }
    } catch { }
}

function Get-V7TunnelListenerOwnerText([int]$Port) {
    try {
        $conn=Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1
        if(-not $conn){return 'none'}
        $proc=Get-CimInstance Win32_Process -Filter ("ProcessId="+[int]$conn.OwningProcess) -ErrorAction SilentlyContinue
        if($proc){return ("pid={0};name={1};path={2}" -f [int]$proc.ProcessId,[string]$proc.Name,[string]$proc.ExecutablePath)}
        return ("pid={0};process=unknown" -f [int]$conn.OwningProcess)
    } catch { return ('lookup-error='+$_.Exception.Message) }
}

function Get-V7SocksListenerOwnerText { return (Get-V7TunnelListenerOwnerText 1081) }

function Get-V7SavedSessionDiagnostic($Profile) {
    $result=[ordered]@{Exists=$false;RegistryExists=$false;PortableCandidate=$false;Source='NONE';Name='';HostName='';PortNumber='';Protocol='';Forwardings='';KeyConfigured=$false;PageantRunning=$false}
    try {
        if(-not $Profile -or [string]$Profile.AuthMode -ne 'SavedSession'){return [pscustomobject]$result}
        $name=[string]$Profile.SavedSession;$result.Name=$name
        if(-not $name){return [pscustomobject]$result}
        try {
            $si=Get-ItemProperty -LiteralPath ('HKCU:\Software\SimonTatham\PuTTY\Sessions\'+$name) -ErrorAction Stop
            $result.Exists=$true;$result.RegistryExists=$true;$result.Source='HKCU'
            $result.HostName=[string]$si.HostName
            $result.PortNumber=[string]$si.PortNumber
            $result.Protocol=[string]$si.Protocol
            try{$result.Forwardings=(@($si.PortForwardings)-join ',')}catch{}
            try{$result.KeyConfigured=[bool]([string]$si.PublicKeyFile)}catch{}
        } catch {
            # Portable PuTTY launchers can own their SavedSession outside the
            # standard PuTTY HKCU key. In that case absence from HKCU is not a
            # failed session assertion; runtime SOCKS identity is authoritative.
            try {
                $legacyPutty=Get-V7LegacyPuttyPath -EngineSourcePath $EngineSourcePath -BaseDir (Split-Path -Parent $EngineSourcePath)
                if($legacyPutty -and ([IO.Path]::GetFileName([string]$legacyPutty) -match '(?i)portable' -or (Split-Path -Parent $legacyPutty) -match '(?i)portable')){
                    $result.Exists=$true;$result.PortableCandidate=$true;$result.Source='PORTABLE_OPAQUE'
                    $dir=Split-Path -Parent $legacyPutty
                    foreach($candidate in @((Join-Path $dir ('Sessions\'+$name)),(Join-Path $dir ('sessions\'+$name)))){
                        if(-not(Test-Path -LiteralPath $candidate -PathType Leaf)){continue}
                        try{
                            $raw=Get-Content -LiteralPath $candidate -Raw -ErrorAction Stop
                            $hm=[regex]::Match($raw,'(?im)^\s*HostName\\(.*?)\\\s*$')
                            $pm=[regex]::Match($raw,'(?im)^\s*PortNumber\\(.*?)\\\s*$')
                            $pr=[regex]::Match($raw,'(?im)^\s*Protocol\\(.*?)\\\s*$')
                            $km=[regex]::Match($raw,'(?im)^\s*PublicKeyFile\\(.*?)\\\s*$')
                            if($hm.Success){
                                $result.HostName=[Uri]::UnescapeDataString([string]$hm.Groups[1].Value)
                                $result.PortNumber=$(if($pm.Success){[string]$pm.Groups[1].Value}else{'22'})
                                $result.Protocol=$(if($pr.Success){[string]$pr.Groups[1].Value}else{'ssh'})
                                $result.KeyConfigured=[bool]($km.Success -and [string]$km.Groups[1].Value)
                                $result.Source='PORTABLE_SLASH_FILE'
                                break
                            }
                        }catch{}
                    }
                }
            } catch { }
        }
        try{$result.PageantRunning=[bool](Get-Process -Name pageant -ErrorAction SilentlyContinue|Select-Object -First 1)}catch{}
    } catch { }
    return [pscustomobject]$result
}

function Get-V7SocksDiagnosticSnapshotText([string]$Label='snapshot') {
    $lines=New-Object Collections.ArrayList
    try{
        $profile=Get-ActiveVpsProfile
        $watch=Get-WatchdogUiStatus
        $socks=Test-TcpListener '127.0.0.1' 1081 300
        $reserve=Test-TcpListener '127.0.0.1' 1080 250
        $listener=Get-V7TunnelListenerOwnerText 1081
        $reserveListener=Get-V7TunnelListenerOwnerText 1080
        $putty=@(Get-Process -Name putty,putty_portable,plink -ErrorAction SilentlyContinue|ForEach-Object{"$($_.ProcessName):$($_.Id)"}) -join ','
        $session=Get-V7SavedSessionDiagnostic $profile
        [void]$lines.Add("label=$Label")
        [void]$lines.Add("version=$UiVersion; time=$((Get-Date).ToString('o')); demo=$([bool]$Demo)")
        [void]$lines.Add("tunnel.primary.id=PRIMARY_AUTO; listen=$socks; endpoint=127.0.0.1:1081; lifecycle=AUTO; owner=$listener")
        [void]$lines.Add("tunnel.reserve.id=RESERVE_MANUAL; listen=$reserve; endpoint=127.0.0.1:1080; lifecycle=MANUAL_ONLY; offAllowed=true; owner=$reserveListener")
        [void]$lines.Add("watchdog.state=$([string]$watch.State); fresh=$([bool]$watch.Fresh); pid=$([int]$watch.Pid); heartbeatAge=$([int]$watch.HeartbeatAge); detail=$([string]$watch.Detail)")
        [void]$lines.Add("puttyProcesses=$(if($putty){$putty}else{'none'})")
        if($profile){
            $secretStored=$false;try{$secretStored=Test-VpsSecretStored ([string]$profile.Id)}catch{}
            [void]$lines.Add("profile.id=$([string]$profile.Id); name=$([string]$profile.Name); auth=$([string]$profile.AuthMode); host=$([string]$profile.Host); sshPort=$([int]$profile.SshPort); user=$([string]$profile.User); session=$([string]$profile.SavedSession); expectedExit=$([string]$profile.ExpectedExitIp); dpapiStored=$secretStored; keyConfigured=$([bool]([string]$profile.KeyFile))")
            [void]$lines.Add("session.exists=$([bool]$session.Exists); session.source=$([string]$session.Source); session.registryExists=$([bool]$session.RegistryExists); session.portableCandidate=$([bool]$session.PortableCandidate); session.host=$([string]$session.HostName); session.port=$([string]$session.PortNumber); session.protocol=$([string]$session.Protocol); session.forwardings=$([string]$session.Forwardings); session.keyConfigured=$([bool]$session.KeyConfigured); pageant=$([bool]$session.PageantRunning)")
        }else{[void]$lines.Add('profile=NONE')}
        try{
            $legacyPutty=Get-V7LegacyPuttyPath -EngineSourcePath $EngineSourcePath -BaseDir (Split-Path -Parent $EngineSourcePath)
            [void]$lines.Add("putty.discovered=$(if($legacyPutty){$legacyPutty}else{'NONE'})")
            if($legacyPutty -and (Test-Path -LiteralPath $legacyPutty)){[void]$lines.Add("putty.sha256=$(Get-FileSha256 $legacyPutty)")}
        }catch{[void]$lines.Add("putty.discoveryError=$($_.Exception.Message)")}
        [void]$lines.Add("engine.exists=$(Test-Path -LiteralPath $EnginePath); engine.sha256=$(Get-FileSha256 $EnginePath)")
        [void]$lines.Add("runtime.ageSeconds=$(Get-V7RuntimeEvidenceAgeSeconds -Path $RuntimeFile)")
        [void]$lines.Add("recovery.attempts=$([int]$script:RuntimeRecoveryAttempts); recovery.nextAt=$($script:RuntimeRecoveryNextAt.ToString('o')); recovery.inFlight=$([bool]$script:RuntimeRecoveryAction)")
    }catch{[void]$lines.Add("snapshot.error=$($_.Exception.Message)")}
    return (ConvertTo-V7TraceSafeText (@($lines)-join '; '))
}

function Write-V7SocksSnapshot([string]$Label='snapshot') {
    try{Write-V7SocksTrace 'SNAPSHOT' (Get-V7SocksDiagnosticSnapshotText $Label)}catch{}
}

function Get-V7TailSafe([string]$Path,[int]$Lines=250) {
    if(-not $Path -or -not(Test-Path -LiteralPath $Path -PathType Leaf)){return @()}
    try {
        # Windows PowerShell 5.1 defaults can interpret UTF-8-without-BOM as ANSI.
        # Read-TextFileSmart prevents mojibake in the exported diagnostic report.
        $raw=Read-TextFileSmart $Path
        if($null -eq $raw){return @()}
        $all=@([string]$raw -split "`r?`n")
        $start=[Math]::Max(0,$all.Count-[Math]::Max(1,$Lines))
        $result=New-Object Collections.ArrayList
        for($i=$start;$i -lt $all.Count;$i++){if($all[$i] -ne ''){[void]$result.Add((ConvertTo-V7TraceSafeText ([string]$all[$i])))}}
        return @($result)
    } catch { return @("[read failed] $($_.Exception.Message)") }
}

function New-V7SocksDebugReport([Parameter(Mandatory=$true)][string]$OutputDir) {
    if(-not(Test-Path -LiteralPath $OutputDir)){New-Item -ItemType Directory -Path $OutputDir -Force|Out-Null}
    $path=Join-Path $OutputDir ("SOCKS-debug-{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $lines=New-Object Collections.ArrayList
    [void]$lines.Add('=== VPS CONTROL CENTER · SOCKS DEBUG REPORT ===')
    [void]$lines.Add("CreatedAt=$((Get-Date).ToString('o'))")
    [void]$lines.Add("UiVersion=$UiVersion")
    [void]$lines.Add('SecretsIncluded=false')
    [void]$lines.Add('NOTE: password/DPAPI/private-key contents and -pw values are not included.')
    [void]$lines.Add('')
    [void]$lines.Add('=== CURRENT SNAPSHOT ===')
    [void]$lines.Add((Get-V7SocksDiagnosticSnapshotText 'export'))
    [void]$lines.Add('')
    foreach($item in @(
        [pscustomobject]@{Title='V7 SOCKS RUNTIME TRACE';Path=$SocksTraceFile;Tail=800},
        [pscustomobject]@{Title='V6.5 SOCKS ENGINE TRACE';Path=$EngineSocksTraceFile;Tail=800},
        [pscustomobject]@{Title='V7 UI LOG';Path=$UiLogFile;Tail=350},
        [pscustomobject]@{Title='V7 LAUNCH LOG';Path=(Join-Path $UiLogsDir 'launch.log');Tail=250},
        [pscustomobject]@{Title='V7 EVENTS LOG';Path=$V7EventsFile;Tail=250},
        [pscustomobject]@{Title='RUNTIME METRICS JSONL';Path=$(if($V7RuntimeMetricsFile){$V7RuntimeMetricsFile}else{''});Tail=300},
        [pscustomobject]@{Title='STATE / DIAGNOSTIC TRACE JSONL';Path=$(if($V7DiagnosticTraceFile){$V7DiagnosticTraceFile}else{''});Tail=300},
        [pscustomobject]@{Title='OPERATION EVIDENCE JSONL';Path=$(if($V7OperationEvidenceFile){$V7OperationEvidenceFile}else{''});Tail=300},
        [pscustomobject]@{Title='ENVIRONMENT LATEST';Path=$(if($V7EnvironmentLatestFile){$V7EnvironmentLatestFile}else{''});Tail=1200},
        [pscustomobject]@{Title='V6.3 CONTROLLER LOG';Path=(Join-Path $StateDir 'controller.log');Tail=350},
        [pscustomobject]@{Title='V6.3 WATCHDOG LOG';Path=(Join-Path $StateDir 'watchdog.log');Tail=350},
        [pscustomobject]@{Title='ROUTE DECISIONS';Path=(Join-Path $StateDir 'route-decisions.log');Tail=180},
        [pscustomobject]@{Title='WATCHDOG HEARTBEAT';Path=$WatchdogHeartbeatFile;Tail=80}
    )){
        [void]$lines.Add("=== $($item.Title) ===")
        [void]$lines.Add("Path=$($item.Path)")
        $tail=Get-V7TailSafe -Path ([string]$item.Path) -Lines ([int]$item.Tail)
        if(@($tail).Count -eq 0){[void]$lines.Add('[no data]')}else{foreach($x in @($tail)){[void]$lines.Add([string]$x)}}
        [void]$lines.Add('')
    }
    try{
        [void]$lines.Add('=== STATE DIRECTORY FILE METADATA ===')
        foreach($f in @(Get-ChildItem -LiteralPath $StateDir -File -ErrorAction SilentlyContinue|Sort-Object Name)){
            # metadata only; do not dump configs, profiles or secret-like content.
            [void]$lines.Add(("{0} | {1} bytes | modified {2:o}" -f $f.Name,$f.Length,$f.LastWriteTime))
        }
    }catch{}
    $text=ConvertTo-V7TraceSafeText (@($lines)-join "`r`n")
    [IO.File]::WriteAllText($path,$text,(New-Object Text.UTF8Encoding($true)))
    return $path
}
