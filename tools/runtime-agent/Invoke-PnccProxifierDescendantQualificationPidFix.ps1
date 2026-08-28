#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [Parameter(Mandatory=$true)][string]$LegacyExecutorPath,
 [string]$ReconciledResultPath,
 [string]$Wu028ResultPath,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-PROXIFIER-DESCENDANT-QUALIFICATION-WU035',
 [int]$SampleIntervalSeconds=50,
 [int]$SampleCount=3,
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$PsExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
function Quote([string]$s){'"'+($s -replace '"','\"')+'"'}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-PROXIFIER-DESCENDANT-QUALIFICATION-WU035.log'
Start-Transcript $log -Force|Out-Null
try {
 if(!(Test-Path -LiteralPath $LegacyExecutorPath -PathType Leaf)){throw 'LegacyExecutorPath missing'}
 $raw=[IO.File]::ReadAllText($LegacyExecutorPath,[Text.Encoding]::UTF8)
 $before=[regex]::Matches($raw,'(?i)\$pid\b').Count
 if($before -lt 1){throw 'legacy executor no longer contains PID collision signature'}
 $patched=$raw.Replace('$pid','$watchdogPid')
 $after=[regex]::Matches($patched,'(?i)\$pid\b').Count
 if($after -ne 0){throw 'PID collision tokens remain after patch'}
 $tokens=$null;$errors=$null
 [void][Management.Automation.Language.Parser]::ParseInput($patched,[ref]$tokens,[ref]$errors)
 if($errors -and $errors.Count -gt 0){throw ('patched executor parse failed: '+(($errors|ForEach-Object Message)-join '; '))}
 $patchedPath=Join-Path $OutputDirectory 'Invoke-PnccProxifierDescendantQualificationFromEvidence.patched.ps1'
 [IO.File]::WriteAllText($patchedPath,$patched,(New-Object Text.UTF8Encoding($true)))
 $childOut=Join-Path $OutputDirectory 'qualified'
 $args=@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$patchedPath,'-Mode',$Mode,'-OutputDirectory',$childOut,'-SampleIntervalSeconds',[string]$SampleIntervalSeconds,'-SampleCount',[string]$SampleCount)
 if($ReconciledResultPath){$args+=@('-ReconciledResultPath',$ReconciledResultPath)}
 if($Wu028ResultPath){$args+=@('-Wu028ResultPath',$Wu028ResultPath)}
 if($FixturePath){$args+=@('-FixturePath',$FixturePath)}
 & $PsExe @args
 $rc=$LASTEXITCODE
 if($Mode -eq 'Plan'){
   if($rc -ne 0){throw ('patched Plan child failed rc='+$rc)}
   Write-Output 'PNCC_PROXIFIER_DESCENDANT_PID_FIX=PLAN_PASS PID_COLLISION_REMOVED=true RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
   exit 0
 }
 if($rc -eq 0){Write-Output 'PNCC_PROXIFIER_DESCENDANT_PID_FIX=PASS PID_COLLISION_REMOVED=true RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false';Write-Output "LOG_PATH=$log";exit 0}
 Write-Output ("PNCC_PROXIFIER_DESCENDANT_PID_FIX=BLOCKED CHILD_EXIT_CODE=$rc PID_COLLISION_REMOVED=true RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false")
 Write-Output "LOG_PATH=$log"
 exit $rc
} catch {
 Write-Output ('PNCC_PROXIFIER_DESCENDANT_PID_FIX=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false')
 Write-Output "LOG_PATH=$log"
 exit 50
} finally {try{Stop-Transcript|Out-Null}catch{}}
