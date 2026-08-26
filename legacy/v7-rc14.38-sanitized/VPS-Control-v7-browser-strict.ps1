#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('Status','Enable','Disable')][string]$Action,
    [Parameter(Mandatory=$true)][ValidateSet('Yandex','Edge')][string]$Browser,
    [string]$ExePath = ''
)
$ErrorActionPreference='Stop'
$rule="VPS Control V7 Strict UDP Block - $Browser"

function Get-RuleState {
    $rules=@(Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue)
    if($rules.Count -eq 0){
        return [pscustomobject]@{Exists=$false;Count=0;Enabled=$false;Program='';ProgramMatch=$false;Protocol='';Direction='';Action='';Healthy=$false}
    }
    $r=$rules[0]
    $app=$null; $port=$null
    try{$app=Get-NetFirewallApplicationFilter -AssociatedNetFirewallRule $r -ErrorAction Stop}catch{}
    try{$port=Get-NetFirewallPortFilter -AssociatedNetFirewallRule $r -ErrorAction Stop}catch{}
    $program=if($app){[string]$app.Program}else{''}
    $programMatch=$false
    if($ExePath -and $program){
        try{$programMatch=([IO.Path]::GetFullPath($program).TrimEnd('\\') -ieq [IO.Path]::GetFullPath($ExePath).TrimEnd('\\'))}catch{$programMatch=($program -ieq $ExePath)}
    }
    $protocol=if($port){[string]$port.Protocol}else{''}
    $isUdp=($protocol -ieq 'UDP' -or $protocol -eq '17')
    $enabled=([string]$r.Enabled -ieq 'True')
    $direction=([string]$r.Direction)
    $actionName=([string]$r.Action)
    $healthy=($rules.Count -eq 1 -and $enabled -and $direction -ieq 'Outbound' -and $actionName -ieq 'Block' -and $isUdp -and $programMatch)
    return [pscustomobject]@{Exists=$true;Count=$rules.Count;Enabled=$enabled;Program=$program;ProgramMatch=$programMatch;Protocol=$protocol;Direction=$direction;Action=$actionName;Healthy=$healthy}
}

function Write-State($s){
    Write-Output "Browser=$Browser"
    Write-Output "Exe=$ExePath"
    Write-Output "Exists=$([bool]$s.Exists)"
    Write-Output "Count=$([int]$s.Count)"
    Write-Output "Enabled=$([bool]$s.Enabled)"
    Write-Output "Program=$([string]$s.Program)"
    Write-Output "ProgramMatch=$([bool]$s.ProgramMatch)"
    Write-Output "Protocol=$([string]$s.Protocol)"
    Write-Output "Direction=$([string]$s.Direction)"
    Write-Output "Action=$([string]$s.Action)"
    Write-Output "Healthy=$([bool]$s.Healthy)"
}

if($Action -eq 'Status'){Write-State (Get-RuleState);exit 0}
if($Action -eq 'Enable'){
    if(-not $ExePath -or -not(Test-Path -LiteralPath $ExePath -PathType Leaf)){Write-Error "EXE браузера не найден: $ExePath";exit 2}
    Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue|Remove-NetFirewallRule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $rule -Direction Outbound -Action Block -Program $ExePath -Protocol UDP -Profile Any -Description 'VPS Control Center V7: block browser UDP to prevent QUIC/WebRTC UDP bypass while TCP is routed through Proxifier/VPS.'|Out-Null
    $state=Get-RuleState
    if(-not $state.Healthy){Write-State $state;Write-Error 'Firewall rule created but integrity verification failed.';exit 3}
    Write-State $state
    Write-Output "STRICT_BROWSER_ENABLED $Browser";exit 0
}
if($Action -eq 'Disable'){
    Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue|Remove-NetFirewallRule -ErrorAction SilentlyContinue
    $state=Get-RuleState
    if($state.Exists){Write-State $state;Write-Error 'Firewall rule still exists.';exit 4}
    Write-State $state
    Write-Output "STRICT_BROWSER_DISABLED $Browser";exit 0
}
