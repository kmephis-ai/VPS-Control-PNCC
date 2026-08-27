#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$OutputPath = "E:\!Chrome_Downloads\PNCC-RUNTIME-BASELINE-PROVENANCE.json"
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'

function Get-Proc([int]$Pid){
    if($Pid -le 0){return $null}
    try{return Get-CimInstance Win32_Process -Filter ("ProcessId="+$Pid) -ErrorAction Stop}catch{return $null}
}
function Get-FileArg([string]$Cmd){
    if([string]::IsNullOrWhiteSpace($Cmd)){return ''}
    $m=[regex]::Match($Cmd,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))')
    if(-not$m.Success){return ''}
    foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}}
    return ''
}
function Get-RedactedFingerprint([string]$Cmd){
    if([string]::IsNullOrWhiteSpace($Cmd)){return ''}
    $s=[string]$Cmd
    $s=[regex]::Replace($s,'(?i)(-pw\s+)("[^"]*"|\S+)','$1<redacted>')
    $s=[regex]::Replace($s,'(?i)(-pwfile\s+)("[^"]*"|\S+)','$1<redacted-path>')
    $s=[regex]::Replace($s,'(?i)(password\s*[=:]\s*)("[^"]*"|\S+)','$1<redacted>')
    $s=[regex]::Replace($s,'(?i)(token|secret|api[_-]?key)\s*[=:]\s*("[^"]*"|\S+)','$1=<redacted>')
    return ([Convert]::ToBase64String([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($s))))
}
function Get-Ancestry([int]$Pid,[int]$Max=8){
    $items=@();$seen=@{};$cur=$Pid
    for($i=0;$i -lt $Max -and $cur -gt 0;$i++){
        if($seen.ContainsKey($cur)){break};$seen[$cur]=$true
        $p=Get-Proc $cur;if($null-eq$p){break}
        $cmd=[string]$p.CommandLine;$fileArg=Get-FileArg $cmd
        $items += [ordered]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;name=[string]$p.Name;exe=[string]$p.ExecutablePath;file_arg=$fileArg;file_sha256=$(if($fileArg -and (Test-Path -LiteralPath $fileArg -PathType Leaf)){(Get-FileHash -LiteralPath $fileArg -Algorithm SHA256).Hash.ToLowerInvariant()}else{''});has_action_watchdog=[bool]($cmd -match '(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)');has_d1081=[bool]($cmd -match '(?i)(?:^|\s)-D\s+"?127\.0\.0\.1:1081"?(?:\s|$)');has_pw=[bool]($cmd -match '(?i)(?:^|\s)-pw(?:\s|=)');has_pwfile=[bool]($cmd -match '(?i)(?:^|\s)-pwfile(?:\s|=)');redacted_command_fingerprint=(Get-RedactedFingerprint $cmd)}
        $cur=[int]$p.ParentProcessId
    }
    return @($items)
}

$stateDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$pidFile=Join-Path $stateDir 'watchdog.pid'
$hbFile=Join-Path $stateDir 'watchdog-heartbeat.json'
$watchPid=0
if(Test-Path -LiteralPath $pidFile -PathType Leaf){try{$watchPid=[int](Get-Content -LiteralPath $pidFile -Raw).Trim()}catch{}}
$watchProc=Get-Proc $watchPid
$listener=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1081 -ErrorAction SilentlyContinue|Select-Object -First 1)
$primaryPid=$(if($listener.Count){[int]$listener[0].OwningProcess}else{0})
$hbAge=-1
if(Test-Path -LiteralPath $hbFile -PathType Leaf){$hbAge=[int]((Get-Date)-(Get-Item -LiteralPath $hbFile).LastWriteTime).TotalSeconds}

$result=[ordered]@{
    schema_version=1
    contract_id='PNCC_RUNTIME_BASELINE_PROVENANCE_V1'
    runtime_mutation=$false
    watchdog=[ordered]@{pid_file_pid=$watchPid;process_exists=($null-ne$watchProc);heartbeat_age_seconds=$hbAge;ancestry=(Get-Ancestry $watchPid)}
    primary_1081=[ordered]@{pid=$primaryPid;ancestry=(Get-Ancestry $primaryPid)}
}
$parent=Split-Path -Parent $OutputPath;if($parent){New-Item -ItemType Directory -Force -Path $parent|Out-Null}
[IO.File]::WriteAllText($OutputPath,($result|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($true)))
Write-Output "PNCC_RUNTIME_BASELINE_PROVENANCE=PASS RUNTIME_MUTATION=false"
Write-Output "OUTPUT=$OutputPath"
exit 0
