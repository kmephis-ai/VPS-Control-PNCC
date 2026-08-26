#requires -Version 5.1
function Initialize-V7DemoEvidence {
    param([Parameter(Mandatory=$true)][string]$StateDir,[Parameter(Mandatory=$true)][string[]]$ModuleNames,[Parameter(Mandatory=$true)]$Defaults)
    if(-not(Test-Path -LiteralPath $StateDir)){New-Item -ItemType Directory -Path $StateDir -Force|Out-Null}
    $cfg=[ordered]@{Version='6.5'};foreach($m in $ModuleNames){$cfg[$m]=[string]$Defaults[$m]}
    [IO.File]::WriteAllText((Join-Path $StateDir 'routing-config.json'),(([pscustomobject]$cfg)|ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($true)))
    $effective=[ordered]@{};$health=[ordered]@{};$metrics=[ordered]@{};$auto=[ordered]@{}
    $vpsSet=@('OpenAI','Claude')
    $i=0
    foreach($m in $ModuleNames){
        $mode=[string]$cfg[$m];$eff=if($mode -eq 'VPS'){'VPS'}elseif($mode -eq 'DIRECT'){'DIRECT'}elseif($vpsSet -contains $m){'VPS'}else{'DIRECT'}
        $effective[$m]=$eff;$health[$m]='HEALTHY';$lat=170+($i*17);if($eff -eq 'VPS'){$lat+=310};$metrics[$m]=[pscustomobject]@{LatencyMs=$lat;FailureClass='NONE';Detail='Демонстрационные данные RC14.12'}
        $auto[$m]=[pscustomobject]@{LastDecision=if($mode -eq 'AUTO'){if($eff -eq 'VPS'){'AUTO_DIRECT_FAILED'}else{'AUTO_DIRECT_HEALTHY'}}else{'INITIAL'};DirectFails=if($eff -eq 'VPS'){2}else{0};DirectRecoveries=if($eff -eq 'DIRECT'){3}else{0}}
        $i++
    }
    $runtime=[ordered]@{Version='6.5-demo';UpdatedAt=(Get-Date).ToString('o');Override='NONE';Effective=[pscustomobject]$effective;Health=[pscustomobject]$health;Metrics=[pscustomobject]$metrics;AutoState=[pscustomobject]$auto;LastReason='DEMO'}
    [IO.File]::WriteAllText((Join-Path $StateDir 'runtime-state.json'),(([pscustomobject]$runtime)|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($true)))
    [IO.File]::WriteAllText((Join-Path $StateDir 'last-known-good.ppx'),'DEMO LKG',(New-Object Text.UTF8Encoding($true)))
    $ops=[ordered]@{Modules=[ordered]@{}};foreach($m in $ModuleNames){$isVps=([string]$effective[$m] -eq 'VPS');$ops.Modules[$m]=[pscustomobject]@{DirectSeconds=if($isVps){6200}else{19800};VpsSeconds=if($isVps){17400}else{2100};Switches=if([string]$cfg[$m] -eq 'AUTO'){2}else{0}}}
    [IO.File]::WriteAllText((Join-Path $StateDir 'operational-stats.json'),(([pscustomobject]$ops)|ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($true)))
    $tele=Join-Path $StateDir 'telemetry.jsonl';if(Test-Path -LiteralPath $tele){Remove-Item -LiteralPath $tele -Force}
    $utf8=New-Object Text.UTF8Encoding($false);$sw=New-Object IO.StreamWriter($tele,$false,$utf8)
    try{$n=0;foreach($m in $ModuleNames){for($k=48;$k -ge 0;$k--){$route=if(($k%7 -eq 0) -and ([string]$cfg[$m] -eq 'AUTO')){'VPS'}else{[string]$effective[$m]};$base=140+($n*13);if($route -eq 'VPS'){$base+=300};$obj=[pscustomobject]@{Timestamp=(Get-Date).AddMinutes(-30*$k).ToString('o');Module=$m;Route=$route;State='HEALTHY';LatencyMs=($base+($k%5)*9);FailureClass='NONE'};$sw.WriteLine(($obj|ConvertTo-Json -Compress))};$n++}}finally{$sw.Dispose()}
    $inc=Join-Path $StateDir 'incidents.jsonl';$items=@(
        [pscustomobject]@{Timestamp=(Get-Date).AddHours(-5).ToString('o');Module='Claude';From='DIRECT';To='VPS';Reason='AUTO_DIRECT_FAILED';Detail='Демо: прямой маршрут недоступен'},
        [pscustomobject]@{Timestamp=(Get-Date).AddHours(-2).ToString('o');Module='GitHub';From='VPS';To='DIRECT';Reason='AUTO_FAILBACK';Detail='Демо: прямой маршрут восстановился'}
    );$sw=New-Object IO.StreamWriter($inc,$false,$utf8);try{foreach($x in $items){$sw.WriteLine(($x|ConvertTo-Json -Compress))}}finally{$sw.Dispose()}
    $self=Join-Path $StateDir 'selftest-history.jsonl';[IO.File]::WriteAllText($self,(([pscustomobject]@{Timestamp=(Get-Date).AddMinutes(-18).ToString('o');State='PASS'}|ConvertTo-Json -Compress)+[Environment]::NewLine),$utf8)
}

function Invoke-V7DemoAction {
    param([Parameter(Mandatory=$true)][string]$Action,[Parameter(Mandatory=$true)][string]$StateDir,[Parameter(Mandatory=$true)][string[]]$ModuleNames)
    $runtimeFile=Join-Path $StateDir 'runtime-state.json';$configFile=Join-Path $StateDir 'routing-config.json'
    $r=Get-Content -LiteralPath $runtimeFile -Raw|ConvertFrom-Json
    $cfg=Get-Content -LiteralPath $configFile -Raw|ConvertFrom-Json
    if($Action -eq 'Direct'){foreach($m in $ModuleNames){$r.Effective.$m='DIRECT'};$r.Override='DIRECT';$r.LastReason='MANUAL_DIRECT'}
    elseif($Action -eq 'Apply'){$r.Override='NONE';foreach($m in $ModuleNames){$mode=[string]$cfg.$m;if($mode -eq 'VPS'){$r.Effective.$m='VPS'}elseif($mode -eq 'DIRECT'){$r.Effective.$m='DIRECT'}else{$r.Effective.$m=if($m -in @('OpenAI','Claude')){'VPS'}else{'DIRECT'}}};$r.LastReason='MANUAL_APPLY'}
    elseif($Action -eq 'RestartTunnel'){$r.LastReason='DEMO_RESTART_TUNNEL'}
    elseif($Action -eq 'SelfTest'){$r.LastReason='DEMO_SELFTEST'}
    else{$r.LastReason=('DEMO_'+$Action.ToUpperInvariant())}
    $r.UpdatedAt=(Get-Date).ToString('o');[IO.File]::WriteAllText($runtimeFile,($r|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($true)))
    return [pscustomobject]@{ExitCode=0;Text="ДЕМО: операция '$Action' смоделирована без изменения Windows/VPS/Keenetic."}
}
