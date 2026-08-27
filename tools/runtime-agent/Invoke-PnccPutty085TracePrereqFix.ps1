#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [string]$PriorWu028TracePath,
 [string]$Wu029ExecutorPath,
 [string]$WorkspacePath,
 [string]$V631Path,
 [string]$PriorWu026Directory,
 [string]$Wu028ExecutorPath,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-PUTTY-085-TRACE-FIX-WU030',
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
function Require-Trace([string]$Trace){
 foreach($needle in @('[CREDENTIAL]  source=V7-DPAPI; decrypt=PASS','[SESSION_METADATA]','source=PORTABLE','found=true','[HOSTKEY_TRUST]  PASS','[PUTTY_START]  ABORT pwfile-unsupported')){
  if(-not $Trace.Contains($needle)){throw ('WU028 trace prerequisite missing: '+$needle)}
 }
}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-PUTTY-085-TRACE-FIX-WU030.log'
Start-Transcript $log -Force|Out-Null
try{
 if($Mode -eq 'Plan'){
  if(!$FixturePath -or !(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
  $trace=Get-Content -LiteralPath $FixturePath -Raw -ErrorAction Stop
  Require-Trace $trace
  Write-Output 'PNCC_PUTTY_085_TRACE_FIX=PLAN_PASS RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
  exit 0
 }
 foreach($p in @($PriorWu028TracePath,$Wu029ExecutorPath,$WorkspacePath,$V631Path,$PriorWu026Directory,$Wu028ExecutorPath)){if(!$p -or !(Test-Path -LiteralPath $p)){throw ('required path missing')}}
 $trace=Get-Content -LiteralPath $PriorWu028TracePath -Raw -ErrorAction Stop
 Require-Trace $trace
 $raw=Get-Content -LiteralPath $Wu029ExecutorPath -Raw -ErrorAction Stop
 $old="foreach(`$needle in @('[CREDENTIAL]  source=V7-DPAPI; decrypt=PASS','[SESSION_METADATA]','source=PORTABLE','found=true','[HOSTKEY_TRUST]  PASS','[PUTTY_START]  ABORT pwfile-unsupported')){if(`$trace -notlike ('*'+`$needle+'*')){throw ('WU028 trace prerequisite missing: '+`$needle)}}"
 $new="foreach(`$needle in @('[CREDENTIAL]  source=V7-DPAPI; decrypt=PASS','[SESSION_METADATA]','source=PORTABLE','found=true','[HOSTKEY_TRUST]  PASS','[PUTTY_START]  ABORT pwfile-unsupported')){if(-not `$trace.Contains(`$needle)){throw ('WU028 trace prerequisite missing: '+`$needle)}}"
 if(-not $raw.Contains($old)){throw 'WU029 buggy trace matcher signature not found'}
 $patched=$raw.Replace($old,$new)
 $patchedPath=Join-Path $OutputDirectory 'Invoke-PnccPutty085AdmissionAndRecovery.PATCHED.ps1'
 [IO.File]::WriteAllText($patchedPath,$patched,(New-Object Text.UTF8Encoding($true)))
 $tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseFile($patchedPath,[ref]$tokens,[ref]$errors);if($errors.Count){throw 'patched WU029 parse failed'}
 $child=& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $patchedPath -Mode Live -WorkspacePath $WorkspacePath -V631Path $V631Path -PriorWu026Directory $PriorWu026Directory -PriorWu028TracePath $PriorWu028TracePath -Wu028ExecutorPath $Wu028ExecutorPath -OutputDirectory (Join-Path $OutputDirectory 'wu029') 2>&1
 $rc=$LASTEXITCODE;$child|ForEach-Object{Write-Output $_}
 if($rc -ne 0){throw ('patched WU029 blocked rc='+$rc)}
 if(($child -join "`n") -notmatch 'PNCC_PUTTY_085_ADMISSION=PASS'){throw 'patched WU029 PASS marker missing'}
 Write-Output 'PNCC_PUTTY_085_TRACE_FIX=PASS RUNTIME_MUTATION=true RESERVE_1080_MUTATION=false RECOVERY_1081=PASS RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false'
 Write-Output "LOG_PATH=$log"
 exit 0
}catch{
 Write-Output ('PNCC_PUTTY_085_TRACE_FIX=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
 Write-Output "LOG_PATH=$log"
 exit 50
}finally{try{Stop-Transcript|Out-Null}catch{}}
