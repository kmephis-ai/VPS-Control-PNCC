#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [string]$WorkspacePath,
 [string]$V631Path,
 [string]$PriorWu026Directory,
 [string]$PriorWu028TracePath,
 [string]$Wu028ExecutorPath,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-PUTTY-085-ADMISSION-WU029',
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$PrimaryPort=1081
$ReservePort=1080
$PuttyVersion='0.85'
$OfficialUrl='https://the.earth.li/~sgtatham/putty/0.85/w64/putty.exe'
$OfficialSha='d01fdb5aae8f112526040a39b0bfb9e27d813003178645e65f8d1cfdb2a26c87'
$PsExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Proc([int]$ProcessId){if($ProcessId -le 0){return $null};try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{return $null}}
function Snap([int]$Port){$r=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue);$o=@();foreach($x in $r){$p=Proc ([int]$x.OwningProcess);$o+=[ordered]@{pid=[int]$x.OwningProcess;name=$(if($p){[string]$p.Name}else{''});exe=$(if($p){[string]$p.ExecutablePath}else{''})}};return [ordered]@{port=$Port;listening=($r.Count -gt 0);owners=@($o|Sort-Object pid)}}
function Key($Value){$Value|ConvertTo-Json -Depth 8 -Compress}
function WriteJson($Value,[string]$Path){$d=Split-Path -Parent $Path;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 16),(New-Object Text.UTF8Encoding($true)))}
function BinaryHasPwFile([string]$Path){$bytes=[IO.File]::ReadAllBytes($Path);$ascii=[Text.Encoding]::ASCII.GetString($bytes);return [bool]($ascii -match '(?i)-pwfile')}

New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-PUTTY-085-ADMISSION-WU029.log'
Start-Transcript $log -Force|Out-Null
try{
 if($Mode -eq 'Plan'){
  if(!$FixturePath -or !(Test-Path -LiteralPath $FixturePath)){throw 'FixturePath required'}
  $f=Get-Content -LiteralPath $FixturePath -Raw|ConvertFrom-Json
  foreach($n in @('wu028_pwfile_unsupported','dpapi_pass','session_metadata_pass','hostkey_trust_pass','primary_absent','reserve_listening','official_url_pinned','official_sha256_pinned','authenticode_required','pwfile_capability_required','portable_launcher_preserved','reserve_observation_only','resume_wu028')){if(-not [bool]$f.$n){throw "plan fixture failed: $n"}}
  Write-Output 'PNCC_PUTTY_085_ADMISSION=PLAN_PASS RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
  exit 0
 }
 if($env:OS -ne 'Windows_NT'){throw 'Windows required'}
 if(!$WorkspacePath -or !(Test-Path -LiteralPath $WorkspacePath)){throw 'WorkspacePath missing'}
 if(!$V631Path -or !(Test-Path -LiteralPath $V631Path)){throw 'V631Path missing'}
 if(!$PriorWu026Directory -or !(Test-Path -LiteralPath $PriorWu026Directory)){throw 'Prior WU026 evidence directory missing'}
 if(!$PriorWu028TracePath -or !(Test-Path -LiteralPath $PriorWu028TracePath -PathType Leaf)){throw 'WU028 trace missing'}
 if(!$Wu028ExecutorPath -or !(Test-Path -LiteralPath $Wu028ExecutorPath -PathType Leaf)){throw 'WU028 executor missing'}
 $trace=Get-Content -LiteralPath $PriorWu028TracePath -Raw
 foreach($needle in @('[CREDENTIAL]  source=V7-DPAPI; decrypt=PASS','[SESSION_METADATA]','source=PORTABLE','found=true','[HOSTKEY_TRUST]  PASS','[PUTTY_START]  ABORT pwfile-unsupported')){if($trace -notlike ('*'+$needle+'*')){throw ('WU028 trace prerequisite missing: '+$needle)}}
 if(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue){throw '1081 unexpectedly listening; admission state changed'}
 $reserveBefore=Snap $ReservePort
 if(-not $reserveBefore.listening){throw '1080 reserve baseline is not listening'}
 $runtimeDir=Split-Path -Parent $V631Path
 $portable=Join-Path $runtimeDir 'PuTTY PORTABLE\putty_portable.exe'
 if(!(Test-Path -LiteralPath $portable -PathType Leaf)){throw 'expected portable launcher missing'}
 $portableSha=Sha $portable
 $transportDir=Split-Path -Parent $portable
 $target=Join-Path $transportDir 'putty.exe'
 $download=Join-Path $OutputDirectory 'putty-0.85-w64.exe'
 if(!(Test-Path -LiteralPath $download -PathType Leaf) -or (Sha $download) -ne $OfficialSha){
  Remove-Item -LiteralPath $download -Force -ErrorAction SilentlyContinue
  Invoke-WebRequest -UseBasicParsing -Uri $OfficialUrl -OutFile $download -ErrorAction Stop
 }
 if((Sha $download) -ne $OfficialSha){throw 'official PuTTY SHA256 mismatch'}
 $sig=Get-AuthenticodeSignature -FilePath $download
 if([string]$sig.Status -ne 'Valid'){throw ('official PuTTY Authenticode invalid: '+[string]$sig.Status)}
 if(-not (BinaryHasPwFile $download)){throw 'official PuTTY binary does not expose -pwfile capability marker'}
 $existingSha=$(if(Test-Path -LiteralPath $target -PathType Leaf){Sha $target}else{''})
 if($existingSha -and $existingSha -ne $OfficialSha){
  $backup=Join-Path $OutputDirectory ('preexisting-putty-'+$existingSha.Substring(0,12)+'.bak')
  Copy-Item -LiteralPath $target -Destination $backup -Force
 }
 Copy-Item -LiteralPath $download -Destination $target -Force
 if((Sha $target) -ne $OfficialSha){throw 'installed managed PuTTY SHA mismatch'}
 if((Sha $portable) -ne $portableSha){throw 'portable launcher changed unexpectedly'}
 if(-not (BinaryHasPwFile $target)){throw 'installed managed PuTTY lost -pwfile capability'}
 $reserveAfterInstall=Snap $ReservePort
 if((Key $reserveBefore) -ne (Key $reserveAfterInstall)){throw 'CRITICAL 1080 snapshot changed during transport admission'}
 $ev=[ordered]@{schema_version=1;contract_id='PNCC_PUTTY_085_ADMISSION_V1';runtime_mutation=$true;reserve_1080_mutation=$false;putty_version=$PuttyVersion;official_sha256=$OfficialSha;authenticode_valid=$true;pwfile_capability=$true;portable_launcher_preserved=$true;reserve_before=$reserveBefore;reserve_after_install=$reserveAfterInstall;recovery='PENDING'}
 $resultPath=Join-Path $OutputDirectory 'putty-085-admission-result.json'
 WriteJson $ev $resultPath
 $args=@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$Wu028ExecutorPath,'-Mode','Live','-WorkspacePath',$WorkspacePath,'-V631Path',$V631Path,'-PriorWu026Directory',$PriorWu026Directory,'-OutputDirectory',(Join-Path $OutputDirectory 'wu028-resume'))
 $child=& $PsExe @args 2>&1
 $rc=$LASTEXITCODE
 $child|ForEach-Object{Write-Output $_}
 if($rc -ne 0){throw ('WU028 resume blocked rc='+$rc)}
 $joined=($child -join "`n")
 if($joined -notmatch 'PNCC_PRIMARY_1081_DPAPI_RECOVERY=PASS'){throw 'WU028 resume PASS marker missing'}
 $reserveAfter=Snap $ReservePort
 if((Key $reserveBefore) -ne (Key $reserveAfter)){throw 'CRITICAL 1080 snapshot changed after recovery'}
 if(-not (Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue)){throw '1081 not listening after recovery'}
 $ev.recovery='PASS';$ev.reserve_after=$reserveAfter;$ev.runtime_authority=$false;$ev.promotion_eligible=$false
 WriteJson $ev $resultPath
 Write-Output 'PNCC_PUTTY_085_ADMISSION=PASS RUNTIME_MUTATION=true RESERVE_1080_MUTATION=false RECOVERY_1081=PASS RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false'
 Write-Output "RESULT=$resultPath"
 Write-Output "LOG_PATH=$log"
 exit 0
}catch{
 Write-Output ('PNCC_PUTTY_085_ADMISSION=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
 Write-Output "LOG_PATH=$log"
 exit 50
}finally{try{Stop-Transcript|Out-Null}catch{}}
