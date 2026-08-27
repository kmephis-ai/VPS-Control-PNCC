#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Live','Plan')][string]$Mode = 'Live',
    [string]$WorkspacePath,
    [string]$V631Path,
    [string]$OutputDirectory = 'E:\!Chrome_Downloads\PNCC-RUNTIME-1081-RECONCILE',
    [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$ExpectedArtifactName = 'VPS-Control-v7.0.0-rc14.39.zip'
$ExpectedArtifactSha = '8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3'
$ExpectedArtifactSize = 700961L
$ExpectedV631Sha = '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$ExpectedOldEngineSha = '90edda2efa418db3363f9a575955295bab856deb1dda5da46761b6ee1eba12ec'
$PrimaryPort = 1081
$ReservePort = 1080
$StateDir = Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$WatchdogPidFile = Join-Path $StateDir 'watchdog.pid'
$WatchdogHeartbeatFile = Join-Path $StateDir 'watchdog-heartbeat.json'
$PowerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Get-Proc([int]$ProcessId) {
    if ($ProcessId -le 0) { return $null }
    try { return Get-CimInstance Win32_Process -Filter ('ProcessId=' + $ProcessId) -ErrorAction Stop }
    catch { return $null }
}
function Get-FileArg([string]$Cmd) {
    if ([string]::IsNullOrWhiteSpace($Cmd)) { return '' }
    $m = [regex]::Match($Cmd, '(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))')
    if (-not $m.Success) { return '' }
    foreach ($i in 1..3) { if ($m.Groups[$i].Success) { return [string]$m.Groups[$i].Value } }
    return ''
}
function Get-PortSnapshot([int]$Port) {
    $rows = @(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue)
    $owners = @()
    foreach ($row in $rows) {
        $proc = Get-Proc ([int]$row.OwningProcess)
        $owners += [ordered]@{
            pid = [int]$row.OwningProcess
            name = $(if ($proc) { [string]$proc.Name } else { '' })
            exe = $(if ($proc) { [string]$proc.ExecutablePath } else { '' })
        }
    }
    return [ordered]@{ port = $Port; listening = ($rows.Count -gt 0); owners = @($owners | Sort-Object pid) }
}
function Snapshot-Key($Value) { return ($Value | ConvertTo-Json -Depth 8 -Compress) }
function Write-Json($Value, [string]$Path) {
    $dir = Split-Path -Parent $Path
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 16), (New-Object Text.UTF8Encoding($true)))
}
function Invoke-Captured([string]$File, [string]$Arguments, [int]$TimeoutSeconds = 120) {
    $out = Join-Path $OutputDirectory ('native-' + [guid]::NewGuid().ToString('N') + '.out.txt')
    $err = Join-Path $OutputDirectory ('native-' + [guid]::NewGuid().ToString('N') + '.err.txt')
    $proc = Start-Process -FilePath $File -ArgumentList $Arguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
        try { $proc.Kill() } catch { }
        throw "native timeout: $File"
    }
    $proc.Refresh()
    $stdout = $(if (Test-Path $out) { Get-Content $out -Raw } else { '' })
    $stderr = $(if (Test-Path $err) { Get-Content $err -Raw } else { '' })
    Remove-Item $out,$err -Force -ErrorAction SilentlyContinue
    return [pscustomobject]@{ ExitCode = [int]$proc.ExitCode; Stdout = [string]$stdout; Stderr = [string]$stderr }
}
function Get-ExpectedVpsIp([string]$Path) {
    $raw = Get-Content -LiteralPath $Path -Raw
    $m = [regex]::Match($raw, "(?m)^\s*\`$ExpectedVpsIp\s*=\s*'([^']+)'\s*$")
    if ($m.Success) { return [string]$m.Groups[1].Value }
    return ''
}
function Get-SocksIp([int]$Port) {
    $curl = (Get-Command curl.exe -ErrorAction Stop).Source
    $r = Invoke-Captured $curl ("--silent --show-error --max-time 20 --socks5-hostname 127.0.0.1:$Port https://api.ipify.org") 30
    if ($r.ExitCode -ne 0) { return '' }
    return $r.Stdout.Trim()
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$log = Join-Path $OutputDirectory 'PNCC-PRIMARY-1081-RECONCILE.log'
Start-Transcript -LiteralPath $log -Force | Out-Null
try {
    if ($Mode -eq 'Plan') {
        if (-not $FixturePath -or -not (Test-Path -LiteralPath $FixturePath -PathType Leaf)) { throw 'FixturePath required in Plan mode' }
        $fixture = Get-Content -LiteralPath $FixturePath -Raw | ConvertFrom-Json
        foreach ($name in @('candidate_identity','rollback_identity','old_primary_proven','old_watchdog_proven','reserve_observation_only','generated_pwfile','generated_no_plain_pw','hostkey_fail_closed')) {
            if (-not [bool]$fixture.$name) { throw "plan fixture failed: $name" }
        }
        Write-Output 'PNCC_PRIMARY_1081_RECONCILE=PLAN_PASS RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
        exit 0
    }

    if ($env:OS -ne 'Windows_NT') { throw 'Live mode requires Windows' }
    if (-not $WorkspacePath -or -not (Test-Path -LiteralPath $WorkspacePath -PathType Container)) { throw 'WorkspacePath missing' }
    if (-not $V631Path -or -not (Test-Path -LiteralPath $V631Path -PathType Leaf)) { throw 'V631Path missing' }
    if ((Get-Sha256 $V631Path) -ne $ExpectedV631Sha) { throw 'V6.3.1 SHA mismatch' }

    $artifact = Join-Path (Join-Path $WorkspacePath 'provider-artifact') $ExpectedArtifactName
    if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) { throw 'candidate artifact missing' }
    $artifactInfo = Get-Item -LiteralPath $artifact
    if ([long]$artifactInfo.Length -ne $ExpectedArtifactSize -or (Get-Sha256 $artifact) -ne $ExpectedArtifactSha) { throw 'candidate artifact identity mismatch' }

    $reserveBefore = Get-PortSnapshot $ReservePort
    $primaryRows = @(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue)
    if ($primaryRows.Count -ne 1) { throw 'expected exactly one 1081 listener' }
    $oldPrimaryProcessId = [int]$primaryRows[0].OwningProcess
    $oldPrimary = Get-Proc $oldPrimaryProcessId
    if ($null -eq $oldPrimary -or [string]$oldPrimary.Name -notmatch '(?i)^(putty|putty_portable|plink)\.exe$') { throw '1081 owner is not proven PuTTY-family' }
    $oldPrimaryCmd = [string]$oldPrimary.CommandLine
    if ($oldPrimaryCmd -notmatch '(?i)(?:^|\s)-D\s+"?127\.0\.0\.1:1081"?(?:\s|$)') { throw '1081 owner lacks exact -D binding' }
    if ($oldPrimaryCmd -notmatch '(?i)(?:^|\s)-pw(?:\s|=)') { throw 'expected legacy plaintext -pw baseline was not observed; refusing mutation' }

    $oldWatchdogProcessId = [int]$oldPrimary.ParentProcessId
    $oldWatchdog = Get-Proc $oldWatchdogProcessId
    if ($null -eq $oldWatchdog -or [string]$oldWatchdog.Name -notmatch '(?i)^powershell\.exe$') { throw '1081 parent is not proven PowerShell watchdog' }
    $oldWatchdogCmd = [string]$oldWatchdog.CommandLine
    if ($oldWatchdogCmd -notmatch '(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)') { throw '1081 parent lacks Watchdog action' }
    $oldEnginePath = Get-FileArg $oldWatchdogCmd
    if (-not $oldEnginePath -or -not (Test-Path -LiteralPath $oldEnginePath -PathType Leaf)) { throw 'old watchdog engine path unresolved' }
    if ((Get-Sha256 $oldEnginePath) -ne $ExpectedOldEngineSha) { throw 'old watchdog engine SHA changed from admitted baseline' }

    $stage = Join-Path $OutputDirectory 'candidate-stage'
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    Expand-Archive -LiteralPath $artifact -DestinationPath $stage -Force
    $upgrade = @(Get-ChildItem $stage -Recurse -File -Filter 'VPS-Control-v7-engine-upgrade.ps1' | Select-Object -First 1)
    if ($upgrade.Count -ne 1) { throw 'candidate generator missing' }
    $engineDir = Split-Path -Parent $upgrade[0].FullName
    $stageV631 = Join-Path $engineDir 'VPS-Control-v6.3.1.ps1'
    Copy-Item -LiteralPath $V631Path -Destination $stageV631 -Force
    $generated = Join-Path $engineDir 'VPS-Control-v6.5.ps1'
    $genArgs = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$($upgrade[0].FullName)`" -SourcePath `"$stageV631`" -DestinationPath `"$generated`""
    $gen = Invoke-Captured $PowerShellExe $genArgs 120
    if ($gen.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $generated -PathType Leaf)) { throw ('candidate engine generation failed: ' + $gen.Stderr) }

    $generatedSha = Get-Sha256 $generated
    $generatedRaw = Get-Content -LiteralPath $generated -Raw
    if ($generatedRaw -notmatch '(?i)-pwfile') { throw 'generated engine lacks -pwfile' }
    if ($generatedRaw -notmatch '(?i)plaintext -pw fallback') { throw 'generated engine lacks plaintext fallback prohibition' }
    if ($generatedRaw -notmatch '(?i)Ensure-V7OfficialPuttyHostKeyTrust') { throw 'generated engine lacks fail-closed host-key trust gate' }
    if ($generatedRaw -notmatch '(?i)RestartTunnel') { throw 'generated engine lacks RestartTunnel action' }

    $evidence = [ordered]@{
        schema_version = 1
        contract_id = 'PNCC_PRIMARY_1081_RECONCILE_V1'
        started_at = (Get-Date).ToString('o')
        runtime_mutation = $true
        reserve_1080_mutation = $false
        old_primary = [ordered]@{ pid = $oldPrimaryProcessId; parent_pid = $oldWatchdogProcessId; has_plain_pw = $true; has_pwfile = $false }
        old_engine_sha256 = $ExpectedOldEngineSha
        generated_engine_sha256 = $generatedSha
        reserve_before = $reserveBefore
        steps = @()
    }

    # Mutation boundary. Only the exact proven Watchdog parent and its exact proven 1081 child are eligible.
    Stop-Process -Id $oldWatchdogProcessId -Force -ErrorAction Stop
    $evidence.steps += @([ordered]@{ step = 'stop_old_watchdog'; pid = $oldWatchdogProcessId; result = 'PASS' })
    Start-Sleep -Milliseconds 600
    $stillOldPrimary = Get-Proc $oldPrimaryProcessId
    if ($stillOldPrimary) { Stop-Process -Id $oldPrimaryProcessId -Force -ErrorAction Stop }
    $evidence.steps += @([ordered]@{ step = 'stop_old_primary_1081'; pid = $oldPrimaryProcessId; result = 'PASS' })

    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline) {
        $listener = Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue
        if (-not $listener) { break }
        Start-Sleep -Milliseconds 300
    }
    if (Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue) { throw '1081 did not stop after proven teardown' }

    $restartArgs = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$generated`" -Action RestartTunnel -NoAppLaunch"
    $restart = Invoke-Captured $PowerShellExe $restartArgs 120
    if ($restart.ExitCode -ne 0) { throw ('exact generated RestartTunnel failed: ' + $restart.Stderr) }

    $deadline = (Get-Date).AddSeconds(45)
    $newPrimary = $null
    while ((Get-Date) -lt $deadline) {
        $rows = @(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($rows.Count) {
            $newPrimary = Get-Proc ([int]$rows[0].OwningProcess)
            if ($newPrimary) { break }
        }
        Start-Sleep -Milliseconds 500
    }
    if ($null -eq $newPrimary) { throw 'new 1081 listener did not appear' }
    $newCmd = [string]$newPrimary.CommandLine
    if ($newCmd -notmatch '(?i)(?:^|\s)-D\s+"?127\.0\.0\.1:1081"?(?:\s|$)') { throw 'new 1081 lacks exact binding' }
    if ($newCmd -match '(?i)(?:^|\s)-pw(?:\s|=)') { throw 'SECURITY BLOCK: new 1081 still exposes plaintext -pw' }
    if ($newCmd -notmatch '(?i)(?:^|\s)-pwfile(?:\s|=)') { throw 'new 1081 does not use -pwfile' }
    $evidence.steps += @([ordered]@{ step = 'restart_primary_1081'; new_pid = [int]$newPrimary.ProcessId; pwfile = $true; plain_pw = $false; result = 'PASS' })

    Remove-Item -LiteralPath $WatchdogPidFile -Force -ErrorAction SilentlyContinue
    $watchdogArgs = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$generated`" -Action Watchdog -WatchIntervalSeconds 45 -NoAppLaunch"
    $newWatchdog = Start-Process -FilePath $PowerShellExe -ArgumentList $watchdogArgs -WindowStyle Hidden -PassThru
    $deadline = (Get-Date).AddSeconds(90)
    $watchdogOk = $false
    $heartbeatAge = -1
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        $watchdogProcess = Get-Proc ([int]$newWatchdog.Id)
        if ($null -eq $watchdogProcess) { break }
        if (Test-Path -LiteralPath $WatchdogHeartbeatFile -PathType Leaf) {
            $heartbeatAge = [int]((Get-Date) - (Get-Item -LiteralPath $WatchdogHeartbeatFile).LastWriteTime).TotalSeconds
            if ($heartbeatAge -ge 0 -and $heartbeatAge -le 60) { $watchdogOk = $true; break }
        }
    }
    if (-not $watchdogOk) { throw 'exact watchdog did not produce fresh heartbeat' }
    $watchdogLive = Get-Proc ([int]$newWatchdog.Id)
    if ($null -eq $watchdogLive) { throw 'new watchdog exited unexpectedly' }
    $watchdogFile = Get-FileArg ([string]$watchdogLive.CommandLine)
    if (-not $watchdogFile -or (Get-Sha256 $watchdogFile) -ne $generatedSha) { throw 'new watchdog engine identity mismatch' }
    $evidence.steps += @([ordered]@{ step = 'start_exact_watchdog'; pid = [int]$newWatchdog.Id; heartbeat_age_seconds = $heartbeatAge; engine_sha256 = $generatedSha; result = 'PASS' })

    $expectedIp = Get-ExpectedVpsIp $V631Path
    if (-not $expectedIp) { throw 'ExpectedVpsIp unresolved from immutable V6.3.1' }
    $routedIp = Get-SocksIp $PrimaryPort
    if (-not $routedIp -or $routedIp -ne $expectedIp) { throw '1081 routed identity mismatch after reconciliation' }

    $reserveAfter = Get-PortSnapshot $ReservePort
    if ((Snapshot-Key $reserveBefore) -ne (Snapshot-Key $reserveAfter)) { throw 'CRITICAL: 1080 reserve snapshot changed' }

    $evidence.reserve_after = $reserveAfter
    $evidence.routed_identity_match = $true
    $evidence.completed_at = (Get-Date).ToString('o')
    $evidence.state = 'PASS'
    $evidence.runtime_authority = $false
    $evidence.promotion_eligible = $false
    $resultPath = Join-Path $OutputDirectory 'primary-1081-reconcile-result.json'
    Write-Json $evidence $resultPath
    Write-Output 'PNCC_PRIMARY_1081_RECONCILE=PASS RUNTIME_MUTATION=true RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false'
    Write-Output "RESULT=$resultPath"
    Write-Output "LOG_PATH=$log"
    exit 0
}
catch {
    $message = $_.Exception.Message
    Write-Output "PNCC_PRIMARY_1081_RECONCILE=BLOCKED ERROR=$message RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
    Write-Output "LOG_PATH=$log"
    exit 50
}
finally {
    try { Stop-Transcript | Out-Null } catch { }
}
