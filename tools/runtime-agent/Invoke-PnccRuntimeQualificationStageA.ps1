[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$WorkspacePath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('Live','Fixture')][string]$Mode='Live',
    [string]$FixturePath,
    [string]$V631Path
)

Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'

$PolicyV631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$PolicyReservePort=1080
$PolicyPrimaryPort=1081
$Scopes=@('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','WATCHDOG_LIFECYCLE','PROXIFIER_DESCENDANT_CLEANUP','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','CREDENTIAL_HOSTKEY','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')

function Get-Sha256([string]$Path){ return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function New-Check([string]$Scope,[string]$Result,[int]$ExitCode,[string]$FailureClass,[string[]]$EvidenceRefs){
    return [ordered]@{scope=$Scope;result=$Result;exit_code=$ExitCode;failure_class=$FailureClass;evidence_refs=@($EvidenceRefs)}
}
function Get-ListenerSnapshot([int]$Port){
    $rows=@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    $owners=@()
    foreach($row in $rows){
        $name='UNKNOWN';$path=''
        try{$p=Get-Process -Id ([int]$row.OwningProcess) -ErrorAction Stop;$name=[string]$p.ProcessName;$path=[string]$p.Path}catch{}
        $owners += [ordered]@{pid=[int]$row.OwningProcess;process=$name;path=$path}
    }
    return [ordered]@{port=$Port;listening=($rows.Count -gt 0);owners=@($owners|Sort-Object pid)}
}
function Snapshot-Key($Snapshot){ return (($Snapshot|ConvertTo-Json -Depth 6 -Compress)) }
function Get-Ip([Nullable[int]]$SocksPort){
    $curl=Join-Path $env:SystemRoot 'System32\curl.exe'
    if(-not(Test-Path -LiteralPath $curl -PathType Leaf)){ return '' }
    $args=@('--silent','--show-error','--max-time','12')
    if($null -ne $SocksPort){$args += @('--socks5-hostname',('127.0.0.1:{0}' -f [int]$SocksPort))}
    $args += 'https://ifconfig.me/ip'
    $old=$ErrorActionPreference
    try{$ErrorActionPreference='Continue';$o=& $curl @args 2>$null;$rc=$LASTEXITCODE}finally{$ErrorActionPreference=$old}
    if($rc -ne 0){return ''}
    $value=(($o|Out-String)-replace '\s','').Trim();$parsed=$null
    if([Net.IPAddress]::TryParse($value,[ref]$parsed)){return $value}
    return ''
}
function Write-JsonUtf8Bom($Value,[string]$Path){
    $parent=Split-Path -Parent $Path;if($parent){New-Item -ItemType Directory -Force -Path $parent|Out-Null}
    $json=$Value|ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($Path,$json,(New-Object Text.UTF8Encoding($true)))
}
function Assert-Equal([string]$Actual,[string]$Expected,[string]$Name){
    if($Actual -cne $Expected){throw "$Name mismatch"}
}

if(-not(Test-Path -LiteralPath $WorkspacePath -PathType Container)){throw "workspace not found: $WorkspacePath"}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$evidencePath=Join-Path $OutputDirectory 'stage-a-evidence.json'
$resultPath=Join-Path $OutputDirectory 'runtime-qualification-stage-a-result.json'
$checks=@();$evidence=[ordered]@{schema_version=2;stage='A';mode=$Mode;runtime_mutation=$false;observations=[ordered]@{}}
$failedClass='ENVIRONMENT_OR_BASELINE_BLOCKER'
$requestId='PNCC-RQ-FIXTURE-STAGE-A'

if($Mode -eq 'Fixture'){
    if([string]::IsNullOrWhiteSpace($FixturePath)-or -not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
    $f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json
    $checks += New-Check 'WINDOWS_BASELINE' $(if([bool]$f.windows){'PASS'}else{'FAIL'}) 0 $(if([bool]$f.windows){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'PROCESS_OWNERSHIP_BASELINE' $(if([bool]$f.ownership){'PASS'}else{'FAIL'}) 0 $(if([bool]$f.ownership){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'WATCHDOG_LIFECYCLE' 'NOT_EXECUTED' 0 $null @()
    $checks += New-Check 'PROXIFIER_DESCENDANT_CLEANUP' 'NOT_EXECUTED' 0 $null @()
    $checks += New-Check 'PRIMARY_AUTO_1081' $(if([bool]$f.primary1081){'PASS'}else{'FAIL'}) 0 $(if([bool]$f.primary1081){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'RESERVE_MANUAL_1080' $(if([bool]$f.reserve1080_unchanged){'PASS'}else{'FAIL'}) 0 $(if([bool]$f.reserve1080_unchanged){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'CREDENTIAL_HOSTKEY' 'NOT_EXECUTED' 0 $null @()
    $checks += New-Check 'NETWORK_QUALIFICATION' $(if([bool]$f.network){'PASS'}else{'FAIL'}) 0 $(if([bool]$f.network){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'ROLLBACK_IDENTITY' $(if([bool]$f.rollback){'PASS'}else{'FAIL'}) 0 $(if([bool]$f.rollback){$null}else{$failedClass}) @('stage-a-evidence.json')
    $evidence.observations.fixture='synthetic'
}else{
    $manifestPath=Join-Path $WorkspacePath 'workspace-manifest.json'
    $requestPath=Join-Path $WorkspacePath 'request\runtime-qualification-request.json'
    if(-not(Test-Path -LiteralPath $manifestPath -PathType Leaf)){throw 'workspace manifest missing'}
    if(-not(Test-Path -LiteralPath $requestPath -PathType Leaf)){throw 'qualification request missing'}
    $manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8|ConvertFrom-Json
    $request=Get-Content -LiteralPath $requestPath -Raw -Encoding UTF8|ConvertFrom-Json
    if([int]$manifest.schema_version -ne 2 -or [string]$manifest.bootstrap_id -cne 'PNCC_RUNTIME_WORKSPACE_BOOTSTRAP_V2'){throw 'Stage A requires PNCC_RUNTIME_WORKSPACE_BOOTSTRAP_V2'}
    if([string]$request.contract_id -cne 'PNCC_RUNTIME_QUALIFICATION_REQUEST_V1'){throw 'runtime request contract mismatch'}
    $requestId=[string]$request.request_id
    if([string]::IsNullOrWhiteSpace($requestId)){throw 'request id missing'}

    $expectedCandidateId=[string]$request.candidate.candidate_id
    $expectedSourceSha=[string]$request.candidate.source_sha
    $expectedArtifactName=[string]$request.candidate.artifact_filename
    $expectedArtifactSha=[string]$request.candidate.artifact_sha256
    $expectedArtifactSize=[long]$request.candidate.artifact_size_bytes
    $expectedV631Sha=[string]$request.expected_invariants.v6_3_1_sha256
    $reservePort=[int]$request.expected_invariants.reserve_manual_port
    $primaryPort=[int]$request.expected_invariants.primary_auto_port

    Assert-Equal ([string]$manifest.request_provider.request_id) $requestId 'workspace/request request_id'
    Assert-Equal ([string]$manifest.candidate.candidate_id) $expectedCandidateId 'workspace/request candidate_id'
    Assert-Equal ([string]$manifest.candidate.source_sha) $expectedSourceSha 'workspace/request source_sha'
    Assert-Equal ([string]$manifest.candidate.artifact_filename) $expectedArtifactName 'workspace/request artifact filename'
    Assert-Equal ([string]$manifest.candidate.artifact_sha256) $expectedArtifactSha 'workspace/request artifact sha256'
    if([long]$manifest.candidate.artifact_size_bytes -ne $expectedArtifactSize){throw 'workspace/request artifact size mismatch'}
    if($reservePort -ne $PolicyReservePort){throw 'reserve port policy mismatch'}
    if($primaryPort -ne $PolicyPrimaryPort){throw 'primary port policy mismatch'}
    Assert-Equal $expectedV631Sha $PolicyV631Sha 'V6.3.1 policy SHA'
    if([string]$request.expected_invariants.reserve_manual_lifecycle -cne 'MANUAL_ONLY'){throw 'reserve lifecycle policy mismatch'}
    if([string]$request.expected_invariants.putty_password_argument -cne '-pwfile'){throw 'PuTTY password argument policy mismatch'}
    if([bool]$request.expected_invariants.plaintext_pw_allowed){throw 'plaintext password transport cannot be allowed'}
    if([bool]$request.expected_invariants.hostkey_verification_disable_allowed){throw 'host-key verification cannot be disabled'}

    $candidatePath=Join-Path (Join-Path $WorkspacePath 'candidate-provider-artifact') $expectedArtifactName
    $candidateOk=$false
    if(Test-Path -LiteralPath $candidatePath -PathType Leaf){
        $ci=Get-Item -LiteralPath $candidatePath
        $candidateOk=([long]$ci.Length -eq $expectedArtifactSize -and (Get-Sha256 $candidatePath)-ceq $expectedArtifactSha)
    }

    $rollbackOk=$false
    if(-not[string]::IsNullOrWhiteSpace($V631Path)-and(Test-Path -LiteralPath $V631Path -PathType Leaf)){$rollbackOk=((Get-Sha256 $V631Path)-ceq $expectedV631Sha)}
    $beforeReserve=Get-ListenerSnapshot $reservePort
    $beforePrimary=Get-ListenerSnapshot $primaryPort
    $directIp=Get-Ip $null
    $routedIp=Get-Ip $primaryPort
    $afterReserve=Get-ListenerSnapshot $reservePort
    $afterPrimary=Get-ListenerSnapshot $primaryPort
    $reserveUnchanged=((Snapshot-Key $beforeReserve)-ceq(Snapshot-Key $afterReserve))
    $ownershipOk=([bool]$beforeReserve.listening -and [bool]$beforePrimary.listening)
    $primaryOk=([bool]$beforePrimary.listening -and [bool]$afterPrimary.listening -and -not[string]::IsNullOrWhiteSpace($routedIp))
    $networkOk=(-not[string]::IsNullOrWhiteSpace($directIp)-and -not[string]::IsNullOrWhiteSpace($routedIp)-and $directIp-cne$routedIp)
    $windowsOk=($env:OS -eq 'Windows_NT')

    $checks += New-Check 'WINDOWS_BASELINE' $(if($windowsOk){'PASS'}else{'FAIL'}) 0 $(if($windowsOk){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'PROCESS_OWNERSHIP_BASELINE' $(if($ownershipOk){'PASS'}else{'FAIL'}) 0 $(if($ownershipOk){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'WATCHDOG_LIFECYCLE' 'NOT_EXECUTED' 0 $null @()
    $checks += New-Check 'PROXIFIER_DESCENDANT_CLEANUP' 'NOT_EXECUTED' 0 $null @()
    $checks += New-Check 'PRIMARY_AUTO_1081' $(if($primaryOk){'PASS'}else{'FAIL'}) 0 $(if($primaryOk){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'RESERVE_MANUAL_1080' $(if($reserveUnchanged){'PASS'}else{'FAIL'}) 0 $(if($reserveUnchanged){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'CREDENTIAL_HOSTKEY' 'NOT_EXECUTED' 0 $null @()
    $checks += New-Check 'NETWORK_QUALIFICATION' $(if($networkOk){'PASS'}else{'FAIL'}) 0 $(if($networkOk){$null}else{$failedClass}) @('stage-a-evidence.json')
    $checks += New-Check 'ROLLBACK_IDENTITY' $(if($rollbackOk -and $candidateOk){'PASS'}else{'FAIL'}) 0 $(if($rollbackOk -and $candidateOk){$null}else{$failedClass}) @('stage-a-evidence.json')

    $evidence.observations.request_id=$requestId
    $evidence.observations.candidate_id=$expectedCandidateId
    $evidence.observations.source_sha=$expectedSourceSha
    $evidence.observations.candidate_identity=$candidateOk
    $evidence.observations.rollback_identity=$rollbackOk
    $evidence.observations.reserve_before=$beforeReserve
    $evidence.observations.reserve_after=$afterReserve
    $evidence.observations.primary_before=$beforePrimary
    $evidence.observations.primary_after=$afterPrimary
    $evidence.observations.reserve_unchanged=$reserveUnchanged
    $evidence.observations.direct_exit_ip=$directIp
    $evidence.observations.primary_1081_exit_ip=$routedIp
    $evidence.observations.direct_vs_primary_different=$networkOk
}

Write-JsonUtf8Bom $evidence $evidencePath
$evidenceSha=Get-Sha256 $evidencePath
$failed=@($checks|Where-Object{$_.result -eq 'FAIL'})
$state='BLOCKED';$failure=$null
if($failed.Count -gt 0){$state='FAILED';$failure=$failedClass}
$result=[ordered]@{
    schema_version=1
    contract_id='PNCC_RUNTIME_QUALIFICATION_RESULT_V1'
    request_id=$requestId
    candidate=[ordered]@{}
    producer=[ordered]@{source_plane='PRIVATE_RUNTIME';agent_id='PNCC_WINDOWS_RUNTIME_AGENT_STAGE_A';runtime_agent_version='0.3.0-stage-a-v2';validation_lab_version='WU-050'}
    environment=[ordered]@{windows_version=$(if($Mode-eq'Fixture'){'FIXTURE'}else{[Environment]::OSVersion.VersionString});powershell_version=$PSVersionTable.PSVersion.ToString()}
    checks=$checks
    evidence_bundle=[ordered]@{sha256=$evidenceSha;private_location_ref='stage-a-evidence.json';sanitation_state='PRIVATE_ONLY_NOT_SANITIZED'}
    qualification_state=$state
    failure_classification=$failure
    runtime_authority=$false
    promotion_eligible=$false
}
Write-JsonUtf8Bom $result $resultPath
Write-Output "PNCC_RUNTIME_STAGE_A=$state MODE=$Mode REQUEST_ID=$requestId FAILED_CHECKS=$($failed.Count) RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
Write-Output "STAGE_A_RESULT=$resultPath"
Write-Output "STAGE_A_EVIDENCE=$evidencePath"
exit 0
