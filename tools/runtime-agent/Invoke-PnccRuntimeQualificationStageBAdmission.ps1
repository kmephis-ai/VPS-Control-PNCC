#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$WorkspacePath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('Live','Fixture')][string]$Mode='Live',
    [string]$FixturePath,
    [string]$V631Path,
    [string]$StageAResultPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'

$ExpectedV631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$ExpectedPrimaryPort=1081
$ExpectedReservePort=1080
$ExpectedReserveLifecycle='MANUAL_ONLY'
$ExpectedPuttyPasswordArgument='-pwfile'
$StateDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$WatchdogPidFile=Join-Path $StateDir 'watchdog.pid'
$WatchdogHeartbeatFile=Join-Path $StateDir 'watchdog-heartbeat.json'

function Get-Sha256([string]$Path){return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Write-JsonUtf8Bom($Value,[string]$Path){$parent=Split-Path -Parent $Path;if($parent){New-Item -ItemType Directory -Force -Path $parent|Out-Null};$json=$Value|ConvertTo-Json -Depth 14;[IO.File]::WriteAllText($Path,$json,(New-Object Text.UTF8Encoding($true)))}
function Snapshot-Port([int]$Port){
    $rows=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue)
    $items=@()
    foreach($row in $rows){
        $name='UNKNOWN';$path=''
        try{$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$row.OwningProcess) -ErrorAction Stop;$name=[string]$p.Name;$path=[string]$p.ExecutablePath}catch{}
        $items += [ordered]@{pid=[int]$row.OwningProcess;process=$name;path=$path}
    }
    return [ordered]@{port=$Port;listening=($rows.Count -gt 0);owners=@($items|Sort-Object pid)}
}
function Snapshot-Key($Value){return ($Value|ConvertTo-Json -Depth 8 -Compress)}
function Get-StageAPath {
    if($StageAResultPath){return $StageAResultPath}
    $root=Join-Path $WorkspacePath 'private-evidence'
    if(-not(Test-Path -LiteralPath $root -PathType Container)){return ''}
    $candidate=@(Get-ChildItem -LiteralPath $root -Filter 'runtime-qualification-stage-a-result.json' -File -Recurse -ErrorAction SilentlyContinue|Sort-Object LastWriteTime -Descending|Select-Object -First 1)
    if($candidate.Count -eq 1){return [string]$candidate[0].FullName}
    return ''
}
function Get-EnginePathFromCommandLine([string]$CommandLine){
    if([string]::IsNullOrWhiteSpace($CommandLine)){return ''}
    $m=[regex]::Match($CommandLine,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))')
    if(-not$m.Success){return ''}
    foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}}
    return ''
}
function Get-PrimaryProcess([int]$PrimaryPort){
    $rows=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue)
    if($rows.Count -ne 1){return $null}
    try{return Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$rows[0].OwningProcess) -ErrorAction Stop}catch{return $null}
}

if(-not(Test-Path -LiteralPath $WorkspacePath -PathType Container)){throw "workspace not found: $WorkspacePath"}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$evidencePath=Join-Path $OutputDirectory 'stage-b-admission-evidence.json'
$resultPath=Join-Path $OutputDirectory 'stage-b-admission-result.json'
$ready=$false
$failure=$null
$observations=[ordered]@{}

if($Mode -eq 'Fixture'){
    if([string]::IsNullOrWhiteSpace($FixturePath)-or -not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
    $f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json
    $checks=[ordered]@{
        stage_a_ready=[bool]$f.stage_a_ready
        candidate_identity=[bool]$f.candidate_identity
        rollback_identity=[bool]$f.rollback_identity
        watchdog_present=[bool]$f.watchdog_present
        watchdog_fresh=[bool]$f.watchdog_fresh
        watchdog_exact_engine=[bool]$f.watchdog_exact_engine
        primary_owner_putty=[bool]$f.primary_owner_putty
        primary_binding_1081=[bool]$f.primary_binding_1081
        plaintext_pw_absent=[bool]$f.plaintext_pw_absent
        reserve_unchanged=[bool]$f.reserve_unchanged
    }
    $ready=(@($checks.Values|Where-Object{-not$_}).Count -eq 0)
    $observations.fixture='synthetic'
}else{
    if($env:OS -ne 'Windows_NT'){throw 'Live mode requires Windows'}
    $manifestPath=Join-Path $WorkspacePath 'workspace-manifest.json'
    $requestPath=Join-Path $WorkspacePath 'request\runtime-qualification-request.json'
    if(-not(Test-Path -LiteralPath $manifestPath -PathType Leaf)){throw 'workspace manifest missing'}
    if(-not(Test-Path -LiteralPath $requestPath -PathType Leaf)){throw 'qualification request missing'}
    $manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8|ConvertFrom-Json
    $request=Get-Content -LiteralPath $requestPath -Raw -Encoding UTF8|ConvertFrom-Json
    if([int]$manifest.schema_version -ne 2 -or [string]$manifest.bootstrap_id -cne 'PNCC_RUNTIME_WORKSPACE_BOOTSTRAP_V2'){throw 'Stable V2 workspace required'}

    $requestId=[string]$request.request_id
    $candidateId=[string]$request.candidate.candidate_id
    $sourceSha=[string]$request.candidate.source_sha
    $artifactName=[string]$request.candidate.artifact_filename
    $artifactSha=[string]$request.candidate.artifact_sha256
    $artifactSize=[long]$request.candidate.artifact_size_bytes
    $primaryPort=[int]$request.expected_invariants.primary_auto_port
    $reservePort=[int]$request.expected_invariants.reserve_manual_port
    $reserveLifecycle=[string]$request.expected_invariants.reserve_manual_lifecycle
    $v631Sha=[string]$request.expected_invariants.v6_3_1_sha256
    $puttyPasswordArgument=[string]$request.expected_invariants.putty_password_argument
    $plaintextAllowed=[bool]$request.expected_invariants.plaintext_pw_allowed
    $hostkeyDisableAllowed=[bool]$request.expected_invariants.hostkey_verification_disable_allowed

    if([string]::IsNullOrWhiteSpace($requestId)-or[string]::IsNullOrWhiteSpace($candidateId)-or[string]::IsNullOrWhiteSpace($sourceSha)){throw 'request identity incomplete'}
    if($primaryPort -ne $ExpectedPrimaryPort -or $reservePort -ne $ExpectedReservePort -or $reserveLifecycle -cne $ExpectedReserveLifecycle){throw 'tunnel invariant mismatch'}
    if($v631Sha -cne $ExpectedV631Sha){throw 'V6.3.1 invariant mismatch'}
    if($puttyPasswordArgument -cne $ExpectedPuttyPasswordArgument -or $plaintextAllowed -or $hostkeyDisableAllowed){throw 'credential/hostkey invariant mismatch'}
    if([string]$manifest.request_provider.request_id -cne $requestId){throw 'workspace/request request_id mismatch'}
    if([string]$manifest.candidate.candidate_id -cne $candidateId -or [string]$manifest.candidate.source_sha -cne $sourceSha){throw 'workspace/request candidate identity mismatch'}
    if([string]$manifest.candidate.artifact_filename -cne $artifactName -or [string]$manifest.candidate.artifact_sha256 -cne $artifactSha -or [long]$manifest.candidate.artifact_size_bytes -ne $artifactSize){throw 'workspace/request artifact identity mismatch'}

    $stageAPath=Get-StageAPath
    if(-not$stageAPath-or-not(Test-Path -LiteralPath $stageAPath -PathType Leaf)){throw 'Stage-A result missing'}
    $stageA=Get-Content -LiteralPath $stageAPath -Raw -Encoding UTF8|ConvertFrom-Json
    $stageAFails=@($stageA.checks|Where-Object{$_.result -eq 'FAIL'})
    $requiredPass=@('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')
    $requiredNotExecuted=@('WATCHDOG_LIFECYCLE','PROXIFIER_DESCENDANT_CLEANUP','CREDENTIAL_HOSTKEY')
    $stageAReady=([string]$stageA.request_id -cne '' -and [string]$stageA.request_id -ceq $requestId -and $stageA.qualification_state -eq 'BLOCKED' -and $stageAFails.Count -eq 0 -and -not[bool]$stageA.runtime_authority -and -not[bool]$stageA.promotion_eligible)
    foreach($scope in $requiredPass){if(@($stageA.checks|Where-Object{$_.scope -eq $scope -and $_.result -eq 'PASS'}).Count -ne 1){$stageAReady=$false}}
    foreach($scope in $requiredNotExecuted){if(@($stageA.checks|Where-Object{$_.scope -eq $scope -and $_.result -eq 'NOT_EXECUTED'}).Count -ne 1){$stageAReady=$false}}

    $artifact=Join-Path (Join-Path $WorkspacePath 'candidate-provider-artifact') $artifactName
    $artifactOk=$false
    if(Test-Path -LiteralPath $artifact -PathType Leaf){$info=Get-Item -LiteralPath $artifact;$artifactOk=([long]$info.Length -eq $artifactSize -and (Get-Sha256 $artifact) -ceq $artifactSha)}
    $rollbackOk=$false
    if($V631Path -and(Test-Path -LiteralPath $V631Path -PathType Leaf)){$rollbackOk=((Get-Sha256 $V631Path)-ceq$v631Sha)}

    $reserveBefore=Snapshot-Port $reservePort
    $primaryBefore=Snapshot-Port $primaryPort
    $primaryProc=Get-PrimaryProcess $primaryPort
    $primaryOwnerPutty=$false;$primaryBinding=$false;$plaintextPwAbsent=$false;$pwfilePresent=$false
    if($null-ne$primaryProc){
        $n=[string]$primaryProc.Name;$cmd=[string]$primaryProc.CommandLine
        $primaryOwnerPutty=($n -match '(?i)^(putty|putty_portable|plink)\.exe$')
        $primaryBinding=($cmd -match ('(?i)(?:^|\s)-D\s+(?:"?127\.0\.0\.1:{0}"?)(?:\s|$)' -f $primaryPort))
        $plaintextPwAbsent=($cmd -notmatch '(?i)(?:^|\s)-pw(?:\s|=)')
        $pwfilePresent=($cmd -match '(?i)(?:^|\s)-pwfile(?:\s|=)')
    }

    $watchdogPresent=$false;$watchdogFresh=$false;$watchdogExactEngine=$false;$watchdogAction=$false;$liveEnginePath='';$liveEngineSha='';$generatedEngineSha=''
    if(Test-Path -LiteralPath $WatchdogPidFile -PathType Leaf){
        try{
            $watchPid=[int](Get-Content -LiteralPath $WatchdogPidFile -Raw).Trim()
            $wp=Get-CimInstance Win32_Process -Filter ('ProcessId='+$watchPid) -ErrorAction Stop
            $watchdogPresent=$true
            $wcmd=[string]$wp.CommandLine
            $watchdogAction=($wcmd -match '(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)')
            $liveEnginePath=Get-EnginePathFromCommandLine $wcmd
            if(Test-Path -LiteralPath $WatchdogHeartbeatFile -PathType Leaf){$age=[int]((Get-Date)-(Get-Item -LiteralPath $WatchdogHeartbeatFile).LastWriteTime).TotalSeconds;$watchdogFresh=($age -ge 0 -and $age -le 240);$observations.watchdog_heartbeat_age_seconds=$age}
        }catch{}
    }

    $work=Join-Path $OutputDirectory 'admission-temp'
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $work|Out-Null
    if($artifactOk-and$rollbackOk){
        $extract=Join-Path $work 'candidate'
        Expand-Archive -LiteralPath $artifact -DestinationPath $extract -Force
        $upgrade=@(Get-ChildItem -LiteralPath $extract -Filter 'VPS-Control-v7-engine-upgrade.ps1' -File -Recurse|Select-Object -First 1)
        if($upgrade.Count -eq 1){
            $generatorDir=Join-Path $work 'generator-input'
            New-Item -ItemType Directory -Force -Path $generatorDir|Out-Null
            $stagedV631=Join-Path $generatorDir 'VPS-Control-v6.3.1.staged.ps1'
            $generated=Join-Path $generatorDir 'VPS-Control-v6.5.generated.ps1'
            Copy-Item -LiteralPath $V631Path -Destination $stagedV631 -Force
            if((Get-Sha256 $stagedV631)-cne$v631Sha){throw 'Stage-B staged V6.3.1 identity mismatch'}
            $out=Join-Path $work 'generator.out.txt';$err=Join-Path $work 'generator.err.txt'
            $ps=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
            $args='-NoLogo -NoProfile -ExecutionPolicy Bypass -File "'+$upgrade[0].FullName+'" -SourcePath "'+$stagedV631+'" -DestinationPath "'+$generated+'"'
            $proc=Start-Process -FilePath $ps -ArgumentList $args -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
            $proc.Refresh()
            if($proc.ExitCode -ne 0-or-not(Test-Path -LiteralPath $generated -PathType Leaf)){throw 'Stage-B exact engine generation failed'}
            $generatedEngineSha=Get-Sha256 $generated
        }
    }
    if($liveEnginePath-and(Test-Path -LiteralPath $liveEnginePath -PathType Leaf)){$liveEngineSha=Get-Sha256 $liveEnginePath}
    $watchdogExactEngine=($watchdogPresent-and$watchdogAction-and$generatedEngineSha-and$liveEngineSha-and$generatedEngineSha-eq$liveEngineSha)

    $reserveAfter=Snapshot-Port $reservePort
    $reserveUnchanged=((Snapshot-Key $reserveBefore)-eq(Snapshot-Key $reserveAfter))
    $checks=[ordered]@{
        stage_a_ready=[bool]$stageAReady
        candidate_identity=[bool]$artifactOk
        rollback_identity=[bool]$rollbackOk
        watchdog_present=[bool]$watchdogPresent
        watchdog_fresh=[bool]$watchdogFresh
        watchdog_exact_engine=[bool]$watchdogExactEngine
        primary_owner_putty=[bool]$primaryOwnerPutty
        primary_binding_1081=[bool]$primaryBinding
        plaintext_pw_absent=[bool]$plaintextPwAbsent
        reserve_unchanged=[bool]$reserveUnchanged
    }
    $ready=(@($checks.Values|Where-Object{-not$_}).Count -eq 0)
    if(-not$ready){$failure='ENVIRONMENT_OR_BASELINE_BLOCKER'}
    $observations.request_id=$requestId;$observations.candidate_id=$candidateId;$observations.source_sha=$sourceSha;$observations.stage_a_result=[IO.Path]::GetFileName($stageAPath)
    $observations.reserve_before=$reserveBefore;$observations.reserve_after=$reserveAfter;$observations.primary_before=$primaryBefore
    $observations.primary_owner_putty=$primaryOwnerPutty;$observations.primary_binding_1081=$primaryBinding;$observations.plaintext_pw_absent=$plaintextPwAbsent;$observations.pwfile_present=$pwfilePresent
    $observations.watchdog_present=$watchdogPresent;$observations.watchdog_fresh=$watchdogFresh;$observations.watchdog_action_watchdog=$watchdogAction
    $observations.live_engine_path=$liveEnginePath;$observations.live_engine_sha256=$liveEngineSha;$observations.generated_engine_sha256=$generatedEngineSha;$observations.exact_engine_match=$watchdogExactEngine
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}

$evidence=[ordered]@{schema_version=2;contract_id='PNCC_RUNTIME_STAGE_B_ADMISSION_EVIDENCE_V2';mode=$Mode;runtime_mutation=$false;reserve_manual_mutation=$false;primary_lifecycle_mutation=$false;checks=$checks;observations=$observations}
Write-JsonUtf8Bom $evidence $evidencePath
$state=if($ready){'READY_FOR_LIFECYCLE'}else{'BLOCKED'}
$result=[ordered]@{schema_version=2;contract_id='PNCC_RUNTIME_STAGE_B_ADMISSION_V2';state=$state;failure_classification=$failure;evidence_sha256=(Get-Sha256 $evidencePath);runtime_mutation=$false;runtime_authority=$false;promotion_eligible=$false;next_action=if($ready){'CONTROLLED_PRIMARY_1081_RESTART'}else{'RESOLVE_ADMISSION_BLOCKERS'}}
Write-JsonUtf8Bom $result $resultPath
Write-Output "PNCC_RUNTIME_STAGE_B_ADMISSION=$state MODE=$Mode RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
Write-Output "STAGE_B_ADMISSION_RESULT=$resultPath"
Write-Output "STAGE_B_ADMISSION_EVIDENCE=$evidencePath"
exit 0