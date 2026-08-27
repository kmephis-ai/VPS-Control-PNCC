#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('Test','Health','Diagnose','PlanPackages','InstallBaseline','InstallMonitoring','OpenSsh')][string]$Action,
    [Parameter(Mandatory=$true)][string]$ProfileId
)
$ErrorActionPreference='Stop'
$StorageHelper=Join-Path $PSScriptRoot 'modules\V7-Storage.ps1'
if(-not(Test-Path -LiteralPath $StorageHelper)){throw 'Не найден modules\V7-Storage.ps1'}
. $StorageHelper
$UiStateDir=Resolve-V7DataRoot -BaseDir $PSScriptRoot
$Layout=Initialize-V7StorageLayout -BaseDir $PSScriptRoot -DataRoot $UiStateDir
$ProfilesFile=Join-Path $Layout.Vps 'vps-profiles.json'
$SecretsDir=$Layout.VpsSecrets
$HealthDir=$Layout.VpsHealth
if(-not(Test-Path -LiteralPath $HealthDir)){New-Item -ItemType Directory -Path $HealthDir -Force|Out-Null}
$SourcePath=Join-Path $PSScriptRoot 'VPS-Control-v6.3.1.ps1'

function Fail([string]$m){ [Console]::Error.WriteLine($m); exit 1 }
function Read-Doc { if(-not(Test-Path -LiteralPath $ProfilesFile)){Fail 'vps-profiles.json не найден.'}; return (Get-Content -LiteralPath $ProfilesFile -Raw|ConvertFrom-Json) }
function Get-Profile { $d=Read-Doc; $p=@($d.Profiles|Where-Object{[string]$_.Id -eq $ProfileId}|Select-Object -First 1)[0]; if(-not $p){Fail 'Профиль VPS не найден.'}; return $p }
function Get-Secret([string]$id){ $path=Join-Path $SecretsDir ($id+'.dpapi'); if(-not(Test-Path -LiteralPath $path)){return ''}; try{$sec=ConvertTo-SecureString -String ((Get-Content -LiteralPath $path -Raw).Trim());$b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec);try{return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)}}catch{return ''} }
function Get-PuttyPath {
    $candidates=New-Object Collections.ArrayList
    # RC14.11: installation-local portable PuTTY is authoritative when present.
    foreach($local in @(
        (Join-Path $PSScriptRoot 'PuTTY PORTABLE\putty_portable.exe'),
        (Join-Path $PSScriptRoot 'PuTTY PORTABLE\putty.exe'),
        (Join-Path $PSScriptRoot 'putty_portable.exe'),
        (Join-Path $PSScriptRoot 'putty.exe')
    )){if($local){[void]$candidates.Add($local)}}
    try {
        if(Test-Path -LiteralPath $SourcePath -PathType Leaf){
            $raw=Get-Content -LiteralPath $SourcePath -Raw
            $m=[regex]::Match($raw,"(?m)^\s*\`$PuttyPath\s*=\s*'([^']+)'\s*$")
            if($m.Success){[void]$candidates.Add($m.Groups[1].Value)}
        }
    } catch {}
    foreach($p in @(
        (Join-Path $env:ProgramFiles 'PuTTY\putty.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'PuTTY\putty.exe')
    )){if($p){[void]$candidates.Add($p)}}
    foreach($name in @('putty.exe','putty_portable.exe')){
        try{$cmd=Get-Command $name -ErrorAction SilentlyContinue;if($cmd -and $cmd.Source){[void]$candidates.Add($cmd.Source)}}catch{}
    }
    foreach($x in @($candidates)){if($x -and(Test-Path -LiteralPath $x -PathType Leaf)){return [string]$x}}
    return ''
}
function Get-PlinkPath {
    $candidates=New-Object Collections.ArrayList
    $putty=Get-PuttyPath
    if($putty){
        $dir=Split-Path -Parent $putty
        foreach($name in @('plink.exe','plink_portable.exe','plink64.exe')){[void]$candidates.Add((Join-Path $dir $name))}
    }
    foreach($p in @(
        (Join-Path $env:ProgramFiles 'PuTTY\plink.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'PuTTY\plink.exe')
    )){if($p){[void]$candidates.Add($p)}}
    foreach($name in @('plink.exe','plink64.exe','plink_portable.exe')){
        try{$cmd=Get-Command $name -ErrorAction SilentlyContinue;if($cmd -and $cmd.Source){[void]$candidates.Add($cmd.Source)}}catch{}
    }
    foreach($x in @($candidates)){if($x -and(Test-Path -LiteralPath $x -PathType Leaf)){return [string]$x}}
    return ''
}


function Get-SavedSessionInfo([string]$Name){
    if(-not $Name){return $null}
    try{return Get-ItemProperty -LiteralPath ('HKCU:\Software\SimonTatham\PuTTY\Sessions\'+$Name) -ErrorAction Stop}catch{return $null}
}
function Test-SavedSessionNonPasswordAuth($Info){
    if(-not $Info){return $false}
    try{$key=[Environment]::ExpandEnvironmentVariables([string]$Info.PublicKeyFile);if($key -and(Test-Path -LiteralPath $key -PathType Leaf)){return $true}}catch{}
    try{if(Get-Process -Name 'pageant' -ErrorAction SilentlyContinue|Select-Object -First 1){return $true}}catch{}
    return $false
}
function Get-VpsPuttyVersion([string]$Executable){
    $s=''
    try{$s=[string](Get-Item -LiteralPath $Executable -ErrorAction Stop).VersionInfo.ProductVersion}catch{}
    if(-not $s){try{$s=[string](Get-Item -LiteralPath $Executable -ErrorAction Stop).VersionInfo.FileVersion}catch{}}
    $m=[regex]::Match($s,'(\d+)\.(\d+)')
    if($m.Success){try{return [version]("$($m.Groups[1].Value).$($m.Groups[2].Value)")}catch{}}
    return $null
}
function Test-VpsPwFileSupport([string]$Executable){
    $v=Get-VpsPuttyVersion $Executable
    return ($v -and ($v.Major -gt 0 -or $v.Minor -ge 77))
}
function New-VpsSecurePwFile([string]$Password){
    if(-not $Password){return ''}
    $dir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3\secure-credentials'
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){
        New-Item -ItemType Directory -Path $dir -Force -ErrorAction Stop|Out-Null
    }
    Get-ChildItem -LiteralPath $dir -Filter '*.pwtmp' -File -ErrorAction SilentlyContinue|
        Where-Object{$_.LastWriteTime -lt (Get-Date).AddMinutes(-5)}|
        Remove-Item -Force -ErrorAction SilentlyContinue

    $currentSid=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid=New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $fileSecurity=New-Object Security.AccessControl.FileSecurity
    $fileSecurity.SetAccessRuleProtection($true,$false)
    $currentRuleArgs=@(
        $currentSid,
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $systemRuleArgs=@(
        $systemSid,
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $currentRule=New-Object -TypeName Security.AccessControl.FileSystemAccessRule -ArgumentList $currentRuleArgs
    $systemRule=New-Object -TypeName Security.AccessControl.FileSystemAccessRule -ArgumentList $systemRuleArgs
    [void]$fileSecurity.AddAccessRule($currentRule)
    [void]$fileSecurity.AddAccessRule($systemRule)

    $path=Join-Path $dir (([guid]::NewGuid().ToString('N'))+'.pwtmp')
    $stream=$null
    try{
        $streamArgs=@(
            $path,
            [IO.FileMode]::CreateNew,
            [Security.AccessControl.FileSystemRights]::Modify,
            [IO.FileShare]::Read,
            4096,
            [IO.FileOptions]::WriteThrough,
            $fileSecurity
        )
        $stream=New-Object -TypeName IO.FileStream -ArgumentList $streamArgs
        $bytes=[Text.Encoding]::UTF8.GetBytes($Password+"`r`n")
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush()
    }
    catch{
        if($stream){try{$stream.Dispose()}catch{};$stream=$null}
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        throw
    }
    finally{if($stream){try{$stream.Dispose()}catch{}}}

    $acl=Get-Acl -LiteralPath $path -ErrorAction Stop
    if(-not [bool]$acl.AreAccessRulesProtected){
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        throw 'Credential file ACL inheritance is not disabled.'
    }
    $allowedSids=@([string]$currentSid.Value,[string]$systemSid.Value)
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $unexpected=@($rules|Where-Object{
        [string]$_.AccessControlType -ne 'Allow' -or
        $allowedSids -notcontains [string]$_.IdentityReference.Value
    })
    if($unexpected.Count -gt 0){
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        throw 'Credential file ACL contains unexpected access rules.'
    }
    foreach($requiredSid in $allowedSids){
        if(@($rules|Where-Object{[string]$_.IdentityReference.Value -eq $requiredSid}).Count -eq 0){
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
            throw "Credential file ACL is missing required SID $requiredSid."
        }
    }
    return $path
}
function Remove-VpsSecurePwFile([string]$Path){
    if(-not $Path){return}
    try{if(Test-Path -LiteralPath $Path -PathType Leaf){Remove-Item -LiteralPath $Path -Force -ErrorAction Stop}}catch{}
}
function Get-Args($p,[string]$Plink,[switch]$Batch){
    $a=New-Object Collections.ArrayList
    if($Batch){[void]$a.Add('-batch')}
    $pw=Get-Secret ([string]$p.Id)
    $pwfile=''
    $mode=[string]$p.AuthMode
    try{
        if($mode -eq 'SavedSession'){
            if(-not $p.SavedSession){Fail 'Не указана PuTTY session.'}
            $si=Get-SavedSessionInfo ([string]$p.SavedSession)
            if(-not $si){Fail "PuTTY session '$([string]$p.SavedSession)' не найдена."}
            if(-not $pw -and -not(Test-SavedSessionNonPasswordAuth $si)){
                Fail 'SavedSession не имеет сохранённого DPAPI-пароля и не подтверждён .ppk/Pageant. Введите пароль один раз во вкладке VPS-серверы и сохраните профиль.'
            }
            [void]$a.Add('-load');[void]$a.Add([string]$p.SavedSession)
            if($p.User){[void]$a.Add('-l');[void]$a.Add([string]$p.User)}
            if($pw){
                if(-not(Test-VpsPwFileSupport $Plink)){Fail 'Plink -pwfile requires version 0.77 or newer; plaintext -pw fallback is forbidden.'}
                $pwfile=New-VpsSecurePwFile $pw
                [void]$a.Add('-pwfile');[void]$a.Add($pwfile)
            }
        }
        else{
            if(-not $p.Host){Fail 'Не указан Host/IP.'}
            foreach($item in @('-ssh','-P',([string][int]$p.SshPort),'-l',[string]$p.User)){[void]$a.Add($item)}
            if($mode -eq 'Password'){
                if(-not $pw){Fail 'Для режима IP/пароль сохранённый пароль не найден.'}
                if(-not(Test-VpsPwFileSupport $Plink)){Fail 'Plink -pwfile requires version 0.77 or newer; plaintext -pw fallback is forbidden.'}
                $pwfile=New-VpsSecurePwFile $pw
                [void]$a.Add('-pwfile');[void]$a.Add($pwfile)
            }
            elseif($mode -eq 'PrivateKey'){
                if(-not $p.KeyFile -or -not(Test-Path -LiteralPath ([string]$p.KeyFile))){Fail 'Файл приватного ключа .ppk не найден.'}
                [void]$a.Add('-i');[void]$a.Add([string]$p.KeyFile)
            }
            elseif($mode -eq 'Pageant'){[void]$a.Add('-agent')}
            else{Fail "Неизвестный AuthMode: $mode"}
            [void]$a.Add([string]$p.Host)
        }
        return [pscustomobject]@{Args=@($a);PasswordFile=$pwfile}
    }
    catch{
        if($pwfile){Remove-VpsSecurePwFile $pwfile;$pwfile=''}
        throw
    }
    finally{$pw=$null}
}
function Invoke-RemoteCapture($p,[string]$script){
    $plink=Get-PlinkPath
    if(-not $plink){Fail 'plink.exe не найден. Проверены локальный PuTTY PORTABLE рядом с V7, каталог PuTTY из V6.3.1, Program Files\PuTTY и PATH.'}
    $argState=Get-Args $p -Plink $plink -Batch
    $a=@($argState.Args)
    $pwfile=[string]$argState.PasswordFile
    $oldEap=$ErrorActionPreference
    $out=@();$rc=1
    try{
        # PowerShell 5.1 can turn native stderr redirected with 2>&1 into NativeCommandError.
        # Keep the native process authoritative and read its real LASTEXITCODE.
        $ErrorActionPreference='Continue'
        $out=@($script | & $plink @a 'sh -s' 2>&1 | ForEach-Object { [string]$_ })
        $rc=[int]$LASTEXITCODE
    }finally{
        $ErrorActionPreference=$oldEap
        if($pwfile){Remove-VpsSecurePwFile $pwfile}
    }
    if($rc -ne 0){
        $out|ForEach-Object{Write-Output $_}
        [Console]::Error.WriteLine("SSH/plink не установил соединение (код $rc). Это ошибка SSH-транспорта, а не успешная операция VPS. Проверьте доступность SSH/порт/host key; SOCKS через этот VPS не сможет работать, пока SSH не восстановлен.")
        if($rc -gt 0){exit $rc}else{exit 1}
    }
    return @($out)
}
function Invoke-RemoteScript($p,[string]$script){$out=Invoke-RemoteCapture $p $script;$out|ForEach-Object{Write-Output $_}}
$p=Get-Profile
if($Action -eq 'OpenSsh'){$putty=Get-PuttyPath;if(-not $putty){Fail 'PuTTY не найден.'};$mode=[string]$p.AuthMode;if($mode -eq 'SavedSession'){$a=@('-load',[string]$p.SavedSession);if($p.User){$a+=@('-l',[string]$p.User)}}else{$a=@('-ssh','-P',([string][int]$p.SshPort),'-l',[string]$p.User);if($mode -eq 'PrivateKey' -and $p.KeyFile){$a+=@('-i',[string]$p.KeyFile)}elseif($mode -eq 'Pageant'){$a+='-agent'};$a+=[string]$p.Host};Start-Process -FilePath $putty -ArgumentList $a|Out-Null;Write-Output 'PuTTY открыт без передачи DPAPI-пароля в командной строке. Сверьте fingerprint SSH host key. Для PrivateKey/Pageant используется выбранный ключ/агент.';exit 0}
if($Action -eq 'Health'){
$out=Invoke-RemoteCapture $p @'
printf 'PUBLIC_IP='; (curl -4 -fsS --max-time 8 https://ifconfig.me 2>/dev/null || wget -qO- --timeout=8 https://ifconfig.me 2>/dev/null || true); echo
printf 'CPU_CORES='; (getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 1)
printf 'LOAD1='; awk '{print $1}' /proc/loadavg 2>/dev/null || echo 0
printf 'MEM_TOTAL_KB='; awk '/MemTotal:/{print $2}' /proc/meminfo 2>/dev/null || echo 0
printf 'MEM_AVAIL_KB='; awk '/MemAvailable:/{print $2}' /proc/meminfo 2>/dev/null || awk '/MemFree:/{print $2}' /proc/meminfo 2>/dev/null || echo 0
printf 'DISK_USED_PCT='; df -P / 2>/dev/null | awk 'NR==2{gsub(/%/,"",$5);print $5}' || echo 0
printf 'FAILED_SERVICES='; if command -v systemctl >/dev/null 2>&1; then systemctl --failed --no-legend --plain 2>/dev/null | grep -c . || true; else echo 0; fi
printf 'UPDATES_AVAILABLE='; if command -v apt-get >/dev/null 2>&1; then apt list --upgradable 2>/dev/null | tail -n +2 | wc -l; elif command -v dnf >/dev/null 2>&1; then dnf -q check-update 2>/dev/null | grep -c '^[A-Za-z0-9]' || true; else echo 0; fi
printf 'UPTIME_SECONDS='; awk '{printf "%.0f\n",$1}' /proc/uptime 2>/dev/null || echo 0
'@
$kv=@{};foreach($line in @($out)){if([string]$line -match '^([A-Z0-9_]+)=(.*)$'){$kv[$Matches[1]]=$Matches[2].Trim()}}
function Num([string]$k,[double]$d=0){try{return [double]::Parse(([string]$kv[$k]),[Globalization.CultureInfo]::InvariantCulture)}catch{return $d}}
$public=[string]$kv.PUBLIC_IP;$expected=([string]$p.ExpectedExitIp).Trim();$exitOk=($public -eq $expected -and $public)
$cores=[math]::Max(1,(Num 'CPU_CORES' 1));$load=Num 'LOAD1';$loadPerCore=$load/$cores
$mt=Num 'MEM_TOTAL_KB';$ma=Num 'MEM_AVAIL_KB';$memAvailPct=if($mt -gt 0){100*$ma/$mt}else{0}
$disk=Num 'DISK_USED_PCT';$failed=[int](Num 'FAILED_SERVICES');$updates=[int](Num 'UPDATES_AVAILABLE');$uptime=[int64](Num 'UPTIME_SECONDS')
$score=100;$reasons=New-Object System.Collections.ArrayList
if(-not $exitOk){$score-=30;[void]$reasons.Add("Внешний IP $public не совпадает с ожидаемым $expected (-30)")}
if($disk -ge 95){$score-=25;[void]$reasons.Add("Диск заполнен на $disk% (-25)")}elseif($disk -ge 85){$score-=15;[void]$reasons.Add("Диск заполнен на $disk% (-15)")}elseif($disk -ge 75){$score-=5;[void]$reasons.Add("Диск заполнен на $disk% (-5)")}
if($mt -gt 0){if($memAvailPct -lt 5){$score-=20;[void]$reasons.Add("Свободно памяти $([math]::Round($memAvailPct,1))% (-20)")}elseif($memAvailPct -lt 10){$score-=12;[void]$reasons.Add("Свободно памяти $([math]::Round($memAvailPct,1))% (-12)")}elseif($memAvailPct -lt 20){$score-=5;[void]$reasons.Add("Свободно памяти $([math]::Round($memAvailPct,1))% (-5)")}}
if($loadPerCore -ge 2){$score-=15;[void]$reasons.Add("Высокая load/core $([math]::Round($loadPerCore,2)) (-15)")}elseif($loadPerCore -ge 1){$score-=8;[void]$reasons.Add("Повышенная load/core $([math]::Round($loadPerCore,2)) (-8)")}
if($failed -gt 0){$score-=10;[void]$reasons.Add("Failed systemd services: $failed (-10)")}
if($updates -ge 50){$score-=8;[void]$reasons.Add("Доступно обновлений: $updates (-8)")}elseif($updates -ge 10){$score-=4;[void]$reasons.Add("Доступно обновлений: $updates (-4)")}
$score=[math]::Max(0,[math]::Min(100,$score));$rating=if($score -ge 90){'Отлично'}elseif($score -ge 75){'Хорошо'}elseif($score -ge 60){'Требует внимания'}else{'Плохо'}
$result=[pscustomobject]@{Version=1;ProfileId=[string]$p.Id;ProfileName=[string]$p.Name;Host=[string]$p.Host;SshPort=[int]$p.SshPort;User=[string]$p.User;AuthMode=[string]$p.AuthMode;SavedSession=[string]$p.SavedSession;KeyFile=[string]$p.KeyFile;GeneratedAt=(Get-Date).ToString('o');SshOk=$true;ExitIpOk=[bool]$exitOk;PublicIp=$public;ExpectedExitIp=$expected;Score=[int]$score;Rating=$rating;CpuCores=[int]$cores;Load1=[math]::Round($load,2);LoadPerCore=[math]::Round($loadPerCore,2);MemoryAvailablePct=[math]::Round($memAvailPct,1);DiskUsedPct=[math]::Round($disk,1);FailedServices=$failed;UpdatesAvailable=$updates;UptimeSeconds=$uptime;Reasons=@($reasons)}
$path=Join-Path $HealthDir (([string]$p.Id)+'.json');$enc=New-Object Text.UTF8Encoding($true);[IO.File]::WriteAllText($path,($result|ConvertTo-Json -Depth 6),$enc)
Write-Output "=== VPS HEALTH SCORE ===";Write-Output "Профиль: $([string]$p.Name)";Write-Output "SSH: PASS";Write-Output "Exit IP: $public / ожидается $expected => $(if($exitOk){'PASS'}else{'FAIL'})";Write-Output "Health Score: $score/100 · $rating";Write-Output "CPU: $cores cores · load1=$load · load/core=$([math]::Round($loadPerCore,2))";Write-Output "RAM available: $([math]::Round($memAvailPct,1))% · Disk used: $disk% · failed services: $failed · updates: $updates";if($reasons.Count){Write-Output 'Причины снижения:';$reasons|ForEach-Object{Write-Output " - $_"}}else{Write-Output 'Существенных ресурсных проблем не обнаружено.'};Write-Output "PRECHECK=$(if($exitOk){'PASS'}else{'FAIL'})";exit $(if($exitOk){0}else{2})
}
if($Action -eq 'Test'){Invoke-RemoteScript $p @'
printf 'VPSCC_SSH=OK\n'
printf 'HOST='; hostname 2>/dev/null || true
printf 'USER='; id -un 2>/dev/null || true
printf 'UID='; id -u 2>/dev/null || true
printf 'KERNEL='; uname -sr 2>/dev/null || true
printf 'PUBLIC_IP='; (curl -fsS --max-time 8 https://ifconfig.me 2>/dev/null || wget -qO- --timeout=8 https://ifconfig.me 2>/dev/null || true); echo
'@;exit 0}
if($Action -eq 'Diagnose'){Invoke-RemoteScript $p @'
echo '=== VPS CONTROL · READ-ONLY SERVER DIAGNOSTICS ==='
echo "TIME=$(date -Is 2>/dev/null || date)"
echo "HOST=$(hostname 2>/dev/null)"
echo "USER=$(id -un 2>/dev/null) UID=$(id -u 2>/dev/null)"
if [ -r /etc/os-release ]; then . /etc/os-release; echo "OS=${PRETTY_NAME:-$NAME}"; fi
echo "KERNEL=$(uname -srmo 2>/dev/null)"
echo "UPTIME=$(uptime -p 2>/dev/null || uptime 2>/dev/null)"
echo "CPU_CORES=$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo '?')"
printf 'LOAD='; cat /proc/loadavg 2>/dev/null | awk '{print $1,$2,$3}' || true
echo '--- MEMORY ---'; (free -h 2>/dev/null || cat /proc/meminfo 2>/dev/null | head -n 8 || true)
echo '--- DISK ---'; df -hT / 2>/dev/null || df -h / 2>/dev/null || true
echo '--- INODES ---'; df -ih / 2>/dev/null || true
echo '--- NETWORK ---'; ip -brief addr 2>/dev/null || ifconfig 2>/dev/null || true; ip route 2>/dev/null | head -n 12 || true
echo '--- PUBLIC IP ---'; (curl -fsS --max-time 8 https://ifconfig.me 2>/dev/null || wget -qO- --timeout=8 https://ifconfig.me 2>/dev/null || true); echo
echo '--- FAILED SERVICES ---'; if command -v systemctl >/dev/null 2>&1; then systemctl --failed --no-pager 2>/dev/null | head -n 30; else echo 'systemd: n/a'; fi
echo '--- LISTENING TCP ---'; (ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true) | head -n 40
echo '--- TOP CPU ---'; ps -eo pid,comm,%cpu,%mem --sort=-%cpu 2>/dev/null | head -n 12 || true
echo '--- TOP MEM ---'; ps -eo pid,comm,%cpu,%mem --sort=-%mem 2>/dev/null | head -n 12 || true
echo '--- DOCKER ---'; if command -v docker >/dev/null 2>&1; then docker --version 2>/dev/null; docker info --format 'containers={{.Containers}} running={{.ContainersRunning}} images={{.Images}}' 2>/dev/null || true; else echo 'not installed'; fi
echo '--- SECURITY/UPDATES READINESS ---'; command -v fail2ban-client >/dev/null 2>&1 && echo 'fail2ban=installed' || echo 'fail2ban=not-installed'; command -v ufw >/dev/null 2>&1 && echo 'ufw=installed' || true; command -v nft >/dev/null 2>&1 && echo 'nftables=available' || true
if command -v apt-get >/dev/null 2>&1; then echo 'PKG=apt'; n=$(apt list --upgradable 2>/dev/null | tail -n +2 | wc -l); echo "UPDATES_AVAILABLE=$n"; elif command -v dnf >/dev/null 2>&1; then echo 'PKG=dnf'; dnf -q check-update >/tmp/vpscc-upd.$$ 2>/dev/null; rc=$?; [ "$rc" = 100 ] && echo "UPDATES_AVAILABLE=$(wc -l </tmp/vpscc-upd.$$)" || echo 'UPDATES_AVAILABLE=0/unknown'; rm -f /tmp/vpscc-upd.$$; elif command -v yum >/dev/null 2>&1; then echo 'PKG=yum'; elif command -v apk >/dev/null 2>&1; then echo 'PKG=apk'; else echo 'PKG=unknown'; fi
echo '=== END READ-ONLY DIAGNOSTICS ==='
'@;exit 0}
if($Action -eq 'PlanPackages'){Invoke-RemoteScript $p @'
echo '=== SAFE PACKAGE PLAN (NO CHANGES) ==='
if command -v apt-get >/dev/null 2>&1; then echo 'Manager: apt'; echo 'Baseline: curl ca-certificates jq htop ncdu lsof dnsutils iproute2 traceroute unzip'; echo 'Monitoring: sysstat vnstat iotop'; elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then echo 'Manager: dnf/yum'; echo 'Baseline: curl ca-certificates jq htop ncdu lsof bind-utils iproute traceroute unzip'; echo 'Monitoring: sysstat vnstat iotop'; elif command -v apk >/dev/null 2>&1; then echo 'Manager: apk'; echo 'Baseline: curl ca-certificates jq htop ncdu lsof bind-tools iproute2 traceroute unzip'; echo 'Monitoring: sysstat vnstat iotop'; else echo 'Unsupported package manager.'; fi
if [ "$(id -u)" = 0 ]; then echo 'Privileges: root OK'; elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then echo 'Privileges: passwordless sudo OK'; else echo 'Privileges: NO (install disabled; use root or passwordless sudo)'; fi
echo 'Policy: package install only; no OS upgrade, no SSH/firewall/sysctl changes.'
'@;exit 0}
if($Action -in @('InstallBaseline','InstallMonitoring')){
$kind=$Action
$installScript=@'
set -eu
if [ "$(id -u)" = 0 ]; then SUDO=''; elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then SUDO='sudo -n'; else echo 'ERROR: root/passwordless sudo required'; exit 20; fi
ACTION='__ACTION__'
if command -v apt-get >/dev/null 2>&1; then
  PM=apt; BASE='curl ca-certificates jq htop ncdu lsof dnsutils iproute2 traceroute unzip'; MON='sysstat vnstat iotop'
  $SUDO apt-get update -y
  if [ "$ACTION" = 'InstallBaseline' ]; then $SUDO apt-get install -y $BASE; else $SUDO apt-get install -y $MON; fi
elif command -v dnf >/dev/null 2>&1; then
  PM=dnf; BASE='curl ca-certificates jq htop ncdu lsof bind-utils iproute traceroute unzip'; MON='sysstat vnstat iotop'
  if [ "$ACTION" = 'InstallBaseline' ]; then $SUDO dnf install -y $BASE; else $SUDO dnf install -y $MON; fi
elif command -v yum >/dev/null 2>&1; then
  PM=yum; BASE='curl ca-certificates jq htop ncdu lsof bind-utils iproute traceroute unzip'; MON='sysstat vnstat iotop'
  if [ "$ACTION" = 'InstallBaseline' ]; then $SUDO yum install -y $BASE; else $SUDO yum install -y $MON; fi
elif command -v apk >/dev/null 2>&1; then
  PM=apk; BASE='curl ca-certificates jq htop ncdu lsof bind-tools iproute2 traceroute unzip'; MON='sysstat vnstat iotop'
  $SUDO apk update
  if [ "$ACTION" = 'InstallBaseline' ]; then $SUDO apk add $BASE; else $SUDO apk add $MON; fi
else echo 'ERROR: unsupported package manager'; exit 21; fi
echo "INSTALL_OK manager=$PM action=$ACTION"
echo 'No OS upgrade / SSH / firewall / sysctl changes were performed.'
'@
$installScript=$installScript.Replace('__ACTION__',$kind)
Invoke-RemoteScript $p $installScript
exit 0
}
