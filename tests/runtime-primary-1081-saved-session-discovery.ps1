#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$RepoRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Generator=Join-Path $RepoRoot 'src\windows-v7\VPS-Control-v7-engine-upgrade.ps1'
$raw=Get-Content -LiteralPath $Generator -Raw -ErrorAction Stop

$tokens=$null;$parseErrors=$null
[void][Management.Automation.Language.Parser]::ParseFile($Generator,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw ('generator parse failed: '+(($parseErrors|ForEach-Object Message)-join '; '))}

$match=[regex]::Match($raw,"(?s)\$replacements\['Test-PuttyConfigured'\]\s*=\s*@'\r?\n(.*?)\r?\n'@")
if(-not $match.Success){throw 'Test-PuttyConfigured replacement body not found'}
Invoke-Expression $match.Groups[1].Value

function Write-V7SocksEngineTrace { param([string]$Phase,[string]$Message) $script:Trace += [pscustomobject]@{Phase=$Phase;Message=$Message} }
function Write-Fail { param([string]$Message) $script:Failures += $Message }
function Get-SavedPuttySessionInfo { return $null }

$script:Listeners=@()
$script:ProcessMap=@{}
$script:ObserverCalls=0
function Get-NetTCPConnection {
    param([string]$State,[int]$LocalPort,[string]$ErrorAction)
    $script:ObserverCalls++
    if($LocalPort -ne 1080){return @()}
    return @($script:Listeners)
}
function Get-CimInstance {
    param([string]$ClassName,[string]$Filter,[string]$ErrorAction)
    $pidText=([regex]::Match($Filter,'ProcessId=(\d+)')).Groups[1].Value
    if(-not $pidText){throw 'unexpected CIM filter'}
    $processId=[int]$pidText
    if(-not $script:ProcessMap.ContainsKey($processId)){throw 'process fixture missing'}
    return $script:ProcessMap[$processId]
}

function Assert([bool]$Condition,[string]$Message){if(-not $Condition){throw "ASSERT: $Message"}}
function New-PortableBackend([string]$Root,[string]$Host,[int]$Port=22,[string]$Protocol='ssh'){
    New-Item -ItemType Directory -Path (Join-Path $Root 'Sessions') -Force|Out-Null
    $exe=Join-Path $Root 'putty_portable.exe'
    [IO.File]::WriteAllBytes($exe,[byte[]](1,2,3))
    if($Host){
        $session=Join-Path (Join-Path $Root 'Sessions') 'AdminVPS'
        $text="HostName\$Host\`r`nPortNumber\$Port\`r`nProtocol\$Protocol\`r`n"
        [IO.File]::WriteAllText($session,$text,(New-Object Text.UTF8Encoding($false)))
    }
    return $exe
}
function Reset-Fixture {
    $script:Trace=@();$script:Failures=@();$script:Listeners=@();$script:ProcessMap=@{};$script:ObserverCalls=0
    $script:PuttySession='AdminVPS'
    $script:V7PuttyDiscoverySource='test'
}
function Add-Observed1080([int]$ProcessId,[string]$Exe){
    $script:Listeners += [pscustomobject]@{OwningProcess=$ProcessId;LocalPort=1080;State='Listen'}
    $script:ProcessMap[$ProcessId]=[pscustomobject]@{ProcessId=$ProcessId;Name=[IO.Path]::GetFileName($Exe);ExecutablePath=$Exe}
}

$temp=Join-Path $env:RUNNER_TEMP ('pncc-wu218-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp -Force|Out-Null
try{
    # Case 1: stale configured backend + exactly one readable observed 1080 backend.
    Reset-Fixture
    $staleDir=Join-Path $temp 'case1-stale-portable';$fallbackDir=Join-Path $temp 'case1-fallback-portable'
    $script:PuttyPath=New-PortableBackend $staleDir ''
    $fallbackExe=New-PortableBackend $fallbackDir '89.125.63.46' 22 'ssh'
    Add-Observed1080 101 $fallbackExe
    $endpoint=Get-V7SavedSessionEndpoint
    Assert ($null-ne$endpoint) 'stale configured path should resolve one observed fallback'
    Assert ([string]$endpoint.Source -eq 'PORTABLE_RESERVE_1080_OBSERVED') 'fallback source marker'
    Assert ([string]$endpoint.Host -eq '89.125.63.46') 'fallback HostName'
    Assert ([int]$endpoint.Port -eq 22) 'fallback PortNumber'
    Assert ([string]$endpoint.Protocol -eq 'ssh') 'fallback Protocol'
    Assert ([string]$script:PuttyPath -eq $fallbackExe) 'selected fallback must replace runtime PuttyPath'

    # Case 2: configured backend is valid; observed 1080 must not be consulted.
    Reset-Fixture
    $configuredDir=Join-Path $temp 'case2-configured-portable';$otherDir=Join-Path $temp 'case2-other-portable'
    $configuredExe=New-PortableBackend $configuredDir '89.125.63.46' 22 'ssh'
    $otherExe=New-PortableBackend $otherDir '203.0.113.10' 22 'ssh'
    $script:PuttyPath=$configuredExe
    Add-Observed1080 201 $otherExe
    $endpoint=Get-V7SavedSessionEndpoint
    Assert ($null-ne$endpoint) 'valid configured backend should resolve'
    Assert ([string]$endpoint.Source -eq 'PORTABLE_CONFIGURED') 'configured source must win'
    Assert ([string]$script:PuttyPath -eq $configuredExe) 'configured PuttyPath must remain selected'
    Assert ($script:ObserverCalls -eq 0) '1080 observer must not run when configured endpoint is valid'

    # Case 3: configured backend invalid and no 1080 listener -> fail closed.
    Reset-Fixture
    $case3Dir=Join-Path $temp 'case3-stale-portable'
    $case3Exe=New-PortableBackend $case3Dir ''
    $script:PuttyPath=$case3Exe
    $endpoint=Get-V7SavedSessionEndpoint
    Assert ($null-eq$endpoint) 'no fallback must fail closed'
    Assert ([string]$script:PuttyPath -eq $case3Exe) 'failed resolution must not mutate PuttyPath'

    # Case 4: two observed fallback backends with conflicting endpoints -> fail closed ambiguous.
    Reset-Fixture
    $case4Dir=Join-Path $temp 'case4-stale-portable'
    $case4Exe=New-PortableBackend $case4Dir ''
    $fallbackA=New-PortableBackend (Join-Path $temp 'case4-a-portable') '89.125.63.46' 22 'ssh'
    $fallbackB=New-PortableBackend (Join-Path $temp 'case4-b-portable') '203.0.113.20' 22 'ssh'
    $script:PuttyPath=$case4Exe
    Add-Observed1080 301 $fallbackA
    Add-Observed1080 302 $fallbackB
    $endpoint=Get-V7SavedSessionEndpoint
    Assert ($null-eq$endpoint) 'multiple fallback candidates must fail closed'
    Assert ([string]$script:PuttyPath -eq $case4Exe) 'ambiguous resolution must not mutate PuttyPath'
    Assert (@($script:Trace|Where-Object{$_.Message -like '*result=AMBIGUOUS*'}).Count -gt 0) 'ambiguity trace required'

    # Static least-authority/security contract.
    $observer=[regex]::Match($raw,'(?s)function Get-V7ObservedReservePuttyExecutableCandidates \{.*?\n\}').Value
    Assert ([bool]$observer) 'observer helper exists'
    Assert (-not($observer -match '(?i)CommandLine')) 'observer must not read process CommandLine'
    Assert (-not($observer -match '(?i)Stop-Process|Start-Process|Restart|\.Kill\(')) 'observer must not mutate 1080 lifecycle'
    Assert ($observer -match 'Get-NetTCPConnection -State Listen -LocalPort 1080') 'observer must be bound to read-only 1080 listener discovery'
    Assert ($raw -match 'Ensure-V7OfficialPuttyHostKeyTrust') 'host-key fail-closed helper preserved'
    Assert ($raw -match "'-pwfile'") 'pwfile security path preserved'
    Assert ($raw -match 'WU218_SAVEDSESSION_FALLBACK_V1') 'WU218 marker present'
    Assert ($raw -match "\$V7PuttyDiscoveryCandidates\s*=\s*@\(\s*\$V7LegacyPuttyPath,") 'legacy/configured candidate must be first'

    Write-Host 'PNCC_WU218_REGRESSION=PASS runtime_mutation=false reserve_1080_mutation=false primary_1081_runtime=false'
    exit 0
}
finally{
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
