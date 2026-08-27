#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [string]$WorkspacePath,
 [string]$V631Path,
 [string]$PriorWu026Directory,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-PRIMARY-1081-DPAPI-RECOVERY-WU028',
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$Artifact='VPS-Control-v7.0.0-rc14.39.zip'
$ArtifactSha='8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3'
$ArtifactSize=700961L
$V631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$PrimaryPort=1081
$ReservePort=1080
$PsExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$StateDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$Heartbeat=Join-Path $StateDir 'watchdog-heartbeat.json'
$PidFile=Join-Path $StateDir 'watchdog.pid'

function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Proc([int]$ProcessId){if($ProcessId -le 0){return $null};try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{return $null}}
function FileArg([string]$CommandLine){if(-not $CommandLine){return ''};$m=[regex]::Match($CommandLine,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))');if(!$m.Success){return ''};foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}};return ''}
function Snap([int]$Port){$r=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue);$o=@();foreach($x in $r){$p=Proc ([int]$x.OwningProcess);$o+=[ordered]@{pid=[int]$x.OwningProcess;name=$(if($p){[string]$p.Name}else{''});exe=$(if($p){[string]$p.ExecutablePath}else{''})}};return [ordered]@{port=$Port;listening=($r.Count -gt 0);owners=@($o|Sort-Object pid)}}
function Key($Value){$Value|ConvertTo-Json -Depth 8 -Compress}
function WriteJson($Value,[string]$Path){$d=Split-Path -Parent $Path;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 16),(New-Object Text.UTF8Encoding($true)))}
function Run([string]$File,[string]$Arguments,[int]$Seconds=120){$o=Join-Path $OutputDirectory ('n-'+[guid]::NewGuid().ToString('N')+'.out');$e=Join-Path $OutputDirectory ('n-'+[guid]::NewGuid().ToString('N')+'.err');$p=Start-Process $File -ArgumentList $Arguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $o -RedirectStandardError $e;if(!$p.WaitForExit($Seconds*1000)){try{$p.Kill()}catch{};throw 'native timeout'};$p.Refresh();$so=$(if(Test-Path $o){Get-Content $o -Raw}else{''});$se=$(if(Test-Path $e){Get-Content $e -Raw}else{''});Remove-Item $o,$e -Force -ErrorAction SilentlyContinue;return [pscustomobject]@{ExitCode=[int]$p.ExitCode;Stdout=[string]$so;Stderr=[string]$se}}
function ExpectedIp([string]$Path){$r=Get-Content $Path -Raw;$m=[regex]::Match($r,"(?m)^\s*\`$ExpectedVpsIp\s*=\s*'([^']+)'\s*$");if($m.Success){return [string]$m.Groups[1].Value};return ''}
function SocksIp(){ $c=(Get-Command curl.exe -ErrorAction Stop).Source;$r=Run $c '--silent --show-error --max-time 20 --socks5-hostname 127.0.0.1:1081 https://api.ipify.org' 30;if($r.ExitCode -ne 0){return ''};return $r.Stdout.Trim() }
function Resolve-ProfileRoot([string]$RuntimeDirectory){$pointer=Join-Path $RuntimeDirectory 'VPS-Control-Data.location';$profile=Join-Path $RuntimeDirectory 'VPS-Control-Data';if(Test-Path -LiteralPath $pointer -PathType Leaf){$candidate=[Environment]::ExpandEnvironmentVariables(([IO.File]::ReadAllText($pointer,[Text.Encoding]::UTF8)).Trim());if($candidate){if(-not [IO.Path]::IsPathRooted($candidate)){$candidate=Join-Path $RuntimeDirectory $candidate};$profile=[IO.Path]::GetFullPath($candidate)}};return $profile}
function Test-DpapiProfile([string]$RuntimeDirectory){$profile=Resolve-ProfileRoot $RuntimeDirectory;$active=Join-Path $profile 'nodes\vps\active-vps.json';if(!(Test-Path -LiteralPath $active -PathType Leaf)){throw 'active VPS profile missing'};$j=Get-Content -LiteralPath $active -Raw -ErrorAction Stop|ConvertFrom-Json;if(-not $j.SecretId){throw 'active VPS profile SecretId missing'};$secret=Join-Path (Join-Path $profile 'secrets\vps') (([string]$j.SecretId)+'.dpapi');if(!(Test-Path -LiteralPath $secret -PathType Leaf)){throw 'active VPS DPAPI secret missing'};$cipher=(Get-Content -LiteralPath $secret -Raw -ErrorAction Stop).Trim();if(-not $cipher){throw 'active VPS DPAPI secret empty'};$secure=ConvertTo-SecureString -String $cipher -ErrorAction Stop;$bstr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);try{$value=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr);if([string]::IsNullOrEmpty($value)){throw 'active VPS DPAPI secret decrypts empty'}}finally{if($bstr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)};$value=$null};return [pscustomobject]@{ProfileRoot=$profile;ActiveProfile=$active;SecretFile=$secret;AuthMode=[string]$j.AuthMode;SavedSessionPresent=[bool]$j.SavedSession}}

New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-PRIMARY-1081-DPAPI-RECOVERY-WU028.log'
Start-Transcript $log -Force|Out-Null
try{
 if($Mode -eq 'Plan'){
  if(!$FixturePath -or !(Test-Path $FixturePath)){throw 'FixturePath required'}
  $f=Get-Content $FixturePath -Raw|ConvertFrom-Json
  foreach($n in @('wu026_blocked','primary_absent','candidate_identity','rollback_identity','active_profile','secret_id','dpapi_present','dpapi_decryptable','pwfile_only','hostkey_fail_closed','reserve_observation_only')){if(-not [bool]$f.$n){throw "plan fixture failed: $n"}}
  Write-Output 'PNCC_PRIMARY_1081_DPAPI_RECOVERY=PLAN_PASS RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
  exit 0
 }
 if($env:OS -ne 'Windows_NT'){throw 'Windows required'}
 if(!$WorkspacePath -or !(Test-Path $WorkspacePath)){throw 'WorkspacePath missing'}
 if(!$V631Path -or !(Test-Path $V631Path)){throw 'V631Path missing'}
 if((Sha $V631Path) -ne $V631Sha){throw 'V6.3.1 SHA mismatch'}
 if(!$PriorWu026Directory -or !(Test-Path $PriorWu026Directory)){throw 'Prior WU026 evidence directory missing'}
 $priorLog=Join-Path $PriorWu026Directory 'PNCC-PRIMARY-1081-RECONCILE.log'
 if(!(Test-Path $priorLog)){throw 'prior WU026 log missing'}
 $prior=Get-Content $priorLog -Raw
 if($prior -notmatch 'PNCC_PRIMARY_1081_RECONCILE=BLOCKED ERROR=new 1081 listener did not appear'){throw 'prior WU026 blocked state not proven'}
 if(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue){throw '1081 unexpectedly listening; recovery state changed'}
 $reserveBefore=Snap $ReservePort
 if(-not $reserveBefore.listening){throw '1080 reserve baseline is not listening'}
 $artifact=Join-Path (Join-Path $WorkspacePath 'provider-artifact') $Artifact
 if(!(Test-Path $artifact)){throw 'candidate artifact missing'}
 $a=Get-Item $artifact
 if([long]$a.Length -ne $ArtifactSize -or (Sha $artifact) -ne $ArtifactSha){throw 'candidate identity mismatch'}
 $runtimeDir=Split-Path -Parent $V631Path
 $profileCheck=Test-DpapiProfile $runtimeDir
 if($profileCheck.AuthMode -and $profileCheck.AuthMode -ne 'SavedSession'){throw 'active VPS auth mode is not SavedSession'}
 $stage=Join-Path $OutputDirectory 'candidate-stage'
 Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
 New-Item -ItemType Directory -Force -Path $stage|Out-Null
 Expand-Archive $artifact -DestinationPath $stage -Force
 $u=@(Get-ChildItem $stage -Recurse -File -Filter 'VPS-Control-v7-engine-upgrade.ps1'|Select-Object -First 1)
 if($u.Count -ne 1){throw 'generator missing'}
 $d=Split-Path -Parent $u[0].FullName
 $sv=Join-Path $d 'VPS-Control-v6.3.1.ps1'
 Copy-Item $V631Path $sv -Force
 $g=Join-Path $d 'VPS-Control-v6.5.ps1'
 $gr=Run $PsExe ("-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$($u[0].FullName)`" -SourcePath `"$sv`" -DestinationPath `"$g`"")
 if($gr.ExitCode -ne 0 -or !(Test-Path $g)){throw 'generation failed'}
 $gsha=Sha $g
 $raw=Get-Content $g -Raw
 if($raw -notmatch "(?i)'?-pwfile'?" -or $raw -notmatch 'Ensure-V7OfficialPuttyHostKeyTrust' -or $raw -notmatch 'V7-DPAPI'){throw 'generated engine security contract failed'}
 if(($raw -match '(?i)\$arguments\s*\+=\s*@\(\s*''-pw''') -or ($raw -match '(?i)\$arguments\s*\+=\s*@\(\s*"-pw"')){throw 'generated engine still constructs plaintext -pw'}
 $installed=Join-Path $runtimeDir 'VPS-Control-v6.5.ps1'
 $oldSha=$(if(Test-Path $installed){Sha $installed}else{''})
 Copy-Item $g $installed -Force
 if((Sha $installed) -ne $gsha){throw 'installed exact engine SHA mismatch'}
 $moduleSource=Join-Path $d 'VPS-Control-v6.5-modules.json'
 $moduleInstalled=Join-Path $runtimeDir 'VPS-Control-v6.5-modules.json'
 if(Test-Path $moduleSource -PathType Leaf){Copy-Item $moduleSource $moduleInstalled -Force;if((Sha $moduleSource) -ne (Sha $moduleInstalled)){throw 'installed module catalog SHA mismatch'}}
 $ev=[ordered]@{schema_version=1;contract_id='PNCC_PRIMARY_1081_DPAPI_RECOVERY_V1';runtime_mutation=$true;reserve_1080_mutation=$false;prior_state='WU026_BLOCKED_NO_1081';old_engine_sha256=$oldSha;installed_engine_sha256=$gsha;dpapi_profile_present=$true;dpapi_decryptable=$true;reserve_before=$reserveBefore;steps=@()}
 $rr=Run $PsExe ("-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$installed`" -Action RestartTunnel -NoAppLaunch") 120
 if($rr.ExitCode -ne 0){throw ('RestartTunnel failed; see private runtime log')}
 $deadline=(Get-Date).AddSeconds(45);$np=$null
 while((Get-Date) -lt $deadline){$r=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue|Select-Object -First 1);if($r.Count){$np=Proc ([int]$r[0].OwningProcess);if($np){break}};Start-Sleep -Milliseconds 500}
 if($null -eq $np){throw 'secure 1081 listener did not appear'}
 $cmd=[string]$np.CommandLine
 if($cmd -match '(?i)(?:^|\s)-pw(?:\s|=)'){throw 'SECURITY BLOCK plaintext -pw observed'}
 if($cmd -notmatch '(?i)(?:^|\s)-pwfile(?:\s|=)'){throw 'new 1081 lacks -pwfile'}
 $ev.steps+=@([ordered]@{step='secure_1081';pid=[int]$np.ProcessId;pwfile=$true;plain_pw=$false;result='PASS'})
 Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
 $wd=Start-Process $PsExe -ArgumentList ("-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$installed`" -Action Watchdog -WatchIntervalSeconds 45 -NoAppLaunch") -WindowStyle Hidden -PassThru
 $ok=$false;$age=-1;$deadline=(Get-Date).AddSeconds(90)
 while((Get-Date) -lt $deadline){Start-Sleep 2;if($null -eq (Proc ([int]$wd.Id))){break};if(Test-Path $Heartbeat){$age=[int]((Get-Date)-(Get-Item $Heartbeat).LastWriteTime).TotalSeconds;if($age -ge 0 -and $age -le 60){$ok=$true;break}}}
 if(!$ok){throw 'watchdog heartbeat not fresh'}
 $wp=Proc ([int]$wd.Id);$wf=FileArg ([string]$wp.CommandLine)
 if(!$wf -or (Sha $wf) -ne $gsha){throw 'watchdog engine mismatch'}
 $ev.steps+=@([ordered]@{step='watchdog';pid=[int]$wd.Id;heartbeat_age_seconds=$age;result='PASS'})
 $expected=ExpectedIp $V631Path
 $actual=SocksIp
 if(!$expected -or !$actual -or $expected -ne $actual){throw '1081 routed identity mismatch'}
 $reserveAfter=Snap $ReservePort
 if((Key $reserveBefore) -ne (Key $reserveAfter)){throw 'CRITICAL 1080 snapshot changed'}
 $ev.reserve_after=$reserveAfter;$ev.routed_identity_match=$true;$ev.state='PASS';$ev.runtime_authority=$false;$ev.promotion_eligible=$false
 $rp=Join-Path $OutputDirectory 'primary-1081-dpapi-recovery-result.json'
 WriteJson $ev $rp
 Write-Output 'PNCC_PRIMARY_1081_DPAPI_RECOVERY=PASS RUNTIME_MUTATION=true RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false'
 Write-Output "RESULT=$rp"
 Write-Output "LOG_PATH=$log"
 exit 0
}catch{
 Write-Output ("PNCC_PRIMARY_1081_DPAPI_RECOVERY=BLOCKED ERROR="+$_.Exception.Message+' RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
 Write-Output "LOG_PATH=$log"
 exit 50
}finally{try{Stop-Transcript|Out-Null}catch{}}
