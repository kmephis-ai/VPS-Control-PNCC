#requires -Version 5.1
# VPS Control Center RC14.7 internal module. Pure/read-only status aggregation for the main Status Center and support snapshots.

function Get-V7StatusStateUi([string]$State) {
    switch (($State + '').ToUpperInvariant()) {
        'GOOD' { return 'ИСПРАВНО' }
        'WARN' { return 'ВНИМАНИЕ' }
        'BAD' { return 'ОШИБКА' }
        'NEUTRAL' { return 'НЕ ПРОВЕРЕН' }
        default { return 'НЕИЗВЕСТНО' }
    }
}

function Get-V7StatusCenterModel {
    param(
        $Runtime,
        $Watchdog,
        [bool]$SocksUp,
        $ProxifierStatus,
        $StorageHealth,
        [string[]]$ModuleNames,
        [string]$OverallState,
        [int]$RuntimeAgeSeconds = -1,
        $KeeneticInventory = $null,
        $Consistency = $null,
        $Tunnels = $null,
        [string]$RoutingTunnelId = 'PRIMARY_AUTO'
    )

    $healthy=0;$degraded=0;$failed=0;$unknown=0;$vpsCount=0
    foreach($module in @($ModuleNames)) {
        $h='UNKNOWN';$effective=''
        try { if($Runtime){$h=[string]$Runtime.Health.$module;$effective=[string]$Runtime.Effective.$module} } catch { }
        switch(($h+'').ToUpperInvariant()) {
            'HEALTHY' { $healthy++ }
            'DEGRADED' { $degraded++ }
            'FAILED' { $failed++ }
            default { $unknown++ }
        }
        if($effective -eq 'VPS'){$vpsCount++}
    }

    $runtimeFresh=($RuntimeAgeSeconds -ge 0 -and $RuntimeAgeSeconds -le 300)
    $routeState='GOOD'
    if(-not $Runtime){$routeState='BAD'}elseif(-not $runtimeFresh){$routeState='WARN'}elseif($failed -gt 0){$routeState='BAD'}elseif($degraded -gt 0 -or $unknown -gt 0){$routeState='WARN'}

    $dependencyState='GOOD';$dependencyDetail='VPS сейчас не используется управляемыми сервисами.'
    if($Runtime -and -not $runtimeFresh){$dependencyState='WARN';$dependencyDetail="runtime устарел ($RuntimeAgeSeconds с); текущее использование VPS неизвестно, последнее evidence: $vpsCount сервисов через VPS."}
    elseif($vpsCount -gt 0) {
        $problems=New-Object Collections.ArrayList
        if(-not $SocksUp){[void]$problems.Add('SOCKS не работает')}
        if(-not $ProxifierStatus -or -not [bool]$ProxifierStatus.Running){[void]$problems.Add('Proxifier не запущен')}
        $watchState='UNKNOWN';try{$watchState=[string]$Watchdog.State}catch{}
        if($watchState -eq 'OFF') {[void]$problems.Add('фоновый контроллер не работает')}
        elseif($watchState -eq 'STALE' -or $watchState -eq 'UNKNOWN'){[void]$problems.Add('состояние фонового контроллера устарело')}
        if($problems.Count -gt 0){$dependencyState='BAD';$dependencyDetail=(@($problems)-join '; ')}
        else{$dependencyDetail="VPS используют сервисов: $vpsCount; SOCKS/Proxifier/контроллер доступны."}
    }

    $storageState='GOOD';$storageDetail='Структура данных доступна.'
    if(-not $StorageHealth -or -not [bool]$StorageHealth.Ok){
        $storageState='BAD'
        try{$storageDetail=(@($StorageHealth.Issues)-join '; ')}catch{$storageDetail='Состояние хранилища недоступно.'}
        if(-not $storageDetail){$storageDetail='Состояние хранилища недоступно.'}
    }

    $freshnessState='NEUTRAL';$freshnessDetail='runtime-state.json ещё не прочитан.'
    if($RuntimeAgeSeconds -ge 0) {
        if($RuntimeAgeSeconds -le 120){$freshnessState='GOOD'}elseif($RuntimeAgeSeconds -le 300){$freshnessState='WARN'}else{$freshnessState='WARN'}
        $freshnessDetail="Возраст runtime: $RuntimeAgeSeconds с."
    }

    $keenState='NEUTRAL';$keenDetail='Read-only inventory ещё не выполнялся.';$keenLifecycle='NOT_CHECKED';$keenRouter='NOT_CHECKED'
    if($KeeneticInventory) {
        try{if($KeeneticInventory.LifecycleState){$keenLifecycle=[string]$KeeneticInventory.LifecycleState};if($KeeneticInventory.RouterState){$keenRouter=[string]$KeeneticInventory.RouterState}}catch{}
        switch($keenLifecycle) {
            'HEALTHY' {$keenState='GOOD'}
            'UPDATE_AVAILABLE' {$keenState='WARN'}
            'DEGRADED' {$keenState='WARN'}
            'FAILED' {$keenState='BAD'}
            'RECOVERY_REQUIRED' {$keenState='BAD'}
            'NOT_INSTALLED' {$keenState='NEUTRAL'}
            default {$keenState='NEUTRAL'}
        }
        if($keenRouter -eq 'UNREACHABLE'){$keenState='BAD'}
        try{
            $parts=New-Object Collections.ArrayList
            if($KeeneticInventory.RouterState){[void]$parts.Add("роутер: $([string]$KeeneticInventory.RouterState)")}
            if($KeeneticInventory.EntwareState){[void]$parts.Add("Entware: $([string]$KeeneticInventory.EntwareState)")}
            if($KeeneticInventory.LastEvidenceAt){[void]$parts.Add("evidence: $([string]$KeeneticInventory.LastEvidenceAt)")}
            if($KeeneticInventory.LastOperationState -eq 'FAILED'){[void]$parts.Add("последняя операция: FAILED rc=$([string]$KeeneticInventory.LastExitCode)")}
            if($parts.Count -gt 0){$keenDetail=(@($parts)-join '; ')}
        }catch{}
    }

    $consistencyState='NEUTRAL';$consistencyDetail='Проверка связанности ещё не выполнялась.'
    if($Consistency) {
        try {
            if([bool]$Consistency.Ok){$consistencyState='GOOD'}else{$consistencyState='BAD'}
            $consistencyDetail="checks=$([int]$Consistency.Summary.Passed)/$([int]$Consistency.Summary.Checks); errors=$([int]$Consistency.Summary.Errors); warnings=$([int]$Consistency.Summary.Warnings)"
            if([int]$Consistency.Summary.Warnings -gt 0 -and $consistencyState -eq 'GOOD'){$consistencyState='WARN'}
        } catch {$consistencyState='WARN';$consistencyDetail='Результат проверки связанности не удалось интерпретировать.'}
    }

    $localState='GOOD'
    if(($OverallState+'').ToUpperInvariant() -in @('FAILED','ENGINE_MISSING','NO_RUNTIME')){$localState='BAD'}
    elseif(($OverallState+'').ToUpperInvariant() -in @('DEGRADED','ATTENTION','STALE_RUNTIME')){$localState='WARN'}

    $primaryTunnelState='NEUTRAL';$primaryTunnelDetail='PRIMARY_AUTO 1081: данные недоступны.'
    $reserveTunnelState='NEUTRAL';$reserveTunnelDetail='RESERVE_MANUAL 1080: OFF допустим.'
    try{
        $tp=@($Tunnels|Where-Object{[string]$_.Id -eq 'PRIMARY_AUTO'}|Select-Object -First 1)
        $tr=@($Tunnels|Where-Object{[string]$_.Id -eq 'RESERVE_MANUAL'}|Select-Object -First 1)
        if($tp.Count-eq1){
            $primaryTunnelState=$(if([bool]$tp[0].Listening){'GOOD'}else{'WARN'})
            $primaryTunnelDetail="PRIMARY_AUTO 127.0.0.1:1081; listening=$([bool]$tp[0].Listening); lifecycle=AUTO"
        }
        if($tr.Count-eq1){
            $reserveTunnelState=$(if([bool]$tr[0].Listening){'GOOD'}else{'NEUTRAL'})
            $reserveTunnelDetail="RESERVE_MANUAL 127.0.0.1:1080; listening=$([bool]$tr[0].Listening); lifecycle=MANUAL_ONLY; OFF допустим"
        }
    }catch{}
    if($RoutingTunnelId -eq 'RESERVE_MANUAL' -and $reserveTunnelState -ne 'GOOD'){
        $dependencyState='BAD'
        $dependencyDetail='VPS-правила вручную направлены через RESERVE_MANUAL/1080, но резервный tunnel не LISTEN.'
    }

    # Compute the top-level control state only after all dependency adjustments are final.
    $controlStates=@($localState,$routeState,$dependencyState,$storageState,$freshnessState,$consistencyState)
    $controlState=if($controlStates -contains 'BAD'){'BAD'}elseif($controlStates -contains 'WARN'){'WARN'}else{'GOOD'}

    $nodes=@(
        [pscustomobject]@{Id='LOCAL';Name='Локальный контур';State=$localState;Detail="Общее состояние: $OverallState"},
        [pscustomobject]@{Id='ROUTING';Name='Маршрутизация';State=$routeState;Detail="исправно=$healthy; ухудшено=$degraded; ошибка=$failed; неизвестно=$unknown"},
        [pscustomobject]@{Id='DEPENDENCIES';Name='VPS-зависимости';State=$dependencyState;Detail=$dependencyDetail},
        [pscustomobject]@{Id='TUNNEL_PRIMARY';Name='Туннель PRIMARY_AUTO';State=$primaryTunnelState;Detail=$primaryTunnelDetail},
        [pscustomobject]@{Id='TUNNEL_RESERVE';Name='Туннель RESERVE_MANUAL';State=$reserveTunnelState;Detail=$reserveTunnelDetail},
        [pscustomobject]@{Id='STORAGE';Name='Хранилище V7';State=$storageState;Detail=$storageDetail},
        [pscustomobject]@{Id='FRESHNESS';Name='Свежесть runtime';State=$freshnessState;Detail=$freshnessDetail},
        [pscustomobject]@{Id='CONSISTENCY';Name='Связанность функций';State=$consistencyState;Detail=$consistencyDetail},
        [pscustomobject]@{Id='KEENETIC';Name='Keenetic';State=$keenState;Detail=$keenDetail}
    )

    return [pscustomobject]@{
        SchemaVersion=1
        GeneratedAt=(Get-Date).ToString('o')
        OverallState=$OverallState
        ControlState=$controlState
        ModuleCounts=[pscustomobject]@{Total=@($ModuleNames).Count;Healthy=$healthy;Degraded=$degraded;Failed=$failed;Unknown=$unknown;UsingVps=$vpsCount}
        Nodes=$nodes
        KeeneticLifecycle=$keenLifecycle
        KeeneticRouterState=$keenRouter
        RuntimeAgeSeconds=$RuntimeAgeSeconds
        RuntimeFresh=$runtimeFresh
    }
}

function Format-V7StatusCenterLine($Model) {
    if(-not $Model){return 'Status Center: данные недоступны.'}
    $lookup=@{}
    foreach($n in @($Model.Nodes)){$lookup[[string]$n.Id]=$n}
    $route=$lookup['ROUTING'];$deps=$lookup['DEPENDENCIES'];$storage=$lookup['STORAGE'];$fresh=$lookup['FRESHNESS'];$consistency=$lookup['CONSISTENCY'];$keen=$lookup['KEENETIC']
    $counts=$Model.ModuleCounts
    $keenText=if([string]$Model.KeeneticRouterState -eq 'UNREACHABLE'){'НЕДОСТУПЕН'}else{switch([string]$Model.KeeneticLifecycle){'HEALTHY'{'ИСПРАВНО'}'UPDATE_AVAILABLE'{'ЕСТЬ ОБНОВЛЕНИЯ'}'NOT_INSTALLED'{'НЕ УСТАНОВЛЕН'}'DEGRADED'{'УХУДШЕНО'}'FAILED'{'ОШИБКА'}'RECOVERY_REQUIRED'{'НУЖНО ВОССТАНОВЛЕНИЕ'}default{'НЕ ПРОВЕРЕН'}}}
    $routeText=if([bool]$Model.RuntimeFresh){"$([int]$counts.Healthy)/$([int]$counts.Total) исправно"}elseif([int]$Model.RuntimeAgeSeconds -ge 0){"ДАННЫЕ УСТАРЕЛИ ($([int]$Model.RuntimeAgeSeconds) с)"}else{'НЕТ ДАННЫХ'}
    $freshText=if([int]$Model.RuntimeAgeSeconds -gt 300){'УСТАРЕЛИ'}else{Get-V7StatusStateUi ([string]$fresh.State)}
    return (('Windows: {0}  •  Маршруты: {1}  •  VPS-зависимости: {2}  •  Данные: {3}' -f (Get-V7StatusStateUi ([string]$lookup['LOCAL'].State)),$routeText,(Get-V7StatusStateUi ([string]$deps.State)),$freshText) + "`r`n" + ('Хранилище: {0}  •  Связанность: {1}  •  Keenetic: {2}' -f (Get-V7StatusStateUi ([string]$storage.State)),(Get-V7StatusStateUi ([string]$consistency.State)),$keenText))
}

function Format-V7StatusCenterDetails($Model) {
    if(-not $Model){return 'Status Center: данные недоступны.'}
    $lines=New-Object Collections.ArrayList
    [void]$lines.Add('=== STATUS CENTER ===')
    [void]$lines.Add("Общее состояние: $([string]$Model.OverallState)")
    foreach($n in @($Model.Nodes)){
        [void]$lines.Add(('{0}: {1} — {2}' -f [string]$n.Name,(Get-V7StatusStateUi ([string]$n.State)),[string]$n.Detail))
    }
    return (@($lines)-join "`r`n")
}

function New-V7SafeSystemSnapshot {
    param(
        [string]$UiVersion,[string]$EngineVersion,[bool]$Demo,[string]$DataRoot,[string]$StateDir,
        $Readiness,$Storage,$PackageIntegrity,$Consistency,$ActiveVps,$KeeneticConfig,$KeeneticInventory,$StatusCenter,
        $RoutingConfig,$Runtime,$RecentEvents,$Tunnels=$null,[string]$RoutingTunnelId='PRIMARY_AUTO'
    )
    return [pscustomobject][ordered]@{
        SchemaVersion=2;Product='VPS Control Center';UiVersion=$UiVersion;EngineVersion=$EngineVersion;CreatedAt=(Get-Date).ToString('o');Demo=$Demo;
        DataRoot=$DataRoot;StateDir=$StateDir;Readiness=$Readiness;Storage=$Storage;PackageIntegrity=$PackageIntegrity;Consistency=$Consistency;
        StatusCenter=$StatusCenter;ActiveVps=$ActiveVps;Keenetic=$KeeneticConfig;KeeneticInventory=$KeeneticInventory;
        RoutingConfig=$RoutingConfig;Runtime=$Runtime;Tunnels=@($Tunnels);RoutingTunnelId=$RoutingTunnelId;RecentEvents=@($RecentEvents);SecretsIncluded=$false
    }
}