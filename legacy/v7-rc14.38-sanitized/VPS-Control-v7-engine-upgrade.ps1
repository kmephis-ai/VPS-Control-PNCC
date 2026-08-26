#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourcePath,
    [Parameter(Mandatory=$true)][string]$DestinationPath
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path -LiteralPath $SourcePath)) { Fail "Исходный VPS-Control-v6.3.1.ps1 не найден: $SourcePath" }
if ((Split-Path -Parent $SourcePath) -ne (Split-Path -Parent $DestinationPath)) {
    Fail 'V6.5 должен создаваться рядом с V6.3.1.'
}

$raw = [IO.File]::ReadAllText($SourcePath)
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($raw, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors -and $parseErrors.Count -gt 0) {
    Fail ("V6.3.1 не прошёл PowerShell AST parse: " + (($parseErrors | ForEach-Object Message) -join '; '))
}

$replacements = @{}

$replacements['Get-DefaultModuleCatalogJson'] = @'
function Get-DefaultModuleCatalogJson {
    if (Test-Path -LiteralPath $BundledModulesFile) {
        return (Get-Content -LiteralPath $BundledModulesFile -Raw -ErrorAction Stop)
    }
    throw "Bundled module catalog missing: $BundledModulesFile"
}
'@

$replacements['New-DefaultConfig'] = @'
function New-DefaultConfig {
    $h = [ordered]@{ Version = $ControllerVersion }
    foreach ($module in $ModuleNames) {
        $fallback = if ($ModuleDefaultModes.ContainsKey($module)) { [string]$ModuleDefaultModes[$module] } else { 'DIRECT' }
        $h[$module] = $fallback
    }
    return [pscustomobject]$h
}
'@

$replacements['Normalize-Config'] = @'
function Normalize-Config($Config) {
    $h = [ordered]@{ Version = $ControllerVersion }
    foreach ($module in $ModuleNames) {
        $fallback = if ($ModuleDefaultModes.ContainsKey($module)) { [string]$ModuleDefaultModes[$module] } else { 'DIRECT' }
        $value = $null
        if ($Config -and $Config.PSObject.Properties[$module]) { $value = [string]$Config.$module }
        $h[$module] = Normalize-Mode $value $fallback
    }
    return [pscustomobject]$h
}
'@

$replacements['New-RouteObject'] = @'
function New-RouteObject {
    $h = [ordered]@{}
    foreach ($module in $ModuleNames) { $h[$module] = 'DIRECT' }
    return [pscustomobject]$h
}
'@

$replacements['Normalize-Routes'] = @'
function Normalize-Routes($Routes) {
    $result = New-RouteObject
    if (-not $Routes) { return $result }
    foreach ($module in $ModuleNames) {
        if ($Routes.PSObject.Properties[$module] -and [string]$Routes.$module -eq 'VPS') { $result.$module = 'VPS' }
        else { $result.$module = 'DIRECT' }
    }
    return $result
}
'@

$replacements['New-HealthObject'] = @'
function New-HealthObject {
    $h = [ordered]@{}
    foreach ($module in $ModuleNames) { $h[$module] = 'UNKNOWN' }
    return [pscustomobject]$h
}
'@

$replacements['New-MetricsObject'] = @'
function New-MetricsObject {
    $h = [ordered]@{}
    foreach ($module in $ModuleNames) { $h[$module] = New-ModuleMetric }
    return [pscustomobject]$h
}
'@

$replacements['New-AutoStateObject'] = @'
function New-AutoStateObject {
    $h = [ordered]@{}
    foreach ($module in $ModuleNames) { $h[$module] = New-AutoModuleState }
    return [pscustomobject]$h
}
'@

$replacements['Set-DesiredMode'] = @'
function Set-DesiredMode(
    [string]$Module,
    [ValidateSet('DIRECT','AUTO','VPS')][string]$Mode
) {
    if ($ModuleNames -notcontains $Module) { throw "Unknown module: $Module" }
    Invoke-WithMutationLock {
        $config = Get-Config
        $config.$Module = $Mode
        Save-Config $config
    } | Out-Null
}
'@

$replacements['Cycle-DesiredMode'] = @'
function Cycle-DesiredMode([string]$Module) {
    if ($ModuleNames -notcontains $Module) { throw "Unknown module: $Module" }
    Invoke-WithMutationLock {
        $config = Get-Config
        $current = Normalize-Mode ([string]$config.$Module)
        switch ($current) {
            'DIRECT' { $config.$Module = 'AUTO' }
            'AUTO' { $config.$Module = 'VPS' }
            default { $config.$Module = 'DIRECT' }
        }
        Save-Config $config
    } | Out-Null
}
'@

$replacements['Test-ModuleHealth'] = @'
function Test-ModuleHealth(
    [Parameter(Mandatory=$true)][string]$Module,
    [Parameter(Mandatory=$true)][ValidateSet('DIRECT','VPS')][string]$Route
) {
    if ($ModuleNames -notcontains $Module) { throw "Unknown module: $Module" }
    $definition = Get-ModuleHealthDefinition $Module
    $details = New-Object System.Collections.Generic.List[string]
    $latencies = New-Object System.Collections.Generic.List[int]
    $passed = 0
    $lastStatus = 0
    $failureClasses = New-Object System.Collections.Generic.List[string]

    if ($Route -eq 'VPS' -and -not (Test-TcpPort $SocksHost $SocksPort)) {
        return [pscustomobject]@{
            Healthy=$false; State='FAILED'; Passed=0; Total=$definition.Urls.Count
            LatencyMs=0; HttpStatus=0; FailureClass='SOCKS_OFF'; Detail='SOCKS_OFF'
        }
    }

    foreach ($url in $definition.Urls) {
        $probe = Invoke-HttpProbe -Route $Route -Url $url
        $lastStatus = [int]$probe.HttpStatus
        if ($probe.Success) {
            $passed++
            if ($probe.LatencyMs -gt 0) { [void]$latencies.Add([int]$probe.LatencyMs) }
        }
        else { [void]$failureClasses.Add([string]$probe.FailureClass) }
        [void]$details.Add([string]$probe.Detail)
    }

    $latencyMs = 0
    if ($latencies.Count -gt 0) {
        $latencyMs = [int][math]::Round((($latencies | Measure-Object -Average).Average))
    }

    if ($passed -lt [int]$definition.Required) { $state = 'FAILED' }
    elseif ($latencyMs -gt 0 -and $latencyMs -ge [int]$definition.DegradedLatencyMs) { $state = 'DEGRADED' }
    else { $state = 'HEALTHY' }

    $failureClass = 'NONE'
    if ($failureClasses.Count -gt 0) { $failureClass = [string]($failureClasses | Select-Object -First 1) }
    elseif ($state -eq 'DEGRADED') { $failureClass = 'LATENCY' }

    return [pscustomobject]@{
        Healthy=($state -ne 'FAILED'); State=$state; Passed=$passed; Total=$definition.Urls.Count
        LatencyMs=$latencyMs; HttpStatus=$lastStatus; FailureClass=$failureClass; Detail=($details -join ' | ')
    }
}
'@

$replacements['Test-SocksIdentity'] = @'
function Test-SocksIdentity {
    $portOpen=Test-TcpPort $SocksHost $SocksPort
    if(-not $portOpen){ return $false }
    $ip=Get-SocksExternalIp
    $ok=($ip -and $ip -eq $ExpectedVpsIp)
    Write-V7SocksEngineTrace 'IDENTITY' ("port=OPEN; observedIp=$(if($ip){$ip}else{'EMPTY'}); expectedIp=$ExpectedVpsIp; ok=$ok")
    return $ok
}
'@

$replacements['Get-EffectivePuttyPassword'] = @'
function Get-EffectivePuttyPassword {
    try {
        if ($VpsSecretId) {
            $secretPath = Join-Path $VpsSecretsDir ($VpsSecretId + '.dpapi')
            if (Test-Path -LiteralPath $secretPath) {
                $cipher = (Get-Content -LiteralPath $secretPath -Raw -ErrorAction Stop).Trim()
                if ($cipher) {
                    $secure = ConvertTo-SecureString -String $cipher -ErrorAction Stop
                    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
                    try {
                        $value=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
                        Write-V7SocksEngineTrace 'CREDENTIAL' 'source=V7-DPAPI; decrypt=PASS; value=<redacted>'
                        return $value
                    }
                    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
                }
            }
        }
    } catch { Write-V7SocksEngineTrace 'CREDENTIAL' ("source=V7-DPAPI; decrypt=FAIL; error="+$_.Exception.Message) }
    if ($PuttyPassword -and $PuttyPassword -ne 'CHANGE_ME') { Write-V7SocksEngineTrace 'CREDENTIAL' 'source=current-script; value=<redacted>'; return $PuttyPassword }
    if (-not $ReusePasswordFromSiblingV6) { Write-V7SocksEngineTrace 'CREDENTIAL' 'source=none; siblingReuse=false'; return '' }
    foreach ($name in @('VPS-Control-v6.3.1.ps1','VPS-Control-v6.3.ps1','VPS-Control-v6.2.1.ps1','VPS-Control-v6.2.ps1','VPS-Control-v6.1.ps1','VPS-Control-v6.ps1','VPS-Control-v5.ps1')) {
        $legacy = Join-Path $PSScriptRoot $name
        if (-not (Test-Path -LiteralPath $legacy)) { continue }
        try {
            $legacyRaw = Get-Content -LiteralPath $legacy -Raw -ErrorAction Stop
            $match = [regex]::Match($legacyRaw, "(?m)^\s*\`$PuttyPassword\s*=\s*'([^']+)'\s*$")
            if ($match.Success -and $match.Groups[1].Value -and $match.Groups[1].Value -ne 'CHANGE_ME') { Write-V7SocksEngineTrace 'CREDENTIAL' ("source=legacy:"+$name+"; value=<redacted>"); return $match.Groups[1].Value }
        } catch { Write-V7SocksEngineTrace 'CREDENTIAL' ("legacy-read-fail file="+$name+" error="+$_.Exception.Message) }
    }
    Write-V7SocksEngineTrace 'CREDENTIAL' 'source=none; passwordPresent=false'
    return ''
}
'@
$replacements['Test-PuttyConfigured'] = @'
function Get-SavedPuttySessionInfo {
    if (-not $PuttySession) { return $null }
    try {
        $path = 'HKCU:\Software\SimonTatham\PuTTY\Sessions\' + $PuttySession
        $info=Get-ItemProperty -LiteralPath $path -ErrorAction Stop
        Write-V7SocksEngineTrace 'SESSION_METADATA' ("name=$PuttySession; source=HKCU; host=$([string]$info.HostName); port=$([string]$info.PortNumber); keyConfigured=$([bool]([string]$info.PublicKeyFile))")
        return $info
    } catch {
        Write-V7SocksEngineTrace 'SESSION_METADATA' ("name=$PuttySession; source=HKCU; result=NOT_FOUND")
        return $null
    }
}
function Test-V7PortablePuttyLauncher {
    try {
        $leaf=[IO.Path]::GetFileName([string]$PuttyPath)
        if($leaf -match '(?i)portable'){return $true}
        $dir=Split-Path -Parent $PuttyPath
        if($dir -and $dir -match '(?i)portable'){return $true}
    } catch { }
    return $false
}
function ConvertFrom-V7PortableRegEscaped([string]$Value) {
    if($null -eq $Value){return ''}
    $v=[string]$Value
    $v=$v -replace '\\\\','\'
    $v=$v -replace '\\"','"'
    try{$v=[Uri]::UnescapeDataString($v)}catch{}
    return $v
}
function Get-V7PortableSlashValue([string]$Raw,[string]$Name) {
    if(-not $Raw -or -not $Name){return ''}
    try{
        # Russian PuTTY Portable / KiTTY-family file backend:
        # Name\value\
        $pattern='(?im)^\s*'+[regex]::Escape($Name)+'\\(.*?)\\\s*$'
        $m=[regex]::Match($Raw,$pattern)
        if($m.Success){
            return ConvertFrom-V7PortableRegEscaped ([string]$m.Groups[1].Value)
        }
    }catch{}
    return ''
}
function Get-V7PortablePuttySessionInfo {
    $result=[ordered]@{Found=$false;Source='';HostName='';PortNumber=22;Protocol='ssh';PublicKeyFile='';KeyConfigured=$false;PageantRunning=$false}
    try {
        $dir=Split-Path -Parent $PuttyPath
        if(-not $dir){return [pscustomobject]$result}
        $raw='';$source=''
        foreach($candidate in @(
            (Join-Path $dir ("Sessions\"+$PuttySession)),
            (Join-Path $dir ("sessions\"+$PuttySession))
        )){
            if(Test-Path -LiteralPath $candidate -PathType Leaf){
                try{$raw=Get-Content -LiteralPath $candidate -Raw -ErrorAction Stop;$source=$candidate;break}catch{}
            }
        }
        if(-not $raw){
            foreach($reg in @(
                (Join-Path $dir 'putty.reg'),
                (Join-Path $dir 'PuTTY.reg'),
                (Join-Path $dir 'Data\settings\putty.reg'),
                (Join-Path $dir 'data\settings\putty.reg')
            )){
                if(-not(Test-Path -LiteralPath $reg -PathType Leaf)){continue}
                try{
                    $all=Get-Content -LiteralPath $reg -Raw -ErrorAction Stop
                    $escaped=[regex]::Escape($PuttySession)
                    $m=[regex]::Match($all,"(?ms)^\[HKEY_CURRENT_USER\\Software\\SimonTatham\\PuTTY\\Sessions\\$escaped\]\s*(.*?)(?=^\[HKEY_|\z)")
                    if($m.Success){$raw=$m.Groups[1].Value;$source=$reg;break}
                }catch{}
            }
        }
        if(-not $raw){
            Write-V7SocksEngineTrace 'SESSION_METADATA' ("name=$PuttySession; source=PORTABLE; result=NOT_FOUND")
            return [pscustomobject]$result
        }
        $result.Found=$true;$result.Source=$source
        foreach($name in @('HostName','Protocol','PublicKeyFile')){
            $value=Get-V7PortableSlashValue -Raw $raw -Name $name

            # Registry-export / INI-like fallbacks.
            if(-not $value){
                $m=[regex]::Match($raw,'(?im)^\s*"?'+[regex]::Escape($name)+'"?\s*=\s*"([^"\r\n]*)"')
                if(-not $m.Success){$m=[regex]::Match($raw,'(?im)^\s*'+[regex]::Escape($name)+'\s*=\s*([^\r\n]+)')}
                if($m.Success){$value=ConvertFrom-V7PortableRegEscaped ($m.Groups[1].Value.Trim().Trim('"'))}
            }

            if($name -eq 'HostName'){$result.HostName=$value}
            elseif($name -eq 'Protocol'){$result.Protocol=$value}
            elseif($name -eq 'PublicKeyFile'){$result.PublicKeyFile=$value}
        }

        $slashPort=Get-V7PortableSlashValue -Raw $raw -Name 'PortNumber'
        if($slashPort -match '^\d+$'){
            try{$result.PortNumber=[int]$slashPort}catch{}
        }

        if(-not $result.PortNumber){
            $pm=[regex]::Match($raw,'(?im)^\s*"?PortNumber"?\s*=\s*dword:([0-9a-f]+)')
            if($pm.Success){try{$result.PortNumber=[Convert]::ToInt32($pm.Groups[1].Value,16)}catch{}}
        }
        if(-not $result.PortNumber){
            $pm=[regex]::Match($raw,'(?im)^\s*PortNumber\s*=\s*(\d+)')
            if($pm.Success){$result.PortNumber=[int]$pm.Groups[1].Value}
        }
        if(-not $result.PortNumber){$result.PortNumber=22}
        if($result.PublicKeyFile){
            $key=[Environment]::ExpandEnvironmentVariables([string]$result.PublicKeyFile)
            if(-not[IO.Path]::IsPathRooted($key)){$key=Join-Path $dir $key}
            $result.PublicKeyFile=$key
            try{$result.KeyConfigured=Test-Path -LiteralPath $key -PathType Leaf}catch{}
        }
        try{$result.PageantRunning=[bool](Get-Process -Name pageant -ErrorAction SilentlyContinue|Select-Object -First 1)}catch{}
        $format=$(if($raw -match '(?im)^\s*HostName\.*\\s*$'){'SLASH_FILE'}else{'REG_OR_INI'})
        Write-V7SocksEngineTrace 'SESSION_METADATA' ("name=$PuttySession; source=PORTABLE; format=$format; file=$source; found=true; host=$($result.HostName); port=$($result.PortNumber); keyConfigured=$($result.KeyConfigured); pageant=$($result.PageantRunning)")
    } catch {
        Write-V7SocksEngineTrace 'SESSION_METADATA' ("name=$PuttySession; source=PORTABLE; error="+$_.Exception.Message)
    }
    return [pscustomobject]$result
}
function Test-SavedPuttySessionHasNonPasswordAuth($Info) {
    if(-not $Info){return $false}
    try{
        $key=[string]$Info.PublicKeyFile
        if($key -and (Test-Path -LiteralPath ([Environment]::ExpandEnvironmentVariables($key)) -PathType Leaf)){return $true}
    }catch{}
    try{if(Get-Process -Name pageant -ErrorAction SilentlyContinue|Select-Object -First 1){return $true}}catch{}
    return $false
}
function Get-V7SavedSessionEndpoint {
    $info=Get-SavedPuttySessionInfo
    $source='HKCU'
    if(-not $info -and (Test-V7PortablePuttyLauncher)){
        $info=Get-V7PortablePuttySessionInfo
        $source='PORTABLE'
    }
    if(-not $info){return $null}
    $remoteHost=[string]$info.HostName
    $remotePort=22
    try{if([int]$info.PortNumber -gt 0){$remotePort=[int]$info.PortNumber}}catch{}
    if(-not $remoteHost){return $null}
    return [pscustomobject]@{Info=$info;Source=$source;Host=$remoteHost;Port=$remotePort}
}
function Test-PuttyConfigured {
    Write-V7SocksEngineTrace 'CONFIG_CHECK' ("begin auth=$VpsAuthMode; session=$PuttySession; vccSocks=${SocksHost}:$SocksPort")
    if(-not(Test-Path -LiteralPath $PuttyPath)){Write-Fail "PuTTY не найден: $PuttyPath";return $false}
    if($VpsAuthMode -eq 'SavedSession'){
        if(-not $PuttySession){Write-Fail 'Не указана SavedSession активного VPS.';return $false}
        $endpoint=Get-V7SavedSessionEndpoint
        if(-not $endpoint){
            Write-V7SocksEngineTrace 'CONFIG_CHECK' 'FAIL SAVED_SESSION_ENDPOINT_UNRESOLVED'
            Write-Fail "SavedSession '$PuttySession': VCC не смог прочитать SSH host/port. VCC SOCKS $SocksPort не запущен."
            return $false
        }
        $password=Get-EffectivePuttyPassword
        $nonPassword=Test-SavedPuttySessionHasNonPasswordAuth $endpoint.Info
        if(-not $password -and -not $nonPassword){
            Write-V7SocksEngineTrace 'CONFIG_CHECK' 'FAIL CREDENTIAL_REQUIRED'
            Write-Fail "SavedSession '$PuttySession': для автоматического VCC SOCKS $SocksPort не найден DPAPI пароль/.ppk/Pageant."
            return $false
        }
        Write-V7SocksEngineTrace 'CONFIG_CHECK' ("PASS saved-session-metadata source=$($endpoint.Source); host=$($endpoint.Host); port=$($endpoint.Port); credential=$(if($password){'password'}else{'key-or-agent'})")
        return $true
    }
    if(-not $VpsHost){Write-Fail 'Не указан Host/IP активного VPS.';return $false}
    if($VpsAuthMode -eq 'Password' -and -not(Get-EffectivePuttyPassword)){Write-Fail 'Не найден сохранённый DPAPI-пароль.';return $false}
    if($VpsAuthMode -eq 'PrivateKey' -and (-not $VpsKeyFile -or -not(Test-Path -LiteralPath $VpsKeyFile))){Write-Fail 'Не найден .ppk SSH-ключ.';return $false}
    if(@('Password','PrivateKey','Pageant') -notcontains $VpsAuthMode){Write-Fail "Неизвестный AuthMode: $VpsAuthMode";return $false}
    return $true
}
'@
$replacements['Start-PuttyTunnel'] = @'
function Test-V7RemoteTcpEndpoint([string]$RemoteHost,[int]$RemotePort,[int]$TimeoutMs=2500) {
    if(-not $RemoteHost -or $RemotePort -le 0){return $false}
    $client=New-Object Net.Sockets.TcpClient
    try{
        $ar=$client.BeginConnect($RemoteHost,$RemotePort,$null,$null)
        if(-not $ar.AsyncWaitHandle.WaitOne($TimeoutMs,$false)){return $false}
        $client.EndConnect($ar);return $client.Connected
    }catch{return $false}finally{try{$client.Close()}catch{}}
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
        Write-V7SocksEngineTrace 'HOSTKEY_TRUST' (
            "FAIL source=portable reason=NOT_FOUND host=$RemoteHost port=$RemotePort"
        )
        return $false
    }

    if (-not (Test-Path -LiteralPath $registryPath)) {
        try {
            New-Item -Path $registryPath -Force -ErrorAction Stop | Out-Null
        }
        catch {
            Write-V7SocksEngineTrace 'HOSTKEY_TRUST' (
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
                Write-V7SocksEngineTrace 'HOSTKEY_TRUST' (
                    "FAIL conflict=true name=$name host=$RemoteHost port=$RemotePort"
                )
                return $false
            }

            $existing++
            Write-V7SocksEngineTrace 'HOSTKEY_TRUST' (
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
            Write-V7SocksEngineTrace 'HOSTKEY_TRUST' (
                "PASS imported=true name=$name source=portable"
            )
        }
        catch {
            Write-V7SocksEngineTrace 'HOSTKEY_TRUST' (
                "FAIL import name=$name error=" + $_.Exception.Message
            )
            return $false
        }
    }

    Write-V7SocksEngineTrace 'HOSTKEY_TRUST' (
        "PASS host=$RemoteHost port=$RemotePort candidates=$($candidates.Count) imported=$imported existing=$existing"
    )

    return $true
}

function Get-V7ManagedPuttyExecutable {
    $launch=[string]$PuttyPath
    try{
        $leaf=[IO.Path]::GetFileName($launch)
        $dir=Split-Path -Parent $launch
        if($leaf -match '(?i)portable' -and $dir){
            $native=Join-Path $dir 'putty.exe'
            if(Test-Path -LiteralPath $native -PathType Leaf){return $native}
        }
    }catch{}
    return $launch
}
function Get-V7PuttyVersion([string]$Executable){
    $s=''
    try{$s=[string](Get-Item -LiteralPath $Executable -ErrorAction Stop).VersionInfo.ProductVersion}catch{}
    if(-not $s){try{$s=[string](Get-Item -LiteralPath $Executable -ErrorAction Stop).VersionInfo.FileVersion}catch{}}
    $m=[regex]::Match($s,'(\d+)\.(\d+)')
    if($m.Success){try{return [version]("$($m.Groups[1].Value).$($m.Groups[2].Value)")}catch{}}
    return $null
}
function Test-V7PuttyPwFileSupport([string]$Executable){
    $v=Get-V7PuttyVersion $Executable
    return ($v -and ($v.Major -gt 0 -or $v.Minor -ge 77))
}
function New-V7SecurePuttyPasswordFile([string]$Password){
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

    Write-V7SocksEngineTrace 'CREDENTIAL_FILE' 'created=true acl=creation-time/current-user+system inheritance=disabled storage=LOCALAPPDATA mode=PWFILE'
    return $path
}

function Remove-V7SecurePuttyPasswordFile {
    try{
        if($script:V7PuttyPasswordFile -and (Test-Path -LiteralPath $script:V7PuttyPasswordFile -PathType Leaf)){
            Remove-Item -LiteralPath $script:V7PuttyPasswordFile -Force -ErrorAction Stop
            Write-V7SocksEngineTrace 'CREDENTIAL_FILE' 'removed=true'
        }
    }catch{Write-V7SocksEngineTrace 'CREDENTIAL_FILE' ("remove-failed="+$_.Exception.Message)}
    finally{$script:V7PuttyPasswordFile=''}
}
function Start-PuttyTunnel {
    if(-not(Test-PuttyConfigured)){Write-V7SocksEngineTrace 'PUTTY_START' 'ABORT config-check-failed';return $false}
    $password=Get-EffectivePuttyPassword
    $effectiveHost=$VpsHost
    $effectivePort=[int]$VpsSshPort
    $effectiveKey=$VpsKeyFile
    $source='EXPLICIT_PROFILE'

    if($VpsAuthMode -eq 'SavedSession'){
        $endpoint=Get-V7SavedSessionEndpoint
        if(-not $endpoint){Write-V7SocksEngineTrace 'PUTTY_START' 'ABORT endpoint-unresolved';return $false}
        $effectiveHost=[string]$endpoint.Host
        $effectivePort=[int]$endpoint.Port
        try{$effectiveKey=[string]$endpoint.Info.PublicKeyFile}catch{}
        $source='SAVED_SESSION_METADATA'
    }

    $launchExe=Get-V7ManagedPuttyExecutable
    $portableRoot=Split-Path -Parent ([string]$PuttyPath)
    if(-not(Ensure-V7OfficialPuttyHostKeyTrust -PortableRoot $portableRoot -RemoteHost $effectiveHost -RemotePort $effectivePort)){
        Write-V7SocksEngineTrace 'PUTTY_START' 'ABORT hostkey-trust-not-proven'
        Write-Fail 'Не удалось подтвердить/перенести доверенный SSH host key активного VPS в официальный PuTTY store.'
        return $false
    }

    $arguments=@('-ssh','-P',([string]$effectivePort),'-D',("${SocksHost}:$SocksPort"),'-N','-l',$PuttyUser)
    Remove-V7SecurePuttyPasswordFile
    if($password){
        if(-not(Test-V7PuttyPwFileSupport $launchExe)){
            Write-V7SocksEngineTrace 'PUTTY_START' 'ABORT pwfile-unsupported'
            Write-Fail 'PuTTY 0.77+ требуется для безопасного -pwfile; plaintext -pw fallback запрещён.'
            $password=$null
            return $false
        }
        $script:V7PuttyPasswordFile=New-V7SecurePuttyPasswordFile $password
        $password=$null
        $arguments+=@('-pwfile',$script:V7PuttyPasswordFile)
        Write-V7SocksEngineTrace 'CREDENTIAL_FILE' 'created=true acl=current-user-only mode=PWFILE'
    }
    elseif($effectiveKey -and (Test-Path -LiteralPath $effectiveKey -PathType Leaf)){$arguments+=@('-i',$effectiveKey)}
    elseif(Get-Process -Name pageant -ErrorAction SilentlyContinue|Select-Object -First 1){$arguments+='-agent'}
    elseif($VpsAuthMode -eq 'Pageant'){$arguments+='-agent'}
    else{Write-V7SocksEngineTrace 'PUTTY_START' 'ABORT credential-disappeared';return $false}
    $arguments+=$effectiveHost

    try{
        $endpointOk=Test-V7RemoteTcpEndpoint -RemoteHost $effectiveHost -RemotePort $effectivePort -TimeoutMs 2500
        Write-V7SocksEngineTrace 'SSH_ENDPOINT' ("host=$effectiveHost; port=$effectivePort; tcpOpen=$endpointOk; source=$source")
        Write-V7SocksEngineTrace 'PUTTY_BINARY' ("exe=$launchExe; source=$source; guiPuttyBatch=false; pwfileSupported=$(Test-V7PuttyPwFileSupport $launchExe)")
        $safeArgs=Convert-V7SafeArgumentSummary -Items $arguments
        Write-V7SocksEngineTrace 'PUTTY_START' ("transport=PuTTY; exe=$launchExe; source=$source; vccSocks=${SocksHost}:$SocksPort; guiPuttyBatch=false; args=$safeArgs")
        $proc=Start-Process -FilePath $launchExe -ArgumentList (Convert-ToProcessArgumentString -Items $arguments) -WindowStyle Minimized -PassThru
        Write-V7SocksEngineTrace 'PUTTY_PROCESS' ("started pid=$($proc.Id); vccSocksPort=$SocksPort")
        Start-Sleep -Milliseconds 900
        try{
            $proc.Refresh()
            if($proc.HasExited){Write-V7SocksEngineTrace 'PUTTY_PROCESS' ("exited-early pid=$($proc.Id) exitCode=$($proc.ExitCode)")}
            else{Write-V7SocksEngineTrace 'PUTTY_PROCESS' ("alive-after-900ms pid=$($proc.Id)")}
        }catch{}
        try{$proc.Dispose()}catch{}
        return $true
    }catch{
        Remove-V7SecurePuttyPasswordFile
        Write-V7SocksEngineTrace 'PUTTY_START' ("FAIL error="+$_.Exception.Message)
        Write-Fail "Не удалось запустить VCC SOCKS ${SocksPort}: $($_.Exception.Message)"
        return $false
    }
}
'@

$replacements['Stop-TunnelProcess'] = @'
function Stop-TunnelProcess([switch]$Quiet) {
    $mutationMutex=$null
    $mutationLockAcquired=$false
    try {
        $mutationMutex=New-Object Threading.Mutex($false,$VccSocksMutationMutexName)
        try {
            $mutationLockAcquired=$mutationMutex.WaitOne([TimeSpan]::FromSeconds(60))
        } catch [Threading.AbandonedMutexException] {
            $mutationLockAcquired=$true
            Write-V7SocksEngineTrace 'MUTATION_LOCK' 'stop acquired=ABANDONED'
        }

        if(-not $mutationLockAcquired){
            Write-V7SocksEngineTrace 'MUTATION_LOCK' 'stop acquired=false timeoutSec=60'
            if(-not $Quiet){Write-Fail "VCC SOCKS $SocksPort mutation lock timeout."}
            return $false
        }

        Write-V7SocksEngineTrace 'MUTATION_LOCK' ("stop acquired=true ownerProcess=$PID mutex=$VccSocksMutationMutexName")

        $conn=Get-NetTCPConnection -LocalAddress $SocksHost -LocalPort $SocksPort -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1
        if(-not $conn){
            Write-V7SocksEngineTrace 'STOP_VCC_SOCKS' "no-listener ${SocksHost}:$SocksPort"
            return $true
        }

        $listenerPid=[int]$conn.OwningProcess
        $proc=Get-CimInstance Win32_Process -Filter ("ProcessId="+$listenerPid) -ErrorAction SilentlyContinue
        if(-not $proc){
            Write-V7SocksEngineTrace 'STOP_VCC_SOCKS' "FAIL owner-unknown pid=$listenerPid"
            return $false
        }

        $name=[string]$proc.Name
        $cmd=[string]$proc.CommandLine
        $allowed=($name -match '(?i)^(putty|putty_portable|plink)\.exe$')
        $managed=($cmd -match ("(?i)(^|\s)-D\s+"+[regex]::Escape("${SocksHost}:$SocksPort")+"(\s|$)"))

        if(-not $allowed -or -not $managed){
            Write-V7SocksEngineTrace 'STOP_VCC_SOCKS' ("FAIL ownership pid=$listenerPid name=$name managed=$managed")
            if(-not $Quiet){Write-Fail "Порт $SocksPort занят process PID=$listenerPid, не доказанным как VCC-managed tunnel. Process не остановлен."}
            return $false
        }

        Stop-Process -Id $listenerPid -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 250

        $still=Get-NetTCPConnection -LocalAddress $SocksHost -LocalPort $SocksPort -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1
        if($still){
            Write-V7SocksEngineTrace 'STOP_VCC_SOCKS' "FAIL still-listening pid=$listenerPid"
            return $false
        }

        Write-V7SocksEngineTrace 'STOP_VCC_SOCKS' ("PASS pid=$listenerPid port=$SocksPort")
        if(-not $Quiet){Write-Ok "VCC SOCKS $SocksPort остановлен."}
        return $true
    } catch {
        Write-V7SocksEngineTrace 'STOP_VCC_SOCKS' ("FAIL error="+$_.Exception.Message)
        if(-not $Quiet){Write-Fail "Не удалось остановить VCC SOCKS ${SocksPort}: $($_.Exception.Message)"}
        return $false
    } finally {
        if($mutationLockAcquired -and $mutationMutex){
            try{$mutationMutex.ReleaseMutex()}catch{}
        }
        if($mutationMutex){try{$mutationMutex.Dispose()}catch{}}
    }
}
'@

$replacements['Ensure-SocksTunnel'] = @'
function Ensure-SocksTunnel([switch]$Quiet) {
    $mutationMutex=$null
    $mutationLockAcquired=$false

    try {
        $mutationMutex=New-Object Threading.Mutex($false,$VccSocksMutationMutexName)

        try {
            $mutationLockAcquired=$mutationMutex.WaitOne([TimeSpan]::FromSeconds(60))
        } catch [Threading.AbandonedMutexException] {
            $mutationLockAcquired=$true
            Write-V7SocksEngineTrace 'MUTATION_LOCK' 'ensure acquired=ABANDONED'
        }

        if(-not $mutationLockAcquired){
            Write-V7SocksEngineTrace 'MUTATION_LOCK' 'ensure acquired=false timeoutSec=60'
            if(-not $Quiet){Write-Fail "VCC SOCKS $SocksPort mutation lock timeout."}
            return $false
        }

        Write-V7SocksEngineTrace 'MUTATION_LOCK' ("ensure acquired=true ownerProcess=$PID mutex=$VccSocksMutationMutexName")
        Write-V7SocksEngineTrace 'ENSURE_BEGIN' ("quiet=$Quiet; socks=${SocksHost}:$SocksPort; expectedIp=$ExpectedVpsIp; waitSeconds=$TunnelWaitSeconds")

        # Critical re-check INSIDE the cross-process lock. If another process
        # repaired 1081 while this caller was waiting, do not start a duplicate.
        if(Test-SocksIdentity){
            Write-V7SocksEngineTrace 'ENSURE_RESULT' 'already-healthy=true'
            if(-not $Quiet){Write-Ok "SOCKS5 ${SocksHost}:$SocksPort уже работает через $ExpectedVpsIp."}
            return $true
        }

        $portBefore=Test-TcpPort $SocksHost $SocksPort
        Write-V7SocksEngineTrace 'ENSURE_PRE' ("portBefore=$portBefore")

        if($portBefore){
            if(-not $Quiet){Write-Warn "Порт $SocksPort открыт, но expected VPS identity не подтверждена."}

            # We already own the named mutex. Windows mutexes are recursive for
            # the owning thread; Stop-TunnelProcess acquires/releases one nested
            # ownership level and therefore remains safe for outside callers too.
            $stopOk=Stop-TunnelProcess -Quiet
            Write-V7SocksEngineTrace 'ENSURE_PRE' ("stale-listener-stop=$stopOk")

            if(-not $stopOk){
                Write-V7SocksEngineTrace 'ENSURE_RESULT' 'FAIL stale-listener-stop=false'
                return $false
            }

            Start-Sleep -Seconds 1

            # Another identity check avoids unnecessary restart if state changed.
            if(Test-SocksIdentity){
                Write-V7SocksEngineTrace 'ENSURE_RESULT' 'healthy-after-stop-phase=true'
                return $true
            }
        }

        if(-not $Quiet){Write-Host 'Запускаю ExampleVPS через PuTTY...'}

        $startOk=Start-PuttyTunnel
        Write-V7SocksEngineTrace 'ENSURE_START' ("StartPuttyTunnel=$startOk")

        if(-not $startOk){
            Write-V7SocksEngineTrace 'ENSURE_RESULT' 'FAIL start-putty=false'
            return $false
        }

        $deadline=(Get-Date).AddSeconds($TunnelWaitSeconds)
        $nextTrace=Get-Date

        while((Get-Date) -lt $deadline){
            if(Test-SocksIdentity){
                Write-V7SocksEngineTrace 'ENSURE_RESULT' ("PASS listener=true identity=$ExpectedVpsIp")
                if(-not $Quiet){Write-Ok "SOCKS5 поднят; VPS exit=$ExpectedVpsIp."}
                return $true
            }

            if((Get-Date) -ge $nextTrace){
                $listener=Get-SocksListenerProcess
                $listenerText=if($listener){"pid=$($listener.ProcessId);name=$($listener.Name)"}else{'none'}
                $puttyPids=@(
                    Get-Process -Name putty,putty_portable,plink -ErrorAction SilentlyContinue |
                    ForEach-Object{"$($_.ProcessName):$($_.Id)"}
                ) -join ','

                Write-V7SocksEngineTrace 'ENSURE_WAIT' (
                    "remainingSec=$([int][Math]::Max(0,($deadline-(Get-Date)).TotalSeconds)); "+
                    "port=$(Test-TcpPort $SocksHost $SocksPort 250); "+
                    "listener=$listenerText; "+
                    "puttyProcesses=$(if($puttyPids){$puttyPids}else{'none'})"
                )

                $nextTrace=(Get-Date).AddSeconds(3)
            }

            Start-Sleep -Milliseconds 900
        }

        Write-V7SocksEngineTrace 'ENSURE_RESULT' ("FAIL timeout=${TunnelWaitSeconds}s; finalPort=$(Test-TcpPort $SocksHost $SocksPort 250)")
        if(-not $Quiet){Write-Fail "Expected SOCKS/VPS не появился за $TunnelWaitSeconds секунд."}
        return $false
    } finally {
        Remove-V7SecurePuttyPasswordFile
        if($mutationLockAcquired -and $mutationMutex){
            try{$mutationMutex.ReleaseMutex()}catch{}
        }
        if($mutationMutex){try{$mutationMutex.Dispose()}catch{}}
    }
}
'@

$replacements['Invoke-ProxifierRawLoad'] = @'
function Invoke-ProxifierRawLoad(
    [string]$ProxifierPath,
    [string]$ProfileFile
) {
    $loaderProcess = $null

    try {
        # Snapshot only Standard Proxifier instances that existed before this
        # profile-load request. If at least one survives, a newly spawned
        # silent-load process is only a transient command helper.
        $primaryBefore = @(
            Get-CimInstance Win32_Process `
                -Filter "Name='Proxifier.exe'" `
                -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ExecutablePath -and
                ([string]$_.ExecutablePath -ieq $ProxifierPath) -and
                (([string]$_.CommandLine) -notmatch '(?i)\bsilent-load\b')
            } |
            Select-Object -ExpandProperty ProcessId
        )

        $args = @($ProfileFile, 'silent-load')
        $loaderProcess = Start-Process `
            -FilePath $ProxifierPath `
            -ArgumentList (Convert-ToProcessArgumentString -Items $args) `
            -PassThru

        $loaderPid = [int]$loaderProcess.Id
        Write-ControllerLog "PROXIFIER_LOAD_REQUEST pid=$loaderPid parent=$PID primaryBefore=$($primaryBefore.Count) profile=$ProfileFile"

        # A helper should normally hand the profile to the already-running
        # Standard instance and exit quickly. Bound the wait so the watchdog
        # can never hang on a modal/helper process.
        $exited = $false
        try { $exited = $loaderProcess.WaitForExit(3500) } catch { $exited = $false }

        if ($exited) {
            $exitCode = $null
            try { $exitCode = [int]$loaderProcess.ExitCode } catch { }

            Write-ControllerLog "PROXIFIER_LOAD_HELPER_EXIT pid=$loaderPid exitCode=$exitCode"

            if ($null -ne $exitCode -and $exitCode -ne 0) {
                Write-ControllerLog "PROXIFIER_LOAD_HELPER_NONZERO pid=$loaderPid exitCode=$exitCode"
                return $false
            }

            return $true
        }

        # Cold start is deliberately fail-safe: without a pre-existing primary,
        # the spawned process may itself become the primary Proxifier instance.
        if ($primaryBefore.Count -eq 0) {
            Write-ControllerLog "PROXIFIER_LOAD_HELPER_RETAIN pid=$loaderPid primaryBefore=0 reason=cold-start"
            return $true
        }

        $primaryStillAlive = $false
        foreach ($primaryPid in @($primaryBefore)) {
            try {
                $primaryInfo = Get-CimInstance Win32_Process `
                    -Filter "ProcessId=$primaryPid" `
                    -ErrorAction SilentlyContinue

                if (
                    $primaryInfo -and
                    $primaryInfo.ExecutablePath -and
                    ([string]$primaryInfo.ExecutablePath -ieq $ProxifierPath) -and
                    (([string]$primaryInfo.CommandLine) -notmatch '(?i)\bsilent-load\b')
                ) {
                    $primaryStillAlive = $true
                    break
                }
            }
            catch { }
        }

        $loaderInfo = $null
        try {
            $loaderInfo = Get-CimInstance Win32_Process `
                -Filter "ProcessId=$loaderPid" `
                -ErrorAction SilentlyContinue
        }
        catch { }

        $ownedHelper = $false
        if ($loaderInfo) {
            $loaderCmd = [string]$loaderInfo.CommandLine
            $ownedHelper = (
                [int]$loaderInfo.ParentProcessId -eq $PID -and
                $loaderInfo.ExecutablePath -and
                ([string]$loaderInfo.ExecutablePath -ieq $ProxifierPath) -and
                $loaderCmd -match '(?i)\bsilent-load\b'
            )
        }

        if (-not $primaryStillAlive -or -not $ownedHelper) {
            Write-ControllerLog "PROXIFIER_LOAD_HELPER_RETAIN pid=$loaderPid owned=$ownedHelper primaryStillAlive=$primaryStillAlive reason=fail-closed"
            return $false
        }

        try {
            Stop-Process -Id $loaderPid -Force -ErrorAction Stop
            Start-Sleep -Milliseconds 150

            $stillRunning = Get-CimInstance Win32_Process `
                -Filter "ProcessId=$loaderPid" `
                -ErrorAction SilentlyContinue

            if ($stillRunning) {
                Write-ControllerLog "PROXIFIER_LOAD_HELPER_STUCK_CLEANUP_FAILED pid=$loaderPid reason=still-running"
                return $false
            }

            Write-ControllerLog "PROXIFIER_LOAD_HELPER_STUCK_CLEANUP pid=$loaderPid parent=$PID primaryStillAlive=true timeoutMs=3500"
            return $true
        }
        catch {
            Write-ControllerLog "PROXIFIER_LOAD_HELPER_STUCK_CLEANUP_FAILED pid=$loaderPid error=$($_.Exception.Message)"
            return $false
        }
    }
    catch {
        Write-ControllerLog "PROXIFIER raw load failed: $($_.Exception.Message)"
        return $false
    }
    finally {
        if ($loaderProcess) {
            try { $loaderProcess.Dispose() } catch { }
        }
    }
}
'@

$replacements['New-ProxifierProfile'] = @'
function Get-V7RoutingTunnelSelection {
    $path=Join-Path $VpsProfileRoot 'runtime\tunnel-routing.json'
    $id='PRIMARY_AUTO'
    try{
        if(Test-Path -LiteralPath $path -PathType Leaf){
            $d=Get-Content -LiteralPath $path -Raw -ErrorAction Stop|ConvertFrom-Json
            if([string]$d.SelectedTunnelId -in @('PRIMARY_AUTO','RESERVE_MANUAL')){$id=[string]$d.SelectedTunnelId}
        }
    }catch{}
    return $id
}
function Get-V7SocksExternalIpForPort([int]$Port){
    try{
        $curl=Get-Command curl.exe -ErrorAction SilentlyContinue
        if(-not$curl){return ''}
        $r=Invoke-CurlSimple -Executable $curl.Source -Arguments @('--silent','--show-error','--max-time','12','--proxy',("socks5h://127.0.0.1:"+$Port),'https://ifconfig.me')
        if($r.ExitCode -ne 0 -or -not$r.StdOut){return ''}
        return (([string]($r.StdOut|Select-Object -First 1)).Trim())
    }catch{return ''}
}
function Get-V7RoutingProxyId {
    $id=Get-V7RoutingTunnelSelection
    if($id -eq 'RESERVE_MANUAL'){
        $ip=Get-V7SocksExternalIpForPort 1080
        if(-not$ip -or $ip -ne $ExpectedVpsIp){
            throw "RESERVE_MANUAL 1080 selected for VPS routing, but expected VPS identity is not healthy. VCC will not auto-start or auto-recover 1080."
        }
        return 101
    }
    return 100
}
function New-ProxifierProfile($Routes, [string]$DestinationPath) {
    # RC14.15: Proxifier application-list grammar is strict: semicolon separators have no surrounding blanks; whitespace-containing filenames are quoted.
    $r = Normalize-Routes $Routes
    $hasVps = Test-AnyEffectiveVps $r
    $routeProxyId=$(if($hasVps){Get-V7RoutingProxyId}else{100})
    $rules = New-Object System.Collections.Generic.List[string]

    [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>Localhost DIRECT</Name>
      <Targets>localhost; 127.0.0.1; ::1; %ComputerName%</Targets>
      <Action type="Direct" />
    </Rule>
"@)
    [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>Tunnel infrastructure DIRECT</Name>
      <Applications>putty.exe;putty_portable.exe;plink.exe;proxifier.exe</Applications>
      <Action type="Direct" />
    </Rule>
"@)
    [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>VPS Control direct probe DIRECT</Name>
      <Applications>vps-control-direct-probe.exe</Applications>
      <Action type="Direct" />
    </Rule>
"@)

    if ($hasVps) {
        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>VPS Control route verification</Name>
      <Applications>vps-control-vps-probe.exe</Applications>
      <Action type="Proxy">$routeProxyId</Action>
    </Rule>
"@)
    }
    else {
        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>VPS Control route verification DIRECT</Name>
      <Applications>vps-control-vps-probe.exe</Applications>
      <Action type="Direct" />
    </Rule>
"@)
    }

    foreach ($module in $ModuleNames) {
        if ([string]$r.$module -ne 'VPS') { continue }
        $entry = Get-ModuleCatalogEntry $module
        $safeName = [System.Security.SecurityElement]::Escape([string]$module)
        $apps = @($entry.Applications | Where-Object { $_ })
        $targets = @($entry.Targets | Where-Object { $_ })
        if ($apps.Count -gt 0) {
            $appsText = (($apps | ForEach-Object {
                $appToken = ([string]$_).Trim()
                if (-not $appToken) { return }
                if ($appToken -match '[;\r\n]') {
                    throw "Invalid Proxifier application token: delimiter/newline is not allowed."
                }
                if ($appToken -match '\s') {
                    if (-not ($appToken.StartsWith('"') -and $appToken.EndsWith('"'))) {
                        $appToken = '"' + $appToken.Replace('"','') + '"'
                    }
                }

                # Proxifier's Applications grammar requires literal double quotes
                # around filenames containing spaces. XML element text does not
                # require quote escaping, so escape only the three characters
                # that are special in text nodes and preserve literal `"`.
                $appToken = $appToken.Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;')
                $appToken
            }) -join ';')
            [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>MODULE $safeName applications VPS</Name>
      <Applications>$appsText</Applications>
      <Action type="Proxy">$routeProxyId</Action>
    </Rule>
"@)
        }
        if ($targets.Count -gt 0) {
            $targetsText = (($targets | ForEach-Object { [System.Security.SecurityElement]::Escape([string]$_) }) -join '; ')
            [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>MODULE $safeName destinations VPS</Name>
      <Targets>$targetsText</Targets>
      <Action type="Proxy">$routeProxyId</Action>
    </Rule>
"@)
        }
    }

    [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>Default DIRECT</Name>
      <Action type="Direct" />
    </Rule>
"@)

    if ($hasVps) {
        $proxyXml = @"
  <ProxyList>
    <Proxy id="100" type="SOCKS5">
      <Address>127.0.0.1</Address>
      <Port>1081</Port>
      <Options>48</Options>
    </Proxy>
    <Proxy id="101" type="SOCKS5">
      <Address>127.0.0.1</Address>
      <Port>1080</Port>
      <Options>48</Options>
    </Proxy>
  </ProxyList>
"@
    }
    else { $proxyXml = '  <ProxyList />' }

    $ruleXml = $rules -join "`n"
    $xml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ProxifierProfile version="101" platform="Windows" product_id="0" product_minver="310">
  <Options>
    <Resolve>
      <AutoModeDetection enabled="true" />
      <ViaProxy enabled="false">
        <TryLocalDnsFirst enabled="false" />
      </ViaProxy>
      <ExclusionList>%ComputerName%; localhost; *.local</ExclusionList>
    </Resolve>
    <Encryption mode="basic" />
    <HttpProxiesSupport enabled="false" />
    <HandleDirectConnections enabled="false" />
    <ConnectionLoopDetection enabled="true" />
    <ProcessServices enabled="true" />
    <ProcessOtherUsers enabled="false" />
  </Options>

$proxyXml

  <ChainList />

  <RuleList>
$ruleXml
  </RuleList>
</ProxifierProfile>
"@

    Write-TextAtomic -Path $DestinationPath -Text $xml
    return $DestinationPath
}
'@

$functions = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
$edits = New-Object System.Collections.ArrayList
foreach ($name in $replacements.Keys) {
    $fn = @($functions | Where-Object { $_.Name -eq $name })
    if ($fn.Count -ne 1) { Fail "Не найдено однозначное определение функции $name (count=$($fn.Count))." }
    [void]$edits.Add([pscustomobject]@{
        Start = $fn[0].Extent.StartOffset
        End = $fn[0].Extent.EndOffset
        Text = [string]$replacements[$name]
    })
}

$out = $raw
foreach ($edit in @($edits | Sort-Object Start -Descending)) {
    $out = $out.Substring(0, [int]$edit.Start) + $edit.Text + $out.Substring([int]$edit.End)
}


$out = $out -replace '(?m)^\$SocksHost\s*=\s*''[^'']+''\s*$', "`$SocksHost = '127.0.0.1'"
$out = $out -replace '(?m)^\$SocksPort\s*=\s*\d+\s*$', "`$SocksPort = 1081"
$out = $out -replace '(?m)^\$SocksPort\s*=\s*1081\s*$', "`$SocksPort = 1081`r`n`$VccSocksMutationMutexName = 'Local\VPSControl-VCC-SOCKS-1081'"

$out = $out -replace '(?m)^\$ControllerVersion\s*=\s*''6\.3\.1''\s*$', "`$ControllerVersion = '6.5'"
$out = $out -replace '(?m)^\$ModuleNames\s*=\s*@\(''OpenAI'',\s*''GitHub'',\s*''DevPackages'',\s*''Firefox''\)\s*$', "`$ModuleNames = @('OpenAI','GitHub','DevPackages','Firefox','Claude','Gemini','Docker','Telegram','YandexBrowser','Edge','CustomExe','CustomSite')`r`n`$ModuleDefaultModes = @{ OpenAI='VPS'; GitHub='AUTO'; DevPackages='AUTO'; Firefox='DIRECT'; Claude='AUTO'; Gemini='AUTO'; Docker='AUTO'; Telegram='AUTO'; YandexBrowser='DIRECT'; Edge='DIRECT'; CustomExe='DIRECT'; CustomSite='DIRECT' }"
$out = $out -replace '(?m)^\$BundledModulesFile\s*=\s*Join-Path\s+\$PSScriptRoot\s+''VPS-Control-v6\.3\.1-modules\.json''\s*$', "`$BundledModulesFile = Join-Path `$PSScriptRoot 'VPS-Control-v6.5-modules.json'"

$out = $out -replace '(?m)^\$ReusePasswordFromSiblingV6\s*=\s*\$true\s*$', @'
$ReusePasswordFromSiblingV6 = $true
$V7LegacyPuttyPath = [string]$PuttyPath
$V7PuttyDiscoverySource = 'legacy-config'
$V7PuttyDiscoveryCandidates = @(
    (Join-Path $PSScriptRoot 'PuTTY PORTABLE\putty_portable.exe'),
    (Join-Path $PSScriptRoot 'PuTTY PORTABLE\putty.exe'),
    (Join-Path $PSScriptRoot 'putty_portable.exe'),
    (Join-Path $PSScriptRoot 'putty.exe'),
    $V7LegacyPuttyPath
)
foreach($candidate in @($V7PuttyDiscoveryCandidates)){
    try{if($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)){$PuttyPath=[string]$candidate;$V7PuttyDiscoverySource=$(if($candidate -eq $V7LegacyPuttyPath){'legacy-config'}else{'colocated'});break}}catch{}
}
$VpsProfileRoot = Join-Path $PSScriptRoot 'VPS-Control-Data'
$VpsDataPointer = Join-Path $PSScriptRoot 'VPS-Control-Data.location'
try {
    if (Test-Path -LiteralPath $VpsDataPointer) {
        $candidate = [Environment]::ExpandEnvironmentVariables(([IO.File]::ReadAllText($VpsDataPointer,[Text.Encoding]::UTF8)).Trim())
        if ($candidate) { if (-not [IO.Path]::IsPathRooted($candidate)) { $candidate = Join-Path $PSScriptRoot $candidate }; $VpsProfileRoot = [IO.Path]::GetFullPath($candidate) }
    }
} catch { }
$VpsActiveProfileFile = Join-Path $VpsProfileRoot 'nodes\vps\active-vps.json'
$VpsSecretsDir = Join-Path $VpsProfileRoot 'secrets\vps'
$VpsHost = ''
$VpsSshPort = 22
$VpsAuthMode = 'SavedSession'
$VpsSecretId = ''
$VpsKeyFile = ''
$V7SocksTraceFile = Join-Path $VpsProfileRoot 'logs\socks-engine.log'
function Write-V7SocksEngineTrace([string]$Phase,[string]$Message='') {
    try {
        $dir=Split-Path -Parent $V7SocksTraceFile;if($dir -and -not(Test-Path -LiteralPath $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
        $safe=[string]$Message
        $safe=[regex]::Replace($safe,'(?i)(-pw\s+)("[^"]*"|\S+)','$1<redacted>')
        $safe=[regex]::Replace($safe,'(?i)(password\s*[=:]\s*)("[^"]*"|\S+)','$1<redacted>')
        if(Test-Path -LiteralPath $V7SocksTraceFile -PathType Leaf){
            try{$tf=Get-Item -LiteralPath $V7SocksTraceFile -ErrorAction Stop;if($tf.Length -gt 2MB){Move-Item -LiteralPath $V7SocksTraceFile -Destination ($V7SocksTraceFile+'.1') -Force -ErrorAction SilentlyContinue}}catch{}
        }
        Add-Content -LiteralPath $V7SocksTraceFile -Value ('{0:yyyy-MM-dd HH:mm:ss.fff}  [{1}]  {2}' -f (Get-Date),$Phase,$safe) -Encoding UTF8
    } catch { }
}
Write-V7SocksEngineTrace 'PUTTY_DISCOVERY' ("selected=$PuttyPath; source=$V7PuttyDiscoverySource; legacy=$V7LegacyPuttyPath; localCandidate="+(Join-Path $PSScriptRoot 'PuTTY PORTABLE\putty_portable.exe'))
function Convert-V7SafeArgumentSummary([object[]]$Items){
    $out=New-Object Collections.ArrayList;$redactNext=$false
    foreach($item in @($Items)){
        $v=[string]$item
        if($redactNext){[void]$out.Add('<redacted>');$redactNext=$false;continue}
        [void]$out.Add($v)
        if($v -in @('-pw','-pwfile')){$redactNext=$true}
    }
    return (@($out)-join ' ')
}
try {
    if (Test-Path -LiteralPath $VpsActiveProfileFile) {
        $activeVps = Get-Content -LiteralPath $VpsActiveProfileFile -Raw -ErrorAction Stop | ConvertFrom-Json
        if ($activeVps.Host) { $VpsHost = [string]$activeVps.Host }
        if ($activeVps.SshPort) { $VpsSshPort = [int]$activeVps.SshPort }
        if ($activeVps.User) { $PuttyUser = [string]$activeVps.User }
        if ($activeVps.ExpectedExitIp) { $ExpectedVpsIp = [string]$activeVps.ExpectedExitIp }
        if ($activeVps.AuthMode) { $VpsAuthMode = [string]$activeVps.AuthMode }
        if ($activeVps.SavedSession) { $PuttySession = [string]$activeVps.SavedSession }
        if ($activeVps.KeyFile) { $VpsKeyFile = [string]$activeVps.KeyFile }
        if ($activeVps.SecretId) { $VpsSecretId = [string]$activeVps.SecretId }
    }
} catch { }
'@
$out = $out.Replace('VPS-Control-v6\.3(?:\.1)?\.ps1', 'VPS-Control-v6\.(?:3(?:\.1)?|4|5)\.ps1')
$out = $out -replace 'VPS CONTROL CENTER - VERSION 6\.3\.1 OBSERVABILITY / SELF-TEST HOTFIX', 'VPS CONTROL CENTER - VERSION 6.5 MULTI-VPS / EXTENSIBLE ROUTING'
$out = $out -replace 'VPS-Control-v6\.3\.1\.ps1', 'VPS-Control-v6.5.ps1'

$tokens2 = $null
$errors2 = $null
[void][System.Management.Automation.Language.Parser]::ParseInput($out, [ref]$tokens2, [ref]$errors2)
if ($errors2 -and $errors2.Count -gt 0) {
    Fail ("Сгенерированный V6.5 не прошёл PowerShell AST parse: " + (($errors2 | ForEach-Object Message) -join '; '))
}

$encoding = New-Object System.Text.UTF8Encoding($true)
[IO.File]::WriteAllText($DestinationPath, $out, $encoding)
Write-Output "OK: $DestinationPath"
exit 0
