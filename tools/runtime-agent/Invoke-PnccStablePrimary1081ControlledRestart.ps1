#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Fixture','Live')][string]$Mode='Fixture',
    [string]$FixturePath,
    [string]$OwnerAuthorizationPath,
    [string]$RepositoryRoot='',
    [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-STABLE-PRIMARY-1081-LIVE-RESTART'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
if([string]::IsNullOrWhiteSpace($RepositoryRoot)){$RepositoryRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}

$ExpectedEngineSha='843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'
$PrimaryPort=1081
$ReservePort=1080
$RouteProbeMaxAttempts=3
$StateDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$PidFile=Join-Path $StateDir 'watchdog.pid'
$Heartbeat=Join-Path $StateDir 'watchdog-heartbeat.json'
$PsExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$script:RouteProbeLastAttempts=0
$script:RouteProbeLastExitCode=-1

function WriteJson($Value,[string]$Path){$d=Split-Path -Parent $Path;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 16),(New-Object Text.UTF8Encoding($true)))}
function Proc([int]$ProcessId){if($ProcessId-le0){return $null};try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{$null}}
function FileArg([string]$Cmd){if(-not$Cmd){return ''};$m=[regex]::Match($Cmd,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))');if(-not$m.Success){return ''};foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}};return ''}
function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Snap([int]$Port){$rows=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue);$o=@();foreach($r in $rows){$p=Proc ([int]$r.OwningProcess);$o+=[ordered]@{pid=[int]$r.OwningProcess;name=$(if($p){[string]$p.Name}else{''});exe=$(if($p){[string]$p.ExecutablePath}else{''})}};[ordered]@{port=$Port;listening=($rows.Count-gt0);listener_count=$rows.Count;owners=@($o|Sort-Object pid)}}
function Key($Value){$Value|ConvertTo-Json -Depth 8 -Compress}
function Fingerprint([string]$CommandLine){if([string]::IsNullOrWhiteSpace($CommandLine)){return ''};$s=[regex]::Replace($CommandLine,'(?i)(-pwfile\s+)(?:"[^"]*"|''[^'']*''|\S+)','$1<redacted-path>');$s=[regex]::Replace($s,'(?i)(-pw\s+)(?:"[^"]*"|''[^'']*''|\S+)','$1<redacted>');$b=[Text.Encoding]::UTF8.GetBytes($s);$h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash($b))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
function Primary(){ $r=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue);if($r.Count-ne1){throw "expected exactly one 1081 listener, got $($r.Count)"};$p=Proc ([int]$r[0].OwningProcess);if($null-eq$p){throw '1081 owner missing'};$cmd=[string]$p.CommandLine;[pscustomobject]@{Pid=[int]$p.ProcessId;Name=[string]$p.Name;Exe=[string]$p.ExecutablePath;Cmd=$cmd;Fingerprint=(Fingerprint $cmd);Putty=([string]$p.Name-match'(?i)^(putty|putty_portable|plink)\.exe$');Binding=($cmd-match'(?i)(?:^|\s)-D\s+"?127\.0\.0\.1:1081"?(?:\s|$)');Pwfile=($cmd-match'(?i)(?:^|\s)-pwfile(?:\s|=)');NoPlainPw=($cmd-notmatch'(?i)(?:^|\s)-pw(?:\s|=)')} }
function Watchdog(){if(-not(Test-Path -LiteralPath $PidFile -PathType Leaf)){throw 'watchdog pid registration missing'};$id=[int](Get-Content -LiteralPath $PidFile -Raw).Trim();$p=Proc $id;if($null-eq$p){throw 'registered watchdog process missing'};$cmd=[string]$p.CommandLine;if($cmd-notmatch'(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){throw 'registered process is not Watchdog'};$f=FileArg $cmd;if(-not$f-or-not(Test-Path -LiteralPath $f -PathType Leaf)){throw 'watchdog engine path missing'};if((Sha $f)-cne$ExpectedEngineSha){throw 'watchdog engine SHA mismatch'};if(-not(Test-Path -LiteralPath $Heartbeat -PathType Leaf)){throw 'watchdog heartbeat missing'};$age=[int]((Get-Date)-(Get-Item -LiteralPath $Heartbeat).LastWriteTime).TotalSeconds;if($age-lt0-or$age-gt240){throw "watchdog heartbeat stale: $age"};[pscustomobject]@{Pid=$id;Engine=$f;Age=$age}}
function SocksIdentity(){
    $curl=(Get-Command curl.exe -ErrorAction Stop).Source
    $script:RouteProbeLastAttempts=0
    $script:RouteProbeLastExitCode=-1
    for($attempt=1;$attempt-le$RouteProbeMaxAttempts;$attempt++){
        $script:RouteProbeLastAttempts=$attempt
        $o=Join-Path $OutputDirectory ('curl-'+[guid]::NewGuid().ToString('N')+'.out')
        $e=Join-Path $OutputDirectory ('curl-'+[guid]::NewGuid().ToString('N')+'.err')
        $p=$null;$timedOut=$false;$value=''
        try{
            $p=Start-Process $curl -ArgumentList '--silent --show-error --max-time 12 --socks5-hostname 127.0.0.1:1081 https://api.ipify.org' -PassThru -WindowStyle Hidden -RedirectStandardOutput $o -RedirectStandardError $e
            if(-not$p.WaitForExit(20000)){$timedOut=$true;try{$p.Kill()}catch{};try{$p.WaitForExit(3000)|Out-Null}catch{}}
            $p.Refresh()
            $script:RouteProbeLastExitCode=$(if($timedOut){124}else{[int]$p.ExitCode})
            if(-not$timedOut-and$script:RouteProbeLastExitCode-eq0-and(Test-Path $o)){$value=(Get-Content $o -Raw).Trim()}
            if($value){return $value}
        }finally{
            Remove-Item $o,$e -Force -ErrorAction SilentlyContinue
        }
        if($attempt-lt$RouteProbeMaxAttempts){Start-Sleep -Milliseconds 750}
    }
    throw ('SOCKS identity probe failed after attempts='+$script:RouteProbeLastAttempts+' last_exit_code='+$script:RouteProbeLastExitCode)
}
function TryPostFailureState($ReserveBefore){
    $snap1081=Snap $PrimaryPort
    $secure=$false;$routeOk=$false;$watchdogOk=$false;$reserveOk=$false;$routeAttempts=0;$routeExit=-1
    if($snap1081.listener_count-eq1){
        try{$q=Primary;$secure=([bool]$q.Putty-and[bool]$q.Binding-and[bool]$q.Pwfile-and[bool]$q.NoPlainPw)}catch{$secure=$false}
        if($secure){
            try{$null=SocksIdentity;$routeOk=$true;$routeAttempts=$script:RouteProbeLastAttempts;$routeExit=$script:RouteProbeLastExitCode}catch{$routeOk=$false;$routeAttempts=$script:RouteProbeLastAttempts;$routeExit=$script:RouteProbeLastExitCode}
        }
    }
    try{$w=Watchdog;$watchdogOk=($w.Engine-and((Sha $w.Engine)-ceq$ExpectedEngineSha))}catch{$watchdogOk=$false}
    $reserveAfter=Snap $ReservePort
    $reserveOk=((Key $ReserveBefore)-ceq(Key $reserveAfter))
    [ordered]@{
        primary_1081_listener_count=[int]$snap1081.listener_count
        primary_1081_secure=$secure
        primary_1081_route_probe_success=$routeOk
        route_probe_attempts=[int]$routeAttempts
        route_probe_last_exit_code=[int]$routeExit
        watchdog_exact_and_fresh=$watchdogOk
        reserve_1080_unchanged=$reserveOk
        runtime_healthy=($snap1081.listener_count-eq1-and$secure-and$routeOk-and$watchdogOk-and$reserveOk)
    }
}

New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$resultPath=Join-Path $OutputDirectory 'stable-primary-1081-live-restart-result.json'
$restartStdout=Join-Path $OutputDirectory 'restart-tunnel.stdout.log'
$restartStderr=Join-Path $OutputDirectory 'restart-tunnel.stderr.log'

if($Mode-ceq'Fixture'){
    if(-not$FixturePath-or-not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
    $f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json
    $checks=[ordered]@{
        authorization_contract=([string]$f.authorization_contract-ceq'PNCC_STABLE_PRIMARY_1081_MUTATION_AUTHORIZATION_V1')
        authorization_state=([string]$f.authorization_state-ceq'AUTHORIZATION_ADMITTED')
        execution_plan_contract=([string]$f.execution_plan_contract-ceq'PNCC_STABLE_PRIMARY_1081_CONTROLLED_RESTART_V1')
        execution_plan_state=([string]$f.execution_plan_state-ceq'EXECUTION_PLAN_ADMITTED')
        default_deny=[bool]$f.default_deny
        owner_token_required=[bool]$f.owner_token_required
        token_exact_main_binding=[bool]$f.token_exact_main_binding
        token_exact_target_binding=[bool]$f.token_exact_target_binding
        token_expiry_required=[bool]$f.token_expiry_required
        token_one_shot_consumption=[bool]$f.token_one_shot_consumption
        exact_stable_engine=[bool]$f.exact_stable_engine
        secure_restart_tunnel_reuse=[bool]$f.secure_restart_tunnel_reuse
        reserve_1080_snapshot_guard=[bool]$f.reserve_1080_snapshot_guard
        post_routed_identity_required=[bool]$f.post_routed_identity_required
        runtime_authority_false=[bool]$f.runtime_authority_false
        promotion_eligible_false=[bool]$f.promotion_eligible_false
    }
    $failed=@($checks.GetEnumerator()|Where-Object{-not[bool]$_.Value}|ForEach-Object{$_.Key})
    $ok=($failed.Count-eq0)
    $r=[ordered]@{schema_version=1;contract_id='PNCC_STABLE_PRIMARY_1081_LIVE_CONTROLLED_RESTART_V1';mode='Fixture';state=$(if($ok){'LIVE_EXECUTOR_ADMITTED_DEFAULT_DENY'}else{'BLOCKED'});checks=$checks;failed_checks=$failed;physical_execution_allowed=$false;owner_authorization_consumed=$false;mutation_executed=$false;runtime_mutation=$false;reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;restart_stdout_capture_required=$true;restart_stderr_capture_required=$true;failure_receipt_required=$true;automatic_mutation_retry=$false;runtime_authority=$false;promotion_eligible=$false}
    WriteJson $r $resultPath
    Write-Output ('PNCC_STABLE_PRIMARY_1081_LIVE_CONTROLLED_RESTART='+$r.state+' PHYSICAL_EXECUTION_ALLOWED=false MUTATION_EXECUTED=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
    if($ok){exit 0}else{exit 50}
}

if($env:OS-cne'Windows_NT'){throw 'Live mode requires Windows'}
if(-not$OwnerAuthorizationPath-or-not(Test-Path -LiteralPath $OwnerAuthorizationPath -PathType Leaf)){throw 'DEFAULT_DENY: valid OwnerAuthorizationPath required for Live mutation'}
if(-not(Test-Path -LiteralPath $RepositoryRoot -PathType Container)){throw 'RepositoryRoot missing'}
$head=(& git -C $RepositoryRoot rev-parse HEAD).Trim();if($LASTEXITCODE-ne0-or-not$head){throw 'cannot resolve exact repository HEAD'}
$token=Get-Content -LiteralPath $OwnerAuthorizationPath -Raw -Encoding UTF8|ConvertFrom-Json
if([string]$token.contract_id-cne'PNCC_OWNER_ONE_SHOT_PRIMARY_1081_RESTART_V1'){throw 'owner token contract mismatch'}
if([string]$token.action-cne'CONTROLLED_RESTART_PRIMARY_1081'){throw 'owner token action mismatch'}
if(-not[bool]$token.execute){throw 'owner token does not authorize execution'}
if([string]$token.main_sha-cne$head){throw 'owner token exact main SHA mismatch'}
if([string]$token.authorization_contract-cne'PNCC_STABLE_PRIMARY_1081_MUTATION_AUTHORIZATION_V1'-or[string]$token.authorization_state-cne'AUTHORIZATION_ADMITTED'){throw 'owner token mutation authorization mismatch'}
$expires=[DateTimeOffset]::Parse([string]$token.expires_utc).ToUniversalTime();$now=[DateTimeOffset]::UtcNow;if($expires-le$now-or$expires-gt$now.AddMinutes(10)){throw 'owner token expired or validity window exceeds 10 minutes'}
$reserveBefore=Snap $ReservePort;if(-not$reserveBefore.listening){throw '1080 reserve is not listening'}
$before=Primary;if(-not$before.Putty-or-not$before.Binding-or-not$before.Pwfile-or-not$before.NoPlainPw){throw 'current 1081 secure identity contract failed'}
$wd=Watchdog
if([int]$token.target_pid-ne$before.Pid-or[string]$token.target_executable-cne$before.Exe-or[string]$token.target_fingerprint-cne$before.Fingerprint){throw 'owner token exact target identity/fingerprint mismatch'}
$preRoute=SocksIdentity;$preRouteAttempts=$script:RouteProbeLastAttempts
$again=Primary;if($again.Pid-ne$before.Pid-or$again.Exe-cne$before.Exe-or$again.Fingerprint-cne$before.Fingerprint){throw 'immediate pre-mutation target revalidation failed'}
$wd2=Watchdog;if($wd2.Engine-cne$wd.Engine){throw 'Watchdog engine changed during authorization window'}
$consumed=$OwnerAuthorizationPath+'.consumed';if(Test-Path -LiteralPath $consumed){throw 'owner token already consumed'};Move-Item -LiteralPath $OwnerAuthorizationPath -Destination $consumed -ErrorAction Stop

$restartWrapper=Join-Path $OutputDirectory 'restart-tunnel-wrapper.cmd'
Remove-Item $restartStdout,$restartStderr,$restartWrapper -Force -ErrorAction SilentlyContinue
function BatchEscape([string]$Value){if($null-eq$Value){return ''};return $Value.Replace('%','%%')}
$wrapperLines=@(
    '@echo off',
    ('"{0}" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "{1}" -Action RestartTunnel -NoAppLaunch 1>"{2}" 2>"{3}"' -f (BatchEscape $PsExe),(BatchEscape $wd2.Engine),(BatchEscape $restartStdout),(BatchEscape $restartStderr)),
    'exit /b %ERRORLEVEL%'
)
[IO.File]::WriteAllLines($restartWrapper,$wrapperLines,[Text.Encoding]::ASCII)
$p=Start-Process $env:ComSpec -ArgumentList ('/d /c "'+$restartWrapper+'"') -PassThru -WindowStyle Hidden
$restartTimedOut=$false
if(-not$p.WaitForExit(120000)){$restartTimedOut=$true;try{$p.Kill()}catch{};try{$p.WaitForExit(5000)|Out-Null}catch{}}
$p.Refresh()
$restartExitCode=$(if($restartTimedOut){124}else{[int]$p.ExitCode})

if($restartTimedOut-or$restartExitCode-ne0){
    $postFailure=TryPostFailureState $reserveBefore
    $failureState=$(if($restartTimedOut){'RESTART_TUNNEL_TIMEOUT'}elseif([bool]$postFailure.runtime_healthy){'RESTART_TUNNEL_FAILED_RUNTIME_HEALTHY'}else{'RESTART_TUNNEL_FAILED_RUNTIME_UNHEALTHY'})
    $failureReceipt=[ordered]@{
        schema_version=1
        contract_id='PNCC_STABLE_PRIMARY_1081_LIVE_CONTROLLED_RESTART_V1'
        mode='Live'
        state=$failureState
        main_sha=$head
        owner_authorization_consumed=$true
        mutation_executed=$true
        runtime_mutation=$true
        reserve_1080_mutation=(-not[bool]$postFailure.reserve_1080_unchanged)
        primary_1081_tunnel_mutation=$true
        restart_tunnel_invoked=$true
        restart_tunnel_timed_out=$restartTimedOut
        restart_tunnel_exit_code=[int]$restartExitCode
        restart_stdout_file='restart-tunnel.stdout.log'
        restart_stderr_file='restart-tunnel.stderr.log'
        post_failure=$postFailure
        automatic_mutation_retry=$false
        runtime_authority=$false
        promotion_eligible=$false
    }
    WriteJson $failureReceipt $resultPath
    Write-Output ('PNCC_STABLE_PRIMARY_1081_LIVE_CONTROLLED_RESTART='+$failureState+' RESTART_TUNNEL_EXIT_CODE='+$restartExitCode+' AUTOMATIC_MUTATION_RETRY=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
    Write-Output ('RESULT='+$resultPath)
    if($restartTimedOut){exit 62}else{exit 61}
}

$deadline=(Get-Date).AddSeconds(45);$after=$null;while((Get-Date)-lt$deadline){try{$after=Primary;if($after){break}}catch{};Start-Sleep -Milliseconds 500};if($null-eq$after){throw 'post-restart 1081 listener missing'}
if(-not$after.Putty-or-not$after.Binding-or-not$after.Pwfile-or-not$after.NoPlainPw){throw 'post-restart 1081 secure identity contract failed'}
$postRoute=SocksIdentity;$postRouteAttempts=$script:RouteProbeLastAttempts;if($postRoute-cne$preRoute){throw 'post-restart routed identity changed'}
$wd3=Watchdog;if($wd3.Engine-cne$wd.Engine){throw 'post-restart Watchdog exact engine mismatch'}
$reserveAfter=Snap $ReservePort;if((Key $reserveBefore)-cne(Key $reserveAfter)){throw 'CRITICAL 1080 snapshot changed'}
$r=[ordered]@{schema_version=1;contract_id='PNCC_STABLE_PRIMARY_1081_LIVE_CONTROLLED_RESTART_V1';mode='Live';state='CONTROLLED_RESTART_PASS';main_sha=$head;owner_authorization_consumed=$true;mutation_executed=$true;runtime_mutation=$true;reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$true;restart_tunnel_invoked=$true;restart_tunnel_timed_out=$false;restart_tunnel_exit_code=0;restart_stdout_file='restart-tunnel.stdout.log';restart_stderr_file='restart-tunnel.stderr.log';pre_target_pid=$before.Pid;post_target_pid=$after.Pid;target_identity_rotated=($before.Pid-ne$after.Pid);secure_pwfile_post=$after.Pwfile;plain_pw_post=(-not$after.NoPlainPw);routed_identity_match=$true;route_probe_pre_attempts=$preRouteAttempts;route_probe_post_attempts=$postRouteAttempts;watchdog_exact_engine=$true;reserve_1080_unchanged=$true;automatic_mutation_retry=$false;runtime_authority=$false;promotion_eligible=$false}
WriteJson $r $resultPath
Write-Output 'PNCC_STABLE_PRIMARY_1081_LIVE_CONTROLLED_RESTART=CONTROLLED_RESTART_PASS MUTATION_EXECUTED=true RUNTIME_MUTATION=true RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false'
Write-Output ('RESULT='+$resultPath)
exit 0
