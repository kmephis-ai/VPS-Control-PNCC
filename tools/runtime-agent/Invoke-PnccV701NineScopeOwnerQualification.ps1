#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Live','Plan')][string]$Mode='Live',
    [string]$OutputRoot='E:\!Chrome_Downloads',
    [string]$V631Path,
    [string]$FixturePath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'

$RunnerVersion='0.1.0'
$Repository='kmephis-ai/VPS-Control-PNCC'
$ControlPlaneSha='157b32a407ff60acc0447b4f4e0229d74a886856'
$ExpectedRequestId='PNCC-RQ-V7.0.1-D58023321360'
$ExpectedCandidateId='PNCC-V7.0.1-D58023321360'
$ExpectedSourceSha='d5802332136087339482c9b3171c1c5c9c18411e'
$ExpectedCandidateFilename='VPS-Control-v7.0.1.zip'
$ExpectedCandidateSha='22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
$ExpectedCandidateSize=[long]701893
$ExpectedCandidateProviderArtifactId=[long]9711822972
$ExpectedCandidateProviderName='PNCC-CANDIDATE-d5802332136087339482c9b3171c1c5c9c18411e'
$ExpectedCandidateProviderDigest='sha256:47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5'
$ExpectedRequestProviderArtifactId=[long]9711823182
$ExpectedProviderBuildRunId=[long]33242642394
$ExpectedRequestProviderName='PNCC-RUNTIME-REQUEST-d5802332136087339482c9b3171c1c5c9c18411e'
$ExpectedRequestProviderDigest='sha256:ac76b2cc60512c2a4a3b83095c82804f586d42d843439467f0d53fb52d71c844'
$ExpectedV631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$ExpectedEngineSha='843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'
$ExpectedScopes=@(
    'WINDOWS_BASELINE',
    'PROCESS_OWNERSHIP_BASELINE',
    'WATCHDOG_LIFECYCLE',
    'PROXIFIER_DESCENDANT_CLEANUP',
    'PRIMARY_AUTO_1081',
    'RESERVE_MANUAL_1080',
    'CREDENTIAL_HOSTKEY',
    'NETWORK_QUALIFICATION',
    'ROLLBACK_IDENTITY'
)
$PrimaryPort=1081
$ReservePort=1080
$PsExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$script:RunDirectory=''
$script:ControlRoot=''
$script:PrivateRoot=''
$script:StepLogRoot=''

function Get-Sha256([string]$Path){
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-JsonUtf8Bom($Value,[string]$Path){
    $parent=Split-Path -Parent $Path
    if($parent){New-Item -ItemType Directory -Force -Path $parent|Out-Null}
    [IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 24),(New-Object Text.UTF8Encoding($true)))
}

function Read-Json([string]$Path){
    if(-not(Test-Path -LiteralPath $Path -PathType Leaf)){throw ('JSON file missing: '+$Path)}
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8|ConvertFrom-Json)
}

function Assert-True([bool]$Condition,[string]$Message){
    if(-not$Condition){throw $Message}
}

function Assert-Equal([string]$Actual,[string]$Expected,[string]$Label){
    if($Actual -cne $Expected){throw ($Label+' mismatch')}
}

function Get-ProcessInfo([int]$ProcessId){
    try{return Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{return $null}
}

function Get-PortSnapshot([int]$Port){
    $rows=@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    $items=@()
    foreach($row in $rows){
        $p=Get-ProcessInfo ([int]$row.OwningProcess)
        $items += [ordered]@{
            local_address=[string]$row.LocalAddress
            local_port=[int]$row.LocalPort
            pid=[int]$row.OwningProcess
            process=$(if($p){[string]$p.Name}else{''})
            executable=$(if($p){[string]$p.ExecutablePath}else{''})
        }
    }
    return [ordered]@{port=$Port;listeners=@($items|Sort-Object local_address,pid)}
}

function Get-SnapshotKey($Value){
    return ($Value|ConvertTo-Json -Depth 10 -Compress)
}

function Format-NativeArgument([string]$Value){
    if($Value -match '^-[A-Za-z][A-Za-z0-9-]*$'){return $Value}
    return ('"'+$Value.Replace('"','\"')+'"')
}

function Invoke-ChildPowerShell([string]$Name,[string]$ScriptPath,[string[]]$Arguments,[int]$TimeoutSeconds=360){
    if(-not(Test-Path -LiteralPath $ScriptPath -PathType Leaf)){throw ('child script missing: '+$ScriptPath)}
    New-Item -ItemType Directory -Force -Path $script:StepLogRoot|Out-Null
    $stdout=Join-Path $script:StepLogRoot ($Name+'.stdout.txt')
    $stderr=Join-Path $script:StepLogRoot ($Name+'.stderr.txt')
    Remove-Item -LiteralPath $stdout,$stderr -Force -ErrorAction SilentlyContinue
    $argLine='-NoLogo -NoProfile -ExecutionPolicy Bypass -File '+(Format-NativeArgument $ScriptPath)
    foreach($a in $Arguments){$argLine+=' '+(Format-NativeArgument ([string]$a))}
    $p=Start-Process -FilePath $PsExe -ArgumentList $argLine -WorkingDirectory $script:ControlRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $timedOut=$false
    if(-not$p.WaitForExit($TimeoutSeconds*1000)){
        $timedOut=$true
        try{$p.Kill()}catch{}
        try{$p.WaitForExit(5000)|Out-Null}catch{}
    }
    $p.Refresh()
    $exitCode=$(if($timedOut){124}else{[int]$p.ExitCode})
    return [pscustomobject]@{Name=$Name;ExitCode=$exitCode;TimedOut=$timedOut;Stdout=$stdout;Stderr=$stderr}
}

function Assert-ChildPass($Step){
    if([bool]$Step.TimedOut){throw ($Step.Name+' timed out')}
    if([int]$Step.ExitCode -ne 0){
        $tail=''
        if(Test-Path -LiteralPath $Step.Stderr -PathType Leaf){$tail=(Get-Content -LiteralPath $Step.Stderr -Tail 8 -ErrorAction SilentlyContinue)-join' | '}
        throw ($Step.Name+' failed exit='+[string]$Step.ExitCode+' stderr='+$tail)
    }
}

function Get-GhArtifactMetadata([long]$ArtifactId){
    $raw=& gh api ('repos/{0}/actions/artifacts/{1}' -f $Repository,$ArtifactId) 2>&1
    if($LASTEXITCODE -ne 0){throw ('gh artifact metadata failed id='+$ArtifactId)}
    try{return (($raw-join"`n")|ConvertFrom-Json)}catch{throw ('gh artifact metadata JSON invalid id='+$ArtifactId)}
}

function Download-GhArtifact([long]$RunId,[string]$Name,[string]$Destination){
    New-Item -ItemType Directory -Force -Path $Destination|Out-Null
    $out=& gh run download $RunId --repo $Repository --name $Name --dir $Destination 2>&1
    if($LASTEXITCODE -ne 0){throw ('gh run download failed artifact='+$Name+' output='+(($out|Select-Object -Last 5)-join' | '))}
}

function Download-ControlFile([string]$RelativePath){
    $dest=Join-Path $script:ControlRoot ($RelativePath -replace '/','\')
    $parent=Split-Path -Parent $dest
    New-Item -ItemType Directory -Force -Path $parent|Out-Null
    $uri='https://raw.githubusercontent.com/'+$Repository+'/'+$ControlPlaneSha+'/'+$RelativePath
    Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $dest
    if(-not(Test-Path -LiteralPath $dest -PathType Leaf)){throw ('control file download missing: '+$RelativePath)}
    $tokens=$null;$errors=$null
    [void][System.Management.Automation.Language.Parser]::ParseFile($dest,[ref]$tokens,[ref]$errors)
    if(@($errors).Count -ne 0){throw ('control file PowerShell parse failed: '+$RelativePath)}
    return $dest
}

function Resolve-V631([string]$RequestedPath){
    if($RequestedPath){
        if(-not(Test-Path -LiteralPath $RequestedPath -PathType Leaf)){throw 'supplied V6.3.1 path missing'}
        if((Get-Sha256 $RequestedPath)-cne$ExpectedV631Sha){throw 'supplied V6.3.1 SHA mismatch'}
        return [IO.Path]::GetFullPath($RequestedPath)
    }
    $roots=New-Object Collections.Generic.List[string]
    foreach($r in @($OutputRoot,'M:\YandexDisk\!Coding\VPS-Control',(Get-Location).Path)){
        if($r-and(Test-Path -LiteralPath $r -PathType Container)-and-not$roots.Contains($r)){[void]$roots.Add($r)}
    }
    foreach($root in $roots){
        foreach($f in @(Get-ChildItem -LiteralPath $root -File -Filter 'VPS-Control-v6.3.1.ps1' -Recurse -ErrorAction SilentlyContinue|Sort-Object LastWriteTime -Descending)){
            try{if((Get-Sha256 $f.FullName)-ceq$ExpectedV631Sha){return $f.FullName}}catch{}
        }
    }
    throw 'exact immutable VPS-Control-v6.3.1.ps1 not found in governed search roots'
}

function Get-Check($Stage,[string]$Scope){
    return @($Stage.checks|Where-Object{[string]$_.scope -ceq $Scope})
}

function Require-StagePass($Stage,[string]$Scope){
    $c=@(Get-Check $Stage $Scope)
    if($c.Count -ne 1 -or [string]$c[0].result -cne 'PASS'){throw ('Stage-A scope not PASS: '+$Scope)}
}

function New-CanonicalCheck([string]$Scope,[string[]]$EvidenceRefs){
    return [ordered]@{scope=$Scope;result='PASS';exit_code=0;failure_class=$null;evidence_refs=@($EvidenceRefs)}
}

function Write-PlanResult([string]$State,[string[]]$Failed){
    $r=[ordered]@{
        schema_version=1
        contract_id='PNCC_V701_NINE_SCOPE_OWNER_QUALIFICATION_PLAN_V1'
        runner_version=$RunnerVersion
        state=$State
        failed_checks=@($Failed)
        runtime_execution_allowed=$false
        runtime_mutation=$false
        reserve_1080_mutation=$false
        primary_1081_tunnel_mutation=$false
        repository_authority_mutation=$false
        runtime_authority=$false
        promotion_eligible=$false
        release_or_tag_authorized=$false
    }
    $out=Join-Path $OutputRoot 'PNCC-WU087-plan-result.json'
    New-Item -ItemType Directory -Force -Path $OutputRoot|Out-Null
    Write-JsonUtf8Bom $r $out
    Write-Output ('PNCC_WU087_PLAN='+$State+' FAILED='+$Failed.Count+' RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
    Write-Output ('RESULT='+$out)
    if($Failed.Count -eq 0){exit 0}else{exit 50}
}

if($Mode -ceq 'Plan'){
    if(-not$FixturePath-or-not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required in Plan mode'}
    $f=Read-Json $FixturePath
    $names=@('request_identity','actual_provider_naming','stage_a_contract','primary_ownership_contract','watchdog_contract','proxifier_contract','credential_hostkey_contract','reserve_observation_only','private_result_contract','promotion_false')
    $failed=@()
    foreach($n in $names){if(-not[bool]$f.$n){$failed+=$n}}
    Write-PlanResult $(if($failed.Count-eq0){'PLAN_PASS'}else{'BLOCKED'}) $failed
}

if($env:OS -cne 'Windows_NT'){throw 'Live mode requires Windows'}
if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -lt 1){throw 'Live mode requires Windows PowerShell 5.1'}
if(-not(Test-Path -LiteralPath $PsExe -PathType Leaf)){throw 'Windows PowerShell 5.1 executable missing'}
if(-not(Get-Command gh -ErrorAction SilentlyContinue)){throw 'gh.exe is required'}
if(-not(Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)){throw 'Get-NetTCPConnection is required'}

[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
New-Item -ItemType Directory -Force -Path $OutputRoot|Out-Null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$script:RunDirectory=Join-Path $OutputRoot ('PNCC-WU087-'+$stamp)
$script:ControlRoot=Join-Path $script:RunDirectory 'control-plane'
$workspace=Join-Path $script:RunDirectory 'workspace'
$requestProviderDir=Join-Path $workspace 'request-provider-artifact'
$candidateProviderDir=Join-Path $workspace 'candidate-provider-artifact'
$requestDir=Join-Path $workspace 'request'
$script:PrivateRoot=Join-Path $workspace 'private-evidence'
$publicRoot=Join-Path $workspace 'public-safe'
$script:StepLogRoot=Join-Path $script:PrivateRoot '00-step-logs'
foreach($d in @($script:RunDirectory,$script:ControlRoot,$workspace,$requestProviderDir,$candidateProviderDir,$requestDir,$script:PrivateRoot,$publicRoot,$script:StepLogRoot)){New-Item -ItemType Directory -Force -Path $d|Out-Null}
$logPath=Join-Path $script:RunDirectory 'PNCC-WU087.log'
$wrapperResultPath=Join-Path $script:RunDirectory 'wu087-owner-run-result.json'
$canonicalResultPath=Join-Path $script:RunDirectory 'runtime-qualification-result.json'
$returnZip=Join-Path $OutputRoot ('PNCC-WU087-RETURN-'+$stamp+'.zip')
$exitCode=50
$finalState='BLOCKED'
$failureMessage=$null
$transcriptStarted=$false

try{
    Start-Transcript -LiteralPath $logPath -Force|Out-Null
    $transcriptStarted=$true
    Write-Output ('PNCC WU-087 owner qualification runner v'+$RunnerVersion)
    Write-Output ('CONTROL_PLANE_SHA='+$ControlPlaneSha)
    Write-Output ('REQUEST_ID='+$ExpectedRequestId)
    Write-Output ('CANDIDATE_ID='+$ExpectedCandidateId)

    & gh auth status 1>$null 2>$null
    if($LASTEXITCODE -ne 0){throw 'gh authentication is required'}

    $v631=Resolve-V631 $V631Path
    Write-Output ('V631_PATH='+$v631)
    Write-Output ('V631_SHA256='+(Get-Sha256 $v631))

    $portsBefore=[ordered]@{reserve_1080=Get-PortSnapshot $ReservePort;primary_1081=Get-PortSnapshot $PrimaryPort}
    Assert-True (@($portsBefore.reserve_1080.listeners).Count -gt 0) '1080 reserve listener baseline missing'
    Assert-True (@($portsBefore.primary_1081.listeners).Count -gt 0) '1081 primary listener baseline missing'
    Write-JsonUtf8Bom $portsBefore (Join-Path $script:PrivateRoot 'ports-before.json')

    $requestMeta=Get-GhArtifactMetadata $ExpectedRequestProviderArtifactId
    Assert-True ([long]$requestMeta.id -eq $ExpectedRequestProviderArtifactId) 'request provider artifact id mismatch'
    Assert-Equal ([string]$requestMeta.name) $ExpectedRequestProviderName 'request provider artifact name'
    Assert-True (-not[bool]$requestMeta.expired) 'request provider artifact expired'
    Assert-Equal ([string]$requestMeta.digest) $ExpectedRequestProviderDigest 'request provider artifact digest'
    Assert-True ([long]$requestMeta.workflow_run.id -eq $ExpectedProviderBuildRunId) 'request provider build run mismatch'
    Assert-Equal ([string]$requestMeta.workflow_run.head_sha) $ExpectedSourceSha 'request provider source SHA'
    Download-GhArtifact $ExpectedProviderBuildRunId $ExpectedRequestProviderName $requestProviderDir

    $requestFiles=@(Get-ChildItem -LiteralPath $requestProviderDir -File -Filter '*.json')
    Assert-True ($requestFiles.Count -eq 1) 'exactly one runtime request JSON required'
    $request=Read-Json $requestFiles[0].FullName
    Assert-True ([int]$request.schema_version -eq 1) 'request schema mismatch'
    Assert-Equal ([string]$request.contract_id) 'PNCC_RUNTIME_QUALIFICATION_REQUEST_V1' 'request contract'
    Assert-Equal ([string]$request.request_id) $ExpectedRequestId 'request id'
    Assert-Equal ([string]$request.candidate.candidate_id) $ExpectedCandidateId 'candidate id'
    Assert-Equal ([string]$request.candidate.source_sha) $ExpectedSourceSha 'candidate source SHA'
    Assert-Equal ([string]$request.candidate.artifact_filename) $ExpectedCandidateFilename 'candidate filename'
    Assert-Equal ([string]$request.candidate.artifact_sha256) $ExpectedCandidateSha 'candidate artifact SHA'
    Assert-True ([long]$request.candidate.artifact_size_bytes -eq $ExpectedCandidateSize) 'candidate size mismatch'
    Assert-True ([long]$request.candidate.provider_artifact_id -eq $ExpectedCandidateProviderArtifactId) 'candidate provider id mismatch'
    Assert-Equal ('sha256:'+[string]$request.candidate.provider_artifact_digest) $ExpectedCandidateProviderDigest 'candidate provider digest'
    Assert-True ([long]$request.candidate.provider_build_run_id -eq $ExpectedProviderBuildRunId) 'candidate provider build run mismatch'
    Assert-True ([string]$request.state -ceq 'RUNTIME_PENDING') 'request state must be RUNTIME_PENDING'
    Assert-True (-not[bool]$request.runtime_authority) 'request cannot carry runtime authority'
    Assert-True (-not[bool]$request.promotion_eligible) 'request cannot carry promotion eligibility'
    Assert-True ([int]$request.expected_invariants.primary_auto_port -eq $PrimaryPort) 'PRIMARY_AUTO invariant mismatch'
    Assert-True ([int]$request.expected_invariants.reserve_manual_port -eq $ReservePort) 'RESERVE_MANUAL invariant mismatch'
    Assert-Equal ([string]$request.expected_invariants.reserve_manual_lifecycle) 'MANUAL_ONLY' 'reserve lifecycle'
    Assert-Equal ([string]$request.expected_invariants.v6_3_1_sha256) $ExpectedV631Sha 'rollback invariant'
    Assert-Equal ([string]$request.expected_invariants.putty_password_argument) '-pwfile' 'PuTTY password transport'
    Assert-True (-not[bool]$request.expected_invariants.plaintext_pw_allowed) 'plaintext password transport cannot be allowed'
    Assert-True (-not[bool]$request.expected_invariants.hostkey_verification_disable_allowed) 'host-key verification disable cannot be allowed'
    $actualScopes=@($request.required_scopes|ForEach-Object{[string]$_})
    Assert-True ($actualScopes.Count -eq $ExpectedScopes.Count) 'scope count mismatch'
    for($i=0;$i-lt$ExpectedScopes.Count;$i++){Assert-Equal $actualScopes[$i] $ExpectedScopes[$i] ('scope index '+$i)}
    Copy-Item -LiteralPath $requestFiles[0].FullName -Destination (Join-Path $requestDir 'runtime-qualification-request.json') -Force

    $candidateMeta=Get-GhArtifactMetadata $ExpectedCandidateProviderArtifactId
    Assert-True ([long]$candidateMeta.id -eq $ExpectedCandidateProviderArtifactId) 'candidate provider artifact id mismatch'
    Assert-Equal ([string]$candidateMeta.name) $ExpectedCandidateProviderName 'candidate provider artifact name'
    Assert-True (-not[bool]$candidateMeta.expired) 'candidate provider artifact expired'
    Assert-Equal ([string]$candidateMeta.digest) $ExpectedCandidateProviderDigest 'candidate provider artifact digest'
    Assert-True ([long]$candidateMeta.workflow_run.id -eq $ExpectedProviderBuildRunId) 'candidate provider build run mismatch'
    Assert-Equal ([string]$candidateMeta.workflow_run.head_sha) $ExpectedSourceSha 'candidate provider source SHA'
    Download-GhArtifact $ExpectedProviderBuildRunId $ExpectedCandidateProviderName $candidateProviderDir

    $candidatePath=Join-Path $candidateProviderDir $ExpectedCandidateFilename
    Assert-True (Test-Path -LiteralPath $candidatePath -PathType Leaf) 'candidate ZIP missing from provider artifact'
    Assert-True ((Get-Item -LiteralPath $candidatePath).Length -eq $ExpectedCandidateSize) 'candidate ZIP size mismatch'
    Assert-Equal (Get-Sha256 $candidatePath) $ExpectedCandidateSha 'candidate ZIP SHA256'
    $candidateManifest=Read-Json (Join-Path $candidateProviderDir 'candidate-manifest.json')
    Assert-Equal ([string]$candidateManifest.candidate_id) $ExpectedCandidateId 'candidate manifest id'
    Assert-Equal ([string]$candidateManifest.source.commit_sha) $ExpectedSourceSha 'candidate manifest source'
    Assert-Equal ([string]$candidateManifest.artifact.filename) $ExpectedCandidateFilename 'candidate manifest filename'
    Assert-Equal ([string]$candidateManifest.artifact.sha256) $ExpectedCandidateSha 'candidate manifest SHA'
    Assert-True ([long]$candidateManifest.artifact.size_bytes -eq $ExpectedCandidateSize) 'candidate manifest size mismatch'
    Assert-Equal ([string]$candidateManifest.runtime.qualification_state) 'NOT_VERIFIED' 'candidate pre-runtime state'
    Assert-True (-not[bool]$candidateManifest.runtime.promotion_eligible) 'candidate cannot be promotion eligible before runtime'

    $workspaceManifest=[ordered]@{
        schema_version=2
        bootstrap_id='PNCC_RUNTIME_WORKSPACE_BOOTSTRAP_V2'
        created_utc=[DateTime]::UtcNow.ToString('o')
        mode='Provider'
        repository=$Repository
        request_provider=[ordered]@{artifact_id=$ExpectedRequestProviderArtifactId;artifact_name=$ExpectedRequestProviderName;artifact_digest=$ExpectedRequestProviderDigest;provider_build_run_id=$ExpectedProviderBuildRunId;source_sha=$ExpectedSourceSha;request_id=$ExpectedRequestId}
        candidate=[ordered]@{candidate_id=$ExpectedCandidateId;source_sha=$ExpectedSourceSha;artifact_filename=$ExpectedCandidateFilename;artifact_sha256=$ExpectedCandidateSha;artifact_size_bytes=$ExpectedCandidateSize;provider_artifact_id=$ExpectedCandidateProviderArtifactId;provider_artifact_name=$ExpectedCandidateProviderName;provider_artifact_digest=$ExpectedCandidateProviderDigest;provider_build_run_id=$ExpectedProviderBuildRunId}
        boundaries=[ordered]@{private_evidence='private-evidence';public_safe='public-safe';runtime_mutation_permitted=$false;runtime_authority=$false;promotion_eligible=$false}
    }
    Write-JsonUtf8Bom $workspaceManifest (Join-Path $workspace 'workspace-manifest.json')

    $helperStageA=Download-ControlFile 'tools/runtime-agent/Invoke-PnccRuntimeQualificationStageA.ps1'
    $helperOwnership=Download-ControlFile 'tools/runtime-agent/Test-PnccStablePrimary1081Ownership.ps1'
    $helperWatchdog=Download-ControlFile 'tools/runtime-agent/Test-PnccStableWatchdogLifecycleV2.ps1'
    $helperCredential=Download-ControlFile 'tools/runtime-agent/Test-PnccStableCredentialHostkeyV4.ps1'
    $helperProxifier=Download-ControlFile 'tools/runtime-agent/Test-PnccStableProxifierDescendantCleanup.ps1'
    [void](Download-ControlFile 'src/windows-v7/VPS-Control-v7-tunnel-manager.ps1')

    $stageADir=Join-Path $script:PrivateRoot '01-stage-a'
    $stageStep=Invoke-ChildPowerShell '01-stage-a' $helperStageA @('-WorkspacePath',$workspace,'-OutputDirectory',$stageADir,'-Mode','Live','-V631Path',$v631) 240
    Assert-ChildPass $stageStep
    $stageA=Read-Json (Join-Path $stageADir 'runtime-qualification-stage-a-result.json')
    Assert-Equal ([string]$stageA.contract_id) 'PNCC_RUNTIME_QUALIFICATION_RESULT_V1' 'Stage-A result contract'
    Assert-Equal ([string]$stageA.request_id) $ExpectedRequestId 'Stage-A request id'
    Assert-True (-not[bool]$stageA.runtime_authority) 'Stage-A cannot grant runtime authority'
    Assert-True (-not[bool]$stageA.promotion_eligible) 'Stage-A cannot grant promotion eligibility'
    foreach($s in @('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')){Require-StagePass $stageA $s}
    foreach($s in @('WATCHDOG_LIFECYCLE','PROXIFIER_DESCENDANT_CLEANUP','CREDENTIAL_HOSTKEY')){
        $c=@(Get-Check $stageA $s)
        if($c.Count-ne1-or[string]$c[0].result-cne'NOT_EXECUTED'){throw ('Stage-A unexpected execution state: '+$s)}
    }

    $ownershipDir=Join-Path $script:PrivateRoot '02-primary-ownership'
    New-Item -ItemType Directory -Force -Path $ownershipDir|Out-Null
    $ownershipPath=Join-Path $ownershipDir 'stable-primary-1081-ownership.json'
    $ownershipStep=Invoke-ChildPowerShell '02-primary-ownership' $helperOwnership @('-Mode','Live','-OutputPath',$ownershipPath) 120
    Assert-ChildPass $ownershipStep
    $ownership=Read-Json $ownershipPath
    Assert-Equal ([string]$ownership.contract_id) 'PNCC_STABLE_PRIMARY_1081_OWNERSHIP_V1' 'primary ownership contract'
    Assert-Equal ([string]$ownership.state) 'OWNERSHIP_ADMITTED' 'primary ownership state'
    foreach($name in @('primary_single','primary_putty','primary_binding','primary_pwfile','primary_no_plain_pw','watchdog_registered','watchdog_action','watchdog_fresh','watchdog_exact_engine','reserve_unchanged')){Assert-True ([bool]$ownership.checks.$name) ('primary ownership check failed: '+$name)}
    Assert-True (-not[bool]$ownership.runtime_mutation) 'primary ownership validator mutated runtime'

    $watchdogDir=Join-Path $script:PrivateRoot '03-watchdog'
    $watchdogStep=Invoke-ChildPowerShell '03-watchdog' $helperWatchdog @('-Mode','LiveObservation','-OutputDirectory',$watchdogDir) 120
    Assert-ChildPass $watchdogStep
    $watchdog=Read-Json (Join-Path $watchdogDir 'stable-watchdog-lifecycle-v2-result.json')
    Assert-Equal ([string]$watchdog.contract_id) 'PNCC_STABLE_WATCHDOG_LIFECYCLE_V2' 'watchdog contract'
    Assert-Equal ([string]$watchdog.state) 'WATCHDOG_OBSERVATION_V2_ADMITTED' 'watchdog state'
    Assert-Equal ([string]$watchdog.exact_engine_sha256) $ExpectedEngineSha 'watchdog engine SHA'
    Assert-True ([bool]$watchdog.reserve_1080_unchanged) 'watchdog observation changed 1080'
    Assert-True ([bool]$watchdog.primary_1081_unchanged) 'watchdog observation changed 1081'
    Assert-True (-not[bool]$watchdog.runtime_mutation) 'watchdog validator mutated runtime'

    $credentialDir=Join-Path $script:PrivateRoot '04-credential-hostkey'
    $credentialStep=Invoke-ChildPowerShell '04-credential-hostkey' $helperCredential @('-Mode','LiveObservation','-OutputDirectory',$credentialDir) 120
    Assert-ChildPass $credentialStep
    $credential=Read-Json (Join-Path $credentialDir 'stable-credential-hostkey-v4-result.json')
    Assert-Equal ([string]$credential.contract_id) 'PNCC_STABLE_CREDENTIAL_HOSTKEY_V4' 'credential contract'
    Assert-Equal ([string]$credential.state) 'CREDENTIAL_HOSTKEY_V4_PASS' 'credential state'
    Assert-True ([bool]$credential.live_exact_engine_identity) 'credential exact engine identity not proven'
    Assert-True ([bool]$credential.pwfile_only) 'pwfile-only transport not proven'
    Assert-True (-not[bool]$credential.plaintext_pw) 'plaintext password transport observed'
    Assert-True ([bool]$credential.hostkey_fail_closed_source_contract) 'host-key fail-closed contract not proven'
    Assert-True ([bool]$credential.reserve_1080_unchanged) 'credential observation changed 1080'
    Assert-True ([bool]$credential.primary_1081_unchanged) 'credential observation changed 1081'
    Assert-True (-not[bool]$credential.runtime_mutation) 'credential validator mutated runtime'

    $proxifierDir=Join-Path $script:PrivateRoot '05-proxifier-descendants'
    $proxifierStep=Invoke-ChildPowerShell '05-proxifier-descendants' $helperProxifier @('-Mode','LiveObservation','-OutputDirectory',$proxifierDir,'-SampleCount','2','-SampleIntervalSeconds','45') 180
    Assert-ChildPass $proxifierStep
    $proxifier=Read-Json (Join-Path $proxifierDir 'stable-proxifier-descendant-cleanup-result.json')
    Assert-Equal ([string]$proxifier.contract_id) 'PNCC_STABLE_PROXIFIER_DESCENDANT_CLEANUP_V1' 'Proxifier contract'
    Assert-Equal ([string]$proxifier.state) 'PROXIFIER_DESCENDANT_CLEAN_PASS' 'Proxifier descendant state'
    Assert-True ([int]$proxifier.max_proxifier_descendants -eq 0) 'Proxifier descendants observed'
    Assert-True ([bool]$proxifier.reserve_1080_unchanged) 'Proxifier observation changed 1080'
    Assert-True ([bool]$proxifier.primary_1081_unchanged) 'Proxifier observation changed 1081'
    Assert-True (-not[bool]$proxifier.runtime_mutation) 'Proxifier validator mutated runtime'

    $portsAfter=[ordered]@{reserve_1080=Get-PortSnapshot $ReservePort;primary_1081=Get-PortSnapshot $PrimaryPort}
    Write-JsonUtf8Bom $portsAfter (Join-Path $script:PrivateRoot 'ports-after.json')
    Assert-Equal (Get-SnapshotKey $portsAfter.reserve_1080) (Get-SnapshotKey $portsBefore.reserve_1080) 'run-level 1080 listener snapshot'
    Assert-Equal (Get-SnapshotKey $portsAfter.primary_1081) (Get-SnapshotKey $portsBefore.primary_1081) 'run-level 1081 listener snapshot'

    $checks=@(
        (New-CanonicalCheck 'WINDOWS_BASELINE' @('private-evidence/01-stage-a/runtime-qualification-stage-a-result.json')),
        (New-CanonicalCheck 'PROCESS_OWNERSHIP_BASELINE' @('private-evidence/01-stage-a/runtime-qualification-stage-a-result.json','private-evidence/02-primary-ownership/stable-primary-1081-ownership.json')),
        (New-CanonicalCheck 'WATCHDOG_LIFECYCLE' @('private-evidence/03-watchdog/stable-watchdog-lifecycle-v2-result.json')),
        (New-CanonicalCheck 'PROXIFIER_DESCENDANT_CLEANUP' @('private-evidence/05-proxifier-descendants/stable-proxifier-descendant-cleanup-result.json')),
        (New-CanonicalCheck 'PRIMARY_AUTO_1081' @('private-evidence/01-stage-a/runtime-qualification-stage-a-result.json','private-evidence/02-primary-ownership/stable-primary-1081-ownership.json')),
        (New-CanonicalCheck 'RESERVE_MANUAL_1080' @('private-evidence/01-stage-a/runtime-qualification-stage-a-result.json','private-evidence/ports-before.json','private-evidence/ports-after.json')),
        (New-CanonicalCheck 'CREDENTIAL_HOSTKEY' @('private-evidence/04-credential-hostkey/stable-credential-hostkey-v4-result.json')),
        (New-CanonicalCheck 'NETWORK_QUALIFICATION' @('private-evidence/01-stage-a/runtime-qualification-stage-a-result.json')),
        (New-CanonicalCheck 'ROLLBACK_IDENTITY' @('private-evidence/01-stage-a/runtime-qualification-stage-a-result.json'))
    )
    Assert-True ($checks.Count -eq 9) 'canonical result must contain nine checks'
    for($i=0;$i-lt$ExpectedScopes.Count;$i++){Assert-Equal ([string]$checks[$i].scope) $ExpectedScopes[$i] ('canonical scope index '+$i)}

    $privateBundle=Join-Path $script:RunDirectory 'private-evidence.zip'
    if(Test-Path -LiteralPath $privateBundle){Remove-Item -LiteralPath $privateBundle -Force}
    Compress-Archive -Path (Join-Path $script:PrivateRoot '*') -DestinationPath $privateBundle -Force
    $privateBundleSha=Get-Sha256 $privateBundle

    $canonical=[ordered]@{
        schema_version=1
        contract_id='PNCC_RUNTIME_QUALIFICATION_RESULT_V1'
        request_id=$ExpectedRequestId
        candidate=[ordered]@{
            candidate_id=$ExpectedCandidateId
            source_sha=$ExpectedSourceSha
            artifact_filename=$ExpectedCandidateFilename
            artifact_sha256=$ExpectedCandidateSha
            artifact_size_bytes=$ExpectedCandidateSize
            provider_artifact_id=$ExpectedCandidateProviderArtifactId
            provider_artifact_digest=$ExpectedCandidateProviderDigest.Substring(7)
            provider_build_run_id=$ExpectedProviderBuildRunId
        }
        producer=[ordered]@{source_plane='PRIVATE_RUNTIME';agent_id='PNCC_V701_NINE_SCOPE_OWNER_QUALIFIER';runtime_agent_version=$RunnerVersion;validation_lab_version='PIPE-WU-087'}
        environment=[ordered]@{windows_version=[Environment]::OSVersion.VersionString;powershell_version=$PSVersionTable.PSVersion.ToString()}
        checks=$checks
        evidence_bundle=[ordered]@{sha256=$privateBundleSha;private_location_ref='private-evidence.zip';sanitation_state='PRIVATE'}
        qualification_state='RUNTIME_VERIFIED'
        failure_classification=$null
        runtime_authority=$true
        promotion_eligible=$false
    }
    Write-JsonUtf8Bom $canonical $canonicalResultPath

    $wrapper=[ordered]@{
        schema_version=1
        contract_id='PNCC_V701_NINE_SCOPE_OWNER_QUALIFICATION_V1'
        runner_version=$RunnerVersion
        state='PASS'
        request_id=$ExpectedRequestId
        candidate_id=$ExpectedCandidateId
        source_sha=$ExpectedSourceSha
        candidate_sha256=$ExpectedCandidateSha
        all_nine_scopes_pass=$true
        reserve_1080_unchanged=$true
        primary_1081_unchanged=$true
        runtime_mutation=$false
        reserve_1080_mutation=$false
        primary_1081_tunnel_mutation=$false
        repository_authority_mutation=$false
        private_runtime_result_authority=$true
        promotion_eligible=$false
        release_or_tag_authorized=$false
        canonical_result='runtime-qualification-result.json'
        private_evidence_bundle='private-evidence.zip'
        private_evidence_bundle_sha256=$privateBundleSha
    }
    Write-JsonUtf8Bom $wrapper $wrapperResultPath
    $finalState='PASS'
    $exitCode=0
}catch{
    $failureMessage=$_.Exception.Message
    $wrapper=[ordered]@{
        schema_version=1
        contract_id='PNCC_V701_NINE_SCOPE_OWNER_QUALIFICATION_V1'
        runner_version=$RunnerVersion
        state='BLOCKED'
        request_id=$ExpectedRequestId
        candidate_id=$ExpectedCandidateId
        failure_classification='ENVIRONMENT_OR_BASELINE_BLOCKER'
        error=$failureMessage
        all_nine_scopes_pass=$false
        runtime_mutation=$false
        reserve_1080_mutation=$false
        primary_1081_tunnel_mutation=$false
        repository_authority_mutation=$false
        private_runtime_result_authority=$false
        promotion_eligible=$false
        release_or_tag_authorized=$false
    }
    try{Write-JsonUtf8Bom $wrapper $wrapperResultPath}catch{}
    $finalState='BLOCKED'
    $exitCode=50
}finally{
    if($transcriptStarted){try{Stop-Transcript|Out-Null}catch{}}
}

try{
    if(Test-Path -LiteralPath $returnZip){Remove-Item -LiteralPath $returnZip -Force}
    Compress-Archive -Path (Join-Path $script:RunDirectory '*') -DestinationPath $returnZip -Force
    $returnSha=Get-Sha256 $returnZip
    Write-Output ('PNCC_WU087='+$finalState+' RUNTIME_MUTATION=false REPOSITORY_AUTHORITY_MUTATION=false PROMOTION_ELIGIBLE=false')
    if($failureMessage){Write-Output ('FAILURE='+$failureMessage)}
    Write-Output ('RESULT='+$wrapperResultPath)
    if(Test-Path -LiteralPath $canonicalResultPath){Write-Output ('CANONICAL_RUNTIME_RESULT='+$canonicalResultPath)}
    Write-Output ('RETURN_ZIP='+$returnZip)
    Write-Output ('RETURN_ZIP_SHA256='+$returnSha)
    Write-Output ('LOG_PATH='+$logPath)
}catch{
    Write-Output ('PNCC_WU087='+$finalState+' RETURN_BUNDLE_ERROR='+$_.Exception.Message)
    Write-Output ('LOG_PATH='+$logPath)
    if($exitCode-eq0){$exitCode=51}
}
exit $exitCode
