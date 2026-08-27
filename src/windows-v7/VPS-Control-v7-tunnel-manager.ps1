#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Status','StartReserve','StopReserve','TestReserve','SelectPrimaryRoute','SelectReserveRoute')]
    [string]$Action='Status',
    [string]$SourceRoot=$PSScriptRoot
)

$ErrorActionPreference='Stop'
Set-StrictMode -Version 2.0

$ReserveHost='127.0.0.1'
$ReservePort=1080
$ReserveId='RESERVE_MANUAL'
$PrimaryPort=1081

function Resolve-DataRoot([string]$BaseDir){
    $default=Join-Path $BaseDir 'VPS-Control-Data'
    $pointer=Join-Path $BaseDir 'VPS-Control-Data.location'
    if(-not(Test-Path -LiteralPath $pointer -PathType Leaf)){return $default}
    try{
        $raw=([IO.File]::ReadAllText($pointer,[Text.Encoding]::UTF8)).Trim()
        if(-not$raw){return $default}
        $expanded=[Environment]::ExpandEnvironmentVariables($raw)
        if(-not[IO.Path]::IsPathRooted($expanded)){$expanded=Join-Path $BaseDir $expanded}
        return [IO.Path]::GetFullPath($expanded)
    }catch{return $default}
}
$DataRoot=Resolve-DataRoot $SourceRoot
$RuntimeDir=Join-Path $DataRoot 'runtime'
$LogsDir=Join-Path $DataRoot 'logs'
$StatusFile=Join-Path $RuntimeDir 'tunnel-status.json'
$RoutingSelectionFile=Join-Path $RuntimeDir 'tunnel-routing.json'
$LogFile=Join-Path $LogsDir 'tunnel-manager.log'
foreach($d in @($RuntimeDir,$LogsDir)){if(-not(Test-Path -LiteralPath $d)){New-Item -ItemType Directory -Path $d -Force|Out-Null}}

function Safe([string]$Text){
    if($null-eq$Text){return ''}
    $s=[string]$Text
    $s=[regex]::Replace($s,'(?i)(-pw\s+)("[^"]*"|''[^'']*''|\S+)','$1<REDACTED>')
    $s=[regex]::Replace($s,'(?i)(-pwfile\s+)("[^"]*"|''[^'']*''|\S+)','$1<REDACTED_PATH>')
    $s=[regex]::Replace($s,'(?i)\b(password|passwd|pwd|token|secret|api[_-]?key|bearer)\s*[:=]\s*("[^"]*"|''[^'']*''|\S+)','$1=<REDACTED>')
    return $s
}
function Log([string]$Phase,[string]$Message){
    try{Add-Content -LiteralPath $LogFile -Value ('{0:yyyy-MM-dd HH:mm:ss.fff} [{1}] {2}' -f (Get-Date),$Phase,(Safe $Message)) -Encoding UTF8}catch{}
}
function Write-Status($Object){
    try{
        $json=$Object|ConvertTo-Json -Depth 12
        [IO.File]::WriteAllText($StatusFile,$json,(New-Object Text.UTF8Encoding($true)))
    }catch{}
}
function Get-Listener([int]$Port){
    try{
        $c=@(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $Port -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1)
        if($c.Count-ne1){return $null}
        $p=Get-CimInstance Win32_Process -Filter ("ProcessId="+[int]$c[0].OwningProcess) -ErrorAction SilentlyContinue
        return [pscustomobject]@{
            Port=$Port;Pid=[int]$c[0].OwningProcess;Name=$(if($p){[string]$p.Name}else{''});
            Path=$(if($p){[string]$p.ExecutablePath}else{''});
            CommandLine=$(if($p){Safe ([string]$p.CommandLine)}else{''});
            Raw=$(if($p){[string]$p.CommandLine}else{''})
        }
    }catch{return $null}
}
function Get-ReserveOwnership($Listener,$Profile,[string]$Identity=''){
    if(-not$Listener){
        return [pscustomobject]@{Proven=$false;Mode='OFF';Reason='not-listening';Session=''}
    }

    $name=[string]$Listener.Name
    $cmd=[string]$Listener.Raw
    $allowed=($name -match '(?i)^(putty|putty_portable|plink)\.exe$')
    if(-not$allowed){
        return [pscustomobject]@{Proven=$false;Mode='UNPROVEN';Reason="process=$name";Session=''}
    }

    if($cmd -match '(?i)(^|\s)-D\s+127\.0\.0\.1:1080(\s|$)'){
        return [pscustomobject]@{Proven=$true;Mode='VCC_MANUAL_EXPLICIT';Reason='explicit-D1080';Session=''}
    }

    $session=''
    $m=[regex]::Match($cmd,'(?i)(?:^|\s)-load\s+(?:"([^"]+)"|''([^'']+)''|(\S+))')
    if($m.Success){
        foreach($i in 1..3){if($m.Groups[$i].Success){$session=[string]$m.Groups[$i].Value;break}}
        $expected=[string]$Profile.SavedSession
        if($expected -and $session -eq $expected){
            return [pscustomobject]@{Proven=$true;Mode='USER_MANUAL_SAVEDSESSION';Reason='matching-saved-session';Session=$session}
        }
    }

    if($Identity -and $Identity -eq [string]$Profile.ExpectedExitIp){
        return [pscustomobject]@{Proven=$true;Mode='USER_MANUAL_EXTERNAL_VERIFIED';Reason='putty-family+expected-identity';Session=$session}
    }

    return [pscustomobject]@{Proven=$false;Mode='UNPROVEN';Reason='putty-family-without-explicit-D/session/identity-proof';Session=$session}
}
function Test-ReserveOwner($Listener,$Profile,[string]$Identity=''){
    $o=Get-ReserveOwnership $Listener $Profile $Identity
    return [bool]$o.Proven
}
function Get-Ip([int]$Port){
    try{
        $curl=Join-Path $env:SystemRoot 'System32\curl.exe'
        $o=&$curl '--silent' '--show-error' '--max-time' '12' '--socks5-hostname' ("127.0.0.1:"+$Port) 'https://ifconfig.me/ip' 2>&1
        if($LASTEXITCODE-ne0){return ''}
        $ip=(($o|Out-String)-replace'\s','').Trim();$parsed=$null
        if([Net.IPAddress]::TryParse($ip,[ref]$parsed)){return $ip}
    }catch{}
    return ''
}
function Get-ActiveProfile{
    $f=Join-Path $DataRoot 'nodes\vps\vps-profiles.json'
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "vps-profiles.json missing"}
    $d=Get-Content -LiteralPath $f -Raw|ConvertFrom-Json
    $p=@($d.Profiles|Where-Object{[string]$_.Id-eq[string]$d.ActiveId}|Select-Object -First 1)
    if($p.Count-ne1){throw "Active VPS profile unresolved"}
    return $p[0]
}
function Get-DpapiPassword([string]$ProfileId){
    $f=Join-Path $DataRoot ('secrets\vps\'+$ProfileId+'.dpapi')
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){return ''}
    $cipher=(Get-Content -LiteralPath $f -Raw).Trim()
    if(-not$cipher){return ''}
    $secure=ConvertTo-SecureString -String $cipher
    $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try{return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)}
    finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)}
}
function Decode([string]$Value){
    if($null-eq$Value){return ''}
    $v=[string]$Value;$v=$v-replace'\\\\','\';$v=$v-replace'\\"','"'
    try{$v=[Uri]::UnescapeDataString($v)}catch{}
    return $v
}
function SlashValue([string]$Raw,[string]$Name){
    if(-not$Raw){return ''}
    $m=[regex]::Match($Raw,'(?im)^\s*'+[regex]::Escape($Name)+'\\(.*?)\\\s*$')
    if($m.Success){return Decode ([string]$m.Groups[1].Value)}
    return ''
}
function Get-SavedSessionEndpoint([string]$Session){
    $dir=Join-Path $SourceRoot 'PuTTY PORTABLE'
    foreach($candidate in @((Join-Path $dir ('Sessions\'+$Session)),(Join-Path $dir ('sessions\'+$Session)))){
        if(Test-Path -LiteralPath $candidate -PathType Leaf){
            $raw=Get-Content -LiteralPath $candidate -Raw
            $h=SlashValue $raw 'HostName';$pt=SlashValue $raw 'PortNumber';$key=SlashValue $raw 'PublicKeyFile'
            if($h){return [pscustomobject]@{HostName=$h;Port=$(if($pt-match'^\d+$'){[int]$pt}else{22});KeyFile=$key;Source='SLASH_FILE'}}
        }
    }
    try{
        $r=Get-ItemProperty -LiteralPath ('HKCU:\Software\SimonTatham\PuTTY\Sessions\'+$Session) -ErrorAction Stop
        if($r.HostName){return [pscustomobject]@{HostName=[string]$r.HostName;Port=$(if($r.PortNumber){[int]$r.PortNumber}else{22});KeyFile=[string]$r.PublicKeyFile;Source='HKCU'}}
    }catch{}
    return $null
}


function ConvertFrom-V7PortableHostKeyName {
    param([string]$Name)

    if ($null -eq $Name) {
        return ''
    }

    try {
        return [Uri]::UnescapeDataString([string]$Name)
    }
    catch {
        return [string]$Name
    }
}

function Get-V7PortableHostKeyCandidates {
    param(
        [string]$PortableRoot,
        [string]$RemoteHost,
        [int]$RemotePort
    )

    $items = New-Object Collections.ArrayList

    if ([string]::IsNullOrWhiteSpace($PortableRoot)) {
        return @()
    }
    if ([string]::IsNullOrWhiteSpace($RemoteHost)) {
        return @()
    }
    if ($RemotePort -le 0) {
        return @()
    }

    $dir = Join-Path $PortableRoot 'SshHostKeys'
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
        return @()
    }

    foreach ($f in @(Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue)) {
        $decoded = ConvertFrom-V7PortableHostKeyName -Name $f.Name
        $targetPattern = '(?i)@' + $RemotePort + ':' + [regex]::Escape($RemoteHost) + '$'

        if ($decoded -notmatch $targetPattern) {
            continue
        }

        $value = ''
        try {
            $value = (Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop).Trim()
        }
        catch {
            continue
        }

        if ([string]::IsNullOrWhiteSpace($value)) {
            continue
        }

        [void]$items.Add([pscustomobject]@{
            Name       = $decoded
            SourcePath = $f.FullName
            Value      = $value
        })
    }

    return @($items)
}

function Ensure-V7OfficialPuttyHostKeyTrust {
    param(
        [string]$PortableRoot,
        [string]$RemoteHost,
        [int]$RemotePort
    )

    $registryPath = 'HKCU:\Software\SimonTatham\PuTTY\SshHostKeys'
    $candidates = @(
        Get-V7PortableHostKeyCandidates `
            -PortableRoot $PortableRoot `
            -RemoteHost $RemoteHost `
            -RemotePort $RemotePort
    )

    if ($candidates.Count -eq 0) {
        Log 'HOSTKEY_TRUST' (
            "FAIL source=portable reason=NOT_FOUND host=$RemoteHost port=$RemotePort"
        )
        return $false
    }

    if (-not (Test-Path -LiteralPath $registryPath)) {
        try {
            New-Item -Path $registryPath -Force -ErrorAction Stop | Out-Null
        }
        catch {
            Log 'HOSTKEY_TRUST' (
                "FAIL registry-create error=" + $_.Exception.Message
            )
            return $false
        }
    }

    $imported = 0
    $existing = 0

    foreach ($candidate in $candidates) {
        $name = [string]$candidate.Name
        $value = [string]$candidate.Value
        $present = $false
        $existingValue = ''

        try {
            $key = Get-Item -LiteralPath $registryPath -ErrorAction Stop
            $valueNames = @($key.GetValueNames())

            if ($valueNames -contains $name) {
                $present = $true
                $existingValue = [string]$key.GetValue($name, '')
            }
        }
        catch {
            $present = $false
            $existingValue = ''
        }

        if ($present) {
            if ($existingValue -ne $value) {
                Log 'HOSTKEY_TRUST' (
                    "FAIL conflict=true name=$name host=$RemoteHost port=$RemotePort"
                )
                return $false
            }

            $existing++
            Log 'HOSTKEY_TRUST' (
                "PASS existing-identical=true name=$name"
            )
            continue
        }

        try {
            New-ItemProperty `
                -LiteralPath $registryPath `
                -Name $name `
                -Value $value `
                -PropertyType String `
                -Force `
                -ErrorAction Stop | Out-Null

            $verifyKey = Get-Item -LiteralPath $registryPath -ErrorAction Stop
            $verify = [string]$verifyKey.GetValue($name, '')

            if ($verify -ne $value) {
                throw 'registry verify mismatch'
            }

            $imported++
            Log 'HOSTKEY_TRUST' (
                "PASS imported=true name=$name source=portable"
            )
        }
        catch {
            Log 'HOSTKEY_TRUST' (
                "FAIL import name=$name error=" + $_.Exception.Message
            )
            return $false
        }
    }

    Log 'HOSTKEY_TRUST' (
        "PASS host=$RemoteHost port=$RemotePort candidates=$($candidates.Count) imported=$imported existing=$existing"
    )

    return $true
}

function Get-PuttyExecutable{
    foreach($p in @(
        (Join-Path $SourceRoot 'PuTTY PORTABLE\putty.exe'),
        (Join-Path $SourceRoot 'PuTTY PORTABLE\putty_portable.exe')
    )){if(Test-Path -LiteralPath $p -PathType Leaf){return $p}}
    throw 'Colocated PuTTY executable not found'
}
function Get-PuttyVersion([string]$Exe){
    $s=''
    try{$s=[string](Get-Item -LiteralPath $Exe).VersionInfo.ProductVersion}catch{}
    if(-not$s){try{$s=[string](Get-Item -LiteralPath $Exe).VersionInfo.FileVersion}catch{}}
    $m=[regex]::Match($s,'(\d+)\.(\d+)')
    if($m.Success){return [version]("$($m.Groups[1].Value).$($m.Groups[2].Value)")}
    return $null
}
function Test-PwFileSupport([string]$Exe){
    $v=Get-PuttyVersion $Exe
    return ($v-and($v.Major-gt0-or$v.Minor-ge77))
}
function New-SecurePwFile([string]$Password){
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
    $currentRule=New-Object -TypeName Security.AccessControl.FileSystemAccessRule -ArgumentList $currentRuleArgs

    $systemRuleArgs=@(
        $systemSid,
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow
    )
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
    finally{
        if($stream){try{$stream.Dispose()}catch{}}
    }

    $acl=Get-Acl -LiteralPath $path -ErrorAction Stop
    if(-not [bool]$acl.AreAccessRulesProtected){
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        throw 'Credential file ACL inheritance is not disabled.'
    }

    $allowedSids=@([string]$currentSid.Value,[string]$systemSid.Value)
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $unexpected=@(
        $rules|Where-Object{
            [string]$_.AccessControlType -ne 'Allow' -or
            $allowedSids -notcontains [string]$_.IdentityReference.Value
        }
    )
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

    Log 'CREDENTIAL_FILE' 'created=true acl=creation-time/current-user+system inheritance=disabled storage=LOCALAPPDATA mode=PWFILE'
    return $path
}

function Convert-ToProcessArgumentString {
    param([Parameter(Mandatory=$true)][string[]]$Items)
    $quoted=foreach($item in $Items){
        if($null -eq $item){'""';continue}
        $value=[string]$item
        if($value -notmatch '[\s"]'){$value;continue}
        $escaped=$value -replace '(\\*)"', '$1$1\"'
        $escaped=$escaped -replace '(\\+)$', '$1$1'
        '"'+$escaped+'"'
    }
    return ($quoted -join ' ')
}
function Get-RoutingSelection {
    $id='PRIMARY_AUTO'
    if(Test-Path -LiteralPath $RoutingSelectionFile -PathType Leaf){
        try{
            $d=Get-Content -LiteralPath $RoutingSelectionFile -Raw|ConvertFrom-Json
            if([string]$d.SelectedTunnelId -in @('PRIMARY_AUTO','RESERVE_MANUAL')){$id=[string]$d.SelectedTunnelId}
        }catch{}
    }
    return $id
}
function Set-RoutingSelection([ValidateSet('PRIMARY_AUTO','RESERVE_MANUAL')][string]$TunnelId,[string]$Reason){
    $obj=[pscustomobject]@{
        SchemaVersion=1
        SelectedTunnelId=$TunnelId
        UpdatedAt=(Get-Date).ToString('o')
        UpdatedBy='MANUAL_UI'
        Reason=$Reason
        AutomaticFailoverAllowed=$false
    }
    $json=$obj|ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText($RoutingSelectionFile,$json,(New-Object Text.UTF8Encoding($true)))
    return $obj
}
function Snapshot([string]$ActionName,[string]$Result,[string]$Detail=''){
    $p=Get-ActiveProfile
    $r=Get-Listener $ReservePort
    $p1081=Get-Listener $PrimaryPort
    $ip=$(if($r){Get-Ip $ReservePort}else{''})
    $ownership=Get-ReserveOwnership $r $p $ip
    $o=[pscustomobject]@{
        SchemaVersion=1;Timestamp=(Get-Date).ToString('o');LastAction=$ActionName;LastResult=$Result;Detail=$Detail;
        ExpectedExitIp=[string]$p.ExpectedExitIp;SelectedRoutingTunnelId=(Get-RoutingSelection);
        Primary=[pscustomobject]@{Id='PRIMARY_AUTO';Port=1081;Listening=($null-ne$p1081);Pid=$(if($p1081){$p1081.Pid}else{0})};
        Reserve=[pscustomobject]@{
            Id='RESERVE_MANUAL';Port=1080;LifecycleMode='MANUAL_ONLY';Listening=($null-ne$r);
            Pid=$(if($r){$r.Pid}else{0});OwnerProven=[bool]$ownership.Proven;OwnershipMode=[string]$ownership.Mode;
            OwnershipReason=[string]$ownership.Reason;SavedSession=$(if($ownership.Session){[string]$ownership.Session}else{''});
            Identity=$ip;IdentityMatch=($ip-and$ip-eq[string]$p.ExpectedExitIp)
        }
    }
    Write-Status $o;return $o
}

try{
    Log 'ACTION' "begin action=$Action reserve=127.0.0.1:1080 lifecycle=MANUAL_ONLY"
    if($Action-eq'Status'){Snapshot $Action 'PASS'|ConvertTo-Json -Depth 8;exit 0}
    if($Action-eq'TestReserve'){
        $s=Snapshot $Action 'PASS'
        if(-not$s.Reserve.Listening){throw 'Reserve 1080 is OFF (allowed; manual reserve is optional).'}
        if(-not$s.Reserve.OwnerProven){throw 'Reserve 1080 listener ownership is not proven.'}
        if(-not$s.Reserve.IdentityMatch){throw "Reserve identity mismatch: $($s.Reserve.Identity)"}
        exit 0
    }
    if($Action-eq'SelectPrimaryRoute'){
        [void](Set-RoutingSelection 'PRIMARY_AUTO' 'manual-select-primary')
        Snapshot $Action 'PASS' 'routing-via-1081'|Out-Null
        Log 'ROUTE_SELECT' 'PASS selected=PRIMARY_AUTO port=1081'
        exit 0
    }
    if($Action-eq'SelectReserveRoute'){
        $p=Get-ActiveProfile
        $l=Get-Listener $ReservePort
        if(-not$l){throw 'Reserve 1080 is OFF. Start it manually before selecting it for VPS routes.'}
        $ip=Get-Ip $ReservePort
        $ownership=Get-ReserveOwnership $l $p $ip
        if(-not$ownership.Proven){throw "Reserve 1080 ownership is not proven; route selection blocked. mode=$($ownership.Mode) reason=$($ownership.Reason)"}
        if(-not$ip -or $ip-ne[string]$p.ExpectedExitIp){throw "Reserve 1080 identity mismatch; route selection blocked. actual=$ip"}
        [void](Set-RoutingSelection 'RESERVE_MANUAL' 'manual-select-reserve')
        Snapshot $Action 'PASS' 'routing-via-1080'|Out-Null
        Log 'ROUTE_SELECT' 'PASS selected=RESERVE_MANUAL port=1080'
        exit 0
    }
    if($Action-eq'StopReserve'){
        $l=Get-Listener $ReservePort
        if(-not$l){Snapshot $Action 'PASS' 'already-off'|Out-Null;exit 0}
        $p=Get-ActiveProfile
        $ip=Get-Ip $ReservePort
        $ownership=Get-ReserveOwnership $l $p $ip
        if(-not$ownership.Proven){
            throw "Port 1080 is occupied by an unproven process PID=$($l.Pid); mode=$($ownership.Mode); fail-closed."
        }
        Log 'STOP' "manual stop ownershipMode=$($ownership.Mode) pid=$($l.Pid)"
        Stop-Process -Id ([int]$l.Pid) -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 500
        if(Get-Listener $ReservePort){throw 'Reserve 1080 is still listening after manual stop.'}
        Snapshot $Action 'PASS' 'manual-stop'|Out-Null;Log 'STOP' "PASS pid=$($l.Pid)";exit 0
    }
    if($Action-eq'StartReserve'){
        $p=Get-ActiveProfile
        $existing=Get-Listener $ReservePort
        if($existing){
            $ip=Get-Ip $ReservePort
            $ownership=Get-ReserveOwnership $existing $p $ip
            if($ownership.Proven -and $ip-eq[string]$p.ExpectedExitIp){
                Snapshot $Action 'PASS' ("already-healthy/adopted:"+[string]$ownership.Mode)|Out-Null
                Log 'ADOPT' "PASS ownershipMode=$($ownership.Mode) pid=$($existing.Pid)"
                exit 0
            }
            throw "Port 1080 is occupied but reserve identity/ownership is not healthy; fail-closed."
        }
        $session=[string]$p.SavedSession
        if(-not$session){throw 'SavedSession is empty.'}
        $ep=Get-SavedSessionEndpoint $session
        if(-not$ep-or-not$ep.HostName){throw "SavedSession endpoint unresolved."}
        $exe=Get-PuttyExecutable
        $portableRoot=Join-Path $SourceRoot 'PuTTY PORTABLE'
        $remoteHost=[string]$ep.HostName
        $remotePort=[int]$ep.Port
        $hostKeyTrustOk=Ensure-V7OfficialPuttyHostKeyTrust `
            -PortableRoot $portableRoot `
            -RemoteHost $remoteHost `
            -RemotePort $remotePort
        if(-not $hostKeyTrustOk){
            throw 'Trusted SSH host key for active VPS is not available in official PuTTY store.'
        }
        $password=Get-DpapiPassword ([string]$p.Id)
        $args=@('-ssh','-P',([string]$ep.Port),'-D','127.0.0.1:1080','-N','-l',([string]$p.User))
        $pwfile=''
        try{
            if($password){
                if(-not(Test-PwFileSupport $exe)){throw 'PuTTY -pwfile requires version 0.77 or newer; plaintext -pw fallback is forbidden.'}
                $pwfile=New-SecurePwFile $password
                $args+=@('-pwfile',$pwfile)
            }elseif($ep.KeyFile-and(Test-Path -LiteralPath $ep.KeyFile -PathType Leaf)){$args+=@('-i',$ep.KeyFile)}
            elseif(Get-Process pageant -ErrorAction SilentlyContinue|Select-Object -First 1){$args+='-agent'}
            else{throw 'No usable DPAPI/.ppk/Pageant credential.'}
            $args+=[string]$ep.HostName
            Log 'START' "manual reserve launch exe=$exe host=$($ep.HostName) port=$($ep.Port) local=1080 credential=$(if($pwfile){'PWFILE'}else{'KEY_OR_AGENT'})"
            $proc=Start-Process -FilePath $exe -ArgumentList (Convert-ToProcessArgumentString -Items $args) -WindowStyle Minimized -PassThru
            $deadline=(Get-Date).AddSeconds(45);$ok=$false
            while((Get-Date)-lt$deadline){
                Start-Sleep -Milliseconds 900
                $ip=Get-Ip $ReservePort
                if($ip-and$ip-eq[string]$p.ExpectedExitIp){$ok=$true;break}
                try{$proc.Refresh();if($proc.HasExited){break}}catch{}
            }
            try{$proc.Dispose()}catch{}
            if(-not$ok){throw 'Manual reserve 1080 did not reach expected VPS identity.'}
        }finally{
            $password=$null
            if($pwfile){Remove-Item -LiteralPath $pwfile -Force -ErrorAction SilentlyContinue}
        }
        Snapshot $Action 'PASS' 'manual-start'|Out-Null
        exit 0
    }
}catch{
    Log 'FAIL' ("action=$Action error="+$_.Exception.Message)
    try{Snapshot $Action 'FAIL' $_.Exception.Message|Out-Null}catch{}
    Write-Error $_.Exception.Message
    exit 50
}
