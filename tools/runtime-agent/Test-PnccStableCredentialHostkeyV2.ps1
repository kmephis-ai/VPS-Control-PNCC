#requires -Version 5.1
[CmdletBinding()]
param([ValidateSet('Fixture','LiveObservation')][string]$Mode='Fixture',[string]$FixturePath,[string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-STABLE-CREDENTIAL-HOSTKEY-V2')
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$ExpectedEngineSha='843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'
$StateDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3';$PidFile=Join-Path $StateDir 'watchdog.pid';$Heartbeat=Join-Path $StateDir 'watchdog-heartbeat.json'
function WJ($v,[string]$p){$d=Split-Path -Parent $p;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 16),(New-Object Text.UTF8Encoding($true)))}
function P([int]$id){try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$id) -ErrorAction Stop}catch{$null}}
function F([string]$c){if(-not$c){return ''};$m=[regex]::Match($c,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))');if(-not$m.Success){return ''};foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}};''}
function S([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function Snap([int]$port){$r=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $port -ErrorAction SilentlyContinue);[ordered]@{port=$port;listening=($r.Count-gt0);listener_count=$r.Count;owner_pids=@($r|%{[int]$_.OwningProcess}|sort)}}
function K($v){$v|ConvertTo-Json -Depth 8 -Compress}
function Test-HostKeyBeforeDecrypt([string]$Raw){
 $lines=@($Raw -split "`r?`n")
 $call=-1;$guard=-1;$decrypt=-1
 for($i=0;$i-lt$lines.Count;$i++){
  $line=[string]$lines[$i]
  if($call-lt0-and$line-match'^\s*\$hostKeyTrustOk\s*=\s*Ensure-V7OfficialPuttyHostKeyTrust\b'){$call=$i;continue}
  if($call-ge0-and$guard-lt0-and$i-gt$call-and$i-le($call+20)-and$line-match'^\s*if\s*\(\s*-not\s+\$hostKeyTrustOk\s*\)'){$guard=$i;continue}
  if($call-ge0-and$decrypt-lt0-and$i-gt$call-and$i-le($call+30)-and$line-match'^\s*\$password\s*=\s*Get-DpapiPassword\b'){$decrypt=$i;break}
 }
 return ($call-ge0-and$guard-gt$call-and$decrypt-gt$guard)
}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null;$rp=Join-Path $OutputDirectory 'stable-credential-hostkey-v2-result.json'
if($Mode-ceq'Fixture'){$f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json;$checks=[ordered]@{dpapi_at_rest=[bool]$f.dpapi_at_rest;pwfile_only=[bool]$f.pwfile_only;plaintext_pw_forbidden=[bool]$f.plaintext_pw_forbidden;hostkey_fail_closed=[bool]$f.hostkey_fail_closed;hostkey_callsite_before_decrypt=[bool]$f.hostkey_callsite_before_decrypt;unknown_hostkey_accept_forbidden=[bool]$f.unknown_hostkey_accept_forbidden;hostkey_verification_disable_forbidden=[bool]$f.hostkey_verification_disable_forbidden;reserve_1080_untouched=[bool]$f.reserve_1080_untouched;primary_1081_observation_only=[bool]$f.primary_1081_observation_only;runtime_authority_false=[bool]$f.runtime_authority_false;promotion_eligible_false=[bool]$f.promotion_eligible_false};$bad=@($checks.GetEnumerator()|?{-not[bool]$_.Value}|%{$_.Key});$ok=($bad.Count-eq0);$r=[ordered]@{schema_version=2;contract_id='PNCC_STABLE_CREDENTIAL_HOSTKEY_V2';mode='Fixture';state=$(if($ok){'CREDENTIAL_HOSTKEY_V2_CONTRACT_ADMITTED'}else{'BLOCKED'});checks=$checks;failed_checks=$bad;runtime_mutation=$false;runtime_authority=$false;promotion_eligible=$false};WJ $r $rp;Write-Output ('PNCC_STABLE_CREDENTIAL_HOSTKEY_V2='+$r.state+' RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false');if($ok){exit 0}else{exit 50}}
if($env:OS-cne'Windows_NT'){throw 'LiveObservation requires Windows'}
$b1080=Snap 1080;$b1081=Snap 1081;if(-not$b1080.listening-or-not$b1081.listening){throw '1080/1081 listener baseline missing'}
if(-not(Test-Path -LiteralPath $PidFile)){throw 'watchdog pid missing'};$wid=[int](Get-Content -LiteralPath $PidFile -Raw).Trim();$wp=P $wid;if($null-eq$wp){throw 'watchdog missing'};$wc=[string]$wp.CommandLine;if($wc-notmatch'(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){throw 'watchdog action mismatch'};$ef=F $wc;if(-not$ef-or(S $ef)-cne$ExpectedEngineSha){throw 'watchdog engine mismatch'}
$hb=Get-Content -LiteralPath $Heartbeat -Raw|ConvertFrom-Json;$age=[int][math]::Round(((Get-Date)-([datetime]$hb.Timestamp)).TotalSeconds);if([int]$hb.Pid-ne$wid-or$age-lt0-or$age-gt240){throw 'heartbeat binding/freshness failed'}
$rows=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1081 -ErrorAction Stop);if($rows.Count-ne1){throw 'expected one 1081 listener'};$tp=P ([int]$rows[0].OwningProcess);$tc=[string]$tp.CommandLine;if([string]$tp.Name-notmatch'(?i)^(putty|putty_portable|plink)\.exe$'){throw '1081 owner not PuTTY-family'};if($tc-notmatch'(?i)(?:^|\s)-pwfile(?:\s|=)'){throw '1081 -pwfile missing'};if($tc-match'(?i)(?:^|\s)-pw(?:\s|=)'){throw 'plaintext -pw observed'}
$raw=Get-Content -LiteralPath $ef -Raw;if($raw-notmatch'Ensure-V7OfficialPuttyHostKeyTrust'){throw 'hostkey trust function missing'};if($raw-notmatch'V7-DPAPI'){throw 'DPAPI source marker missing'};if(($raw-match'(?i)-hostkey\s+\*')-or($raw-match'(?i)auto.?accept.*host.?key')-or($raw-match'(?i)HostKeyVerificationDisableAllowed\s*=\s*\$true')){throw 'hostkey bypass marker observed'}
if(-not(Test-HostKeyBeforeDecrypt $raw)){throw 'hostkey trust callsite/guard before DPAPI decrypt not proven'}
$a1080=Snap 1080;$a1081=Snap 1081;if((K $b1080)-cne(K $a1080)){throw '1080 changed'};if((K $b1081)-cne(K $a1081)){throw '1081 changed'}
$r=[ordered]@{schema_version=2;contract_id='PNCC_STABLE_CREDENTIAL_HOSTKEY_V2';mode='LiveObservation';state='CREDENTIAL_HOSTKEY_V2_PASS';exact_engine_sha256=$ExpectedEngineSha;dpapi_source_marker=$true;pwfile_only=$true;plaintext_pw=$false;hostkey_fail_closed_source_contract=$true;hostkey_callsite_guard_before_dpapi_decrypt=$true;reserve_1080_unchanged=$true;primary_1081_unchanged=$true;runtime_mutation=$false;runtime_authority=$false;promotion_eligible=$false};WJ $r $rp;Write-Output 'PNCC_STABLE_CREDENTIAL_HOSTKEY_V2=CREDENTIAL_HOSTKEY_V2_PASS RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false';Write-Output ('RESULT='+$rp);exit 0
