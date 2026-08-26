#requires -Version 5.1
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('Probe','HostKeyProbe','OpenEntwareSsh','EntwareStatus','EntwareRefresh','EntwareUpgrade','InstallReadiness')][string]$Action
)
$ErrorActionPreference='Stop'
$StorageHelper=Join-Path $PSScriptRoot 'modules\V7-Storage.ps1'
if(-not(Test-Path -LiteralPath $StorageHelper)){throw 'Не найден modules\V7-Storage.ps1'}
. $StorageHelper
$DataDir=Resolve-V7DataRoot -BaseDir $PSScriptRoot
$Layout=Initialize-V7StorageLayout -BaseDir $PSScriptRoot -DataRoot $DataDir
$ConfigFile=Join-Path $Layout.Keenetic 'keenetic.json'
$SecretFile=Join-Path $Layout.Secrets 'keenetic-entware.dpapi'
$SourcePath=Join-Path $PSScriptRoot 'VPS-Control-v6.3.1.ps1'
function Fail([string]$m,[int]$c=1){[Console]::Error.WriteLine($m);exit $c}
function Read-Cfg { if(-not(Test-Path -LiteralPath $ConfigFile)){return [pscustomobject]@{Host='192.0.2.1';EntwareSshPort=222;EntwareUser='root';EntwareHostKey=''}}; try{return Get-Content -LiteralPath $ConfigFile -Raw|ConvertFrom-Json}catch{Fail 'keenetic.json повреждён.'} }
function Get-Secret { if(-not(Test-Path -LiteralPath $SecretFile)){return ''}; try{$sec=ConvertTo-SecureString -String ((Get-Content -LiteralPath $SecretFile -Raw).Trim());$b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec);try{return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)}}catch{return ''} }
function Get-PuttyPath {
    $candidates=New-Object Collections.ArrayList
    # RC14.11: installation-local portable PuTTY is authoritative when present.
    foreach($local in @(
        (Join-Path $PSScriptRoot 'PuTTY PORTABLE\putty_portable.exe'),
        (Join-Path $PSScriptRoot 'PuTTY PORTABLE\putty.exe'),
        (Join-Path $PSScriptRoot 'putty_portable.exe'),
        (Join-Path $PSScriptRoot 'putty.exe')
    )){if($local){[void]$candidates.Add($local)}}
    try{
        if(Test-Path -LiteralPath $SourcePath -PathType Leaf){
            $raw=Get-Content -LiteralPath $SourcePath -Raw
            $m=[regex]::Match($raw,"(?m)^\s*\`$PuttyPath\s*=\s*'([^']+)'\s*$")
            if($m.Success){[void]$candidates.Add($m.Groups[1].Value)}
        }
    }catch{}
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
        foreach($name in @('plink.exe','plink64.exe','plink_portable.exe')){[void]$candidates.Add((Join-Path $dir $name))}
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

function Invoke-PlinkCapture([string[]]$PlinkArgs,[string]$InputText=''){
  $plink=Get-PlinkPath
  if(-not $plink){Fail 'plink.exe не найден. Проверены локальный PuTTY PORTABLE рядом с V7, каталог PuTTY из V6.3.1, Program Files\PuTTY и PATH.'}
  $oldEap=$ErrorActionPreference;$o=@();$rc=1
  try{
    $ErrorActionPreference='Continue'
    if($InputText){$o=@($InputText|& $plink @PlinkArgs 2>&1 | ForEach-Object { [string]$_ })}
    else{$o=@(& $plink @PlinkArgs 2>&1 | ForEach-Object { [string]$_ })}
    $rc=[int]$LASTEXITCODE
  }finally{$ErrorActionPreference=$oldEap}
  return [pscustomobject]@{ExitCode=$rc;Lines=@($o);Text=(@($o)-join "`r`n")}
}
function Invoke-Entware([string]$RemoteScript){
  $cfg=Read-Cfg
  $pw=Get-Secret;if(-not $pw){Fail 'Пароль Entware SSH не сохранён. Укажите его на вкладке Keenetic и сохраните в DPAPI.'}
  $hostKey='';try{$hostKey=[string]$cfg.EntwareHostKey}catch{}
  if(-not $hostKey){Fail 'SSH fingerprint Keenetic ещё не закреплён. Нажмите «Проверить / доверить SSH-ключ», сверьте SHA256 fingerprint и подтвердите его. Пароль повторно вводить не потребуется.' 21}
  $a=@('-batch','-ssh','-P',([string][int]$cfg.EntwareSshPort),'-l',[string]$cfg.EntwareUser,'-hostkey',$hostKey,'-pw',$pw,[string]$cfg.Host,'sh -s')
  $r=Invoke-PlinkCapture -PlinkArgs $a -InputText $RemoteScript
  $r.Lines|ForEach-Object{Write-Output $_}
  if([int]$r.ExitCode -ne 0){
    Fail "SSH Entware не установил соединение (код $([int]$r.ExitCode)). Проверьте SSH-порт, доступность роутера, pinned host key и сохранённый DPAPI-пароль." ([int]$r.ExitCode)
  }
}
$cfg=Read-Cfg;$routerAddress=[string]$cfg.Host
if($Action -eq 'HostKeyProbe'){
  $plink=Get-PlinkPath
  if(-not $plink){Fail 'plink.exe не найден. Проверены локальный PuTTY PORTABLE рядом с V7, каталог PuTTY из V6.3.1, Program Files\PuTTY и PATH.'}
  $a=@('-v','-batch','-ssh','-P',([string][int]$cfg.EntwareSshPort),'-l',[string]$cfg.EntwareUser,[string]$cfg.Host,'exit')
  $r=Invoke-PlinkCapture -PlinkArgs $a
  $all=[string]$r.Text
  $m=[regex]::Match($all,'SHA256:[A-Za-z0-9+/=]+')
  if(-not $m.Success){$m=[regex]::Match($all,'(?i)(?:[0-9a-f]{2}:){15}[0-9a-f]{2}')}
  if(-not $m.Success){
    Write-Output $all
    Fail 'Не удалось получить fingerprint SSH-сервера. Проверьте, что Entware SSH-порт доступен и сервер действительно отвечает протоколом SSH.' 22
  }
  Write-Output '=== KEENETIC SSH HOST KEY PROBE ==='
  Write-Output "HOST=$([string]$cfg.Host)"
  Write-Output "PORT=$([int]$cfg.EntwareSshPort)"
  Write-Output "HOSTKEY_FINGERPRINT=$($m.Value)"
  Write-Output 'TRUST=OWNER_CONFIRMATION_REQUIRED'
  exit 0
}
if($Action -eq 'OpenEntwareSsh'){
  $putty=Get-PuttyPath
  if(-not $putty){Fail 'PuTTY не найден. Проверены путь из V6.3.1, стандартный Program Files\PuTTY и PATH.'}
  $a=@('-ssh','-P',([string][int]$cfg.EntwareSshPort),'-l',[string]$cfg.EntwareUser,[string]$cfg.Host)
  Start-Process -FilePath $putty -ArgumentList $a | Out-Null
  Write-Output 'Интерактивный PuTTY открыт как ручная консоль. Для автоматической привязки host key используйте кнопку V7 «Проверить / доверить SSH-ключ» — она не требует повторного ввода пароля.'
  exit 0
}
if($Action -eq 'Probe'){
  Write-Output '=== KEENETIC · READ-ONLY PROBE ===';Write-Output "HOST=$routerAddress"
  try{$ping=Test-Connection -ComputerName $routerAddress -Count 1 -Quiet -ErrorAction Stop}catch{$ping=$false};Write-Output "PING=$(if($ping){'PASS'}else{'FAIL/ICMP-BLOCKED'})"
  foreach($port in @(80,443,[int]$cfg.EntwareSshPort)){try{$c=New-Object Net.Sockets.TcpClient;$ar=$c.BeginConnect($routerAddress,$port,$null,$null);$ok=$ar.AsyncWaitHandle.WaitOne(700,$false);if($ok -and $c.Connected){$c.EndConnect($ar);$state='OPEN'}else{$state='CLOSED'};$c.Close()}catch{$state='CLOSED'};Write-Output "TCP_$port=$state"}
  try{$r=Invoke-WebRequest -Uri ("http://$routerAddress/auth") -Method Get -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop;Write-Output "HTTP_AUTH=$($r.StatusCode)"}catch{if($_.Exception.Response){Write-Output "HTTP_AUTH=$([int]$_.Exception.Response.StatusCode.value__)";try{Write-Output "REALM=$($_.Exception.Response.Headers['X-NDM-Realm'])"}catch{}}else{Write-Output 'HTTP_AUTH=UNREACHABLE'}}
  exit 0
}
if($Action -eq 'EntwareStatus'){
$remote=@'
echo '=== ENTWARE STATUS ==='
printf 'HOST='; hostname 2>/dev/null || true
printf 'KERNEL='; uname -sr 2>/dev/null || true
if [ -x /opt/bin/opkg ] || command -v opkg >/dev/null 2>&1; then
 echo 'ENTWARE=INSTALLED'
 printf 'OPKG='; command -v opkg 2>/dev/null || echo /opt/bin/opkg
 printf 'OPT_MOUNT='; mount | grep ' /opt ' | head -n1 || true
 printf 'OPT_FS='; df -h /opt 2>/dev/null | tail -n1 || true
 printf 'PACKAGES='; opkg list-installed 2>/dev/null | wc -l
 printf 'UPGRADABLE='; opkg list-upgradable 2>/dev/null | wc -l
 [ -f /opt/etc/initrc ] && echo 'INITRC=PRESENT' || echo 'INITRC=UNKNOWN'
else
 echo 'ENTWARE=NOT_DETECTED'
 exit 0
fi
'@
Invoke-Entware $remote
exit 0
}
if($Action -eq 'EntwareRefresh'){
$remote=@'
set -e
command -v opkg >/dev/null 2>&1 || { echo 'ENTWARE=NOT_DETECTED'; exit 4; }
echo '=== ENTWARE REPOSITORY REFRESH ==='
opkg update
echo 'ENTWARE=INSTALLED'
echo 'REFRESH=PASS'
printf 'PACKAGES='; opkg list-installed 2>/dev/null | wc -l
printf 'UPGRADABLE='; opkg list-upgradable 2>/dev/null | wc -l
'@
Invoke-Entware $remote
exit 0
}
if($Action -eq 'EntwareUpgrade'){
$remote=@'
set -e
command -v opkg >/dev/null 2>&1 || { echo 'ENTWARE=NOT_DETECTED'; exit 4; }
echo '=== ENTWARE PACKAGE UPGRADE ==='
opkg update
before=$(opkg list-upgradable 2>/dev/null | wc -l)
echo "UPGRADABLE_BEFORE=$before"
if [ "$before" -eq 0 ]; then
 echo 'ENTWARE=INSTALLED'
 printf 'PACKAGES='; opkg list-installed 2>/dev/null | wc -l
 echo 'UPGRADABLE_AFTER=0'
 echo 'UPGRADE=NOT_NEEDED'
 exit 0
fi
opkg upgrade
after=$(opkg list-upgradable 2>/dev/null | wc -l)
echo 'ENTWARE=INSTALLED'
printf 'PACKAGES='; opkg list-installed 2>/dev/null | wc -l
echo "UPGRADABLE_AFTER=$after"
echo 'UPGRADE=PASS'
'@
Invoke-Entware $remote
exit 0
}
if($Action -eq 'InstallReadiness'){
  Write-Output '=== ENTWARE INSTALL/REMOVE READINESS ==='
  Write-Output "Router: $routerAddress"
  Write-Output 'RC14.11 намеренно не выполняет установку или полное удаление Entware.'
  Write-Output 'MUTATION=BLOCKED_RUNTIME_EVIDENCE_REQUIRED'
  Write-Output 'PRECONDITION_1=RCI inventory: model, KeeneticOS, CPU architecture'
  Write-Output 'PRECONDITION_2=Open Package support (OPKG) component state'
  Write-Output 'PRECONDITION_3=USB storage, filesystem, free space, existing /opt'
  Write-Output 'PRECONDITION_4=current opkg/initrc/services conflict inventory'
  Write-Output 'PRECONDITION_5=recovery backup of startup-config and Entware metadata'
  Write-Output 'PRECONDITION_6=exact transaction plan plus explicit owner confirmation'
  Write-Output 'FUTURE_FLOW=backup -> precheck -> exact plan -> confirmation -> mutation -> read-back verify -> health -> recovery if required'
  exit 0
}
