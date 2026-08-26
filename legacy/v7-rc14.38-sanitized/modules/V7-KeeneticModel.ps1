#requires -Version 5.1
# VPS Control Center RC14 read-only Keenetic/Entware evidence model.

function Get-V7KeeneticLifecycleText {
@'
ЦЕЛЕВАЯ МОДЕЛЬ ENTWARE (RC14 READINESS)

NOT_INSTALLED
  -> PRECHECK
  -> READY_TO_INSTALL
  -> BACKUP_REQUIRED
  -> INSTALLING
  -> VERIFYING
  -> HEALTHY

Отдельные состояния:
PARTIAL_INSTALL · DEGRADED · UPDATE_AVAILABLE · FAILED · RECOVERY_REQUIRED

RC14 разрешает discovery/read-only часть и уже существующие подтверждаемые maintenance-операции opkg update/upgrade; install/remove остаётся заблокирован.
Mutation install/remove остаётся FAIL-CLOSED до реального evidence с Keenetic.

Обязательные preconditions будущей установки:
1. Read-only inventory Keenetic/Entware с сохранённым evidence timestamp.
2. Точная модель устройства, версия KeeneticOS и архитектура CPU.
3. Наличие/состояние компонента Open Package support (OPKG).
4. Инвентаризация USB-накопителей, разделов, файловой системы и свободного места.
5. Проверка существующих /opt, opkg, initrc и конфликтующих сервисов.
6. Recovery backup startup-config и метаданных текущего Entware.
7. Exact transaction plan: что будет создано/изменено/удалено.
8. Явное подтверждение владельца именно этого transaction plan.
9. Mutation с журналом шагов.
10. Read-back verification + health check.
11. При неполном результате: RECOVERY_REQUIRED и конкретный recovery path.

Будущее удаление:
backup -> inventory -> stop managed services -> detach OPKG -> optional cleanup -> verify LAN/WAN/router health.

MUTATION STATUS: BLOCKED_RUNTIME_EVIDENCE_REQUIRED
'@
}

function Get-V7KeeneticFieldValue {
    param([string]$Text,[string]$Name)
    if($Text -match ("(?m)^"+[regex]::Escape($Name)+"=(.*)$")){return $Matches[1].Trim()}
    return ''
}

function Parse-V7KeeneticEvidence {
    param([string]$Text,[string]$Action='')
    $routerState='NOT_CHECKED';$entwareState='NOT_CHECKED';$lifecycle='NOT_CHECKED'
    $ping=Get-V7KeeneticFieldValue $Text 'PING'
    $httpAuth=Get-V7KeeneticFieldValue $Text 'HTTP_AUTH'
    $tcp80=Get-V7KeeneticFieldValue $Text 'TCP_80'
    $tcp443=Get-V7KeeneticFieldValue $Text 'TCP_443'
    $hostname=Get-V7KeeneticFieldValue $Text 'HOST'
    $kernel=Get-V7KeeneticFieldValue $Text 'KERNEL'
    $opkg=Get-V7KeeneticFieldValue $Text 'OPKG'
    $optMount=Get-V7KeeneticFieldValue $Text 'OPT_MOUNT'
    $optFs=Get-V7KeeneticFieldValue $Text 'OPT_FS'
    $packages=Get-V7KeeneticFieldValue $Text 'PACKAGES'
    $updates=Get-V7KeeneticFieldValue $Text 'UPGRADABLE'
    if(-not $updates){$updates=Get-V7KeeneticFieldValue $Text 'UPGRADABLE_AFTER'}
    $initrc=Get-V7KeeneticFieldValue $Text 'INITRC'

    if($Action -eq 'Probe' -or $Text -match 'KEENETIC · READ-ONLY PROBE') {
        if($tcp80 -eq 'OPEN' -or $tcp443 -eq 'OPEN' -or ($httpAuth -and $httpAuth -ne 'UNREACHABLE')){$routerState='REACHABLE'}
        elseif($ping -eq 'PASS'){$routerState='REACHABLE'}
        elseif($Text){$routerState='UNREACHABLE'}
    }

    if($Text -match '(?m)^ENTWARE=INSTALLED\s*$'){
        $entwareState='INSTALLED'
        $u=0;try{if($updates){$u=[int]$updates}}catch{}
        if($u -gt 0){$lifecycle='UPDATE_AVAILABLE'}
        elseif($opkg -and $optFs){$lifecycle='HEALTHY'}
        else{$lifecycle='DEGRADED'}
    }
    elseif($Text -match '(?m)^ENTWARE=NOT_DETECTED\s*$'){$entwareState='NOT_DETECTED';$lifecycle='NOT_INSTALLED'}

    $sshPort='';$sshState=''
    foreach($m in [regex]::Matches($Text,'(?m)^TCP_(\d+)=(OPEN|CLOSED)\s*$')){
        if($m.Groups[1].Value -ne '80' -and $m.Groups[1].Value -ne '443'){$sshPort=$m.Groups[1].Value;$sshState=$m.Groups[2].Value;break}
    }

    return [pscustomobject]@{
        Action=$Action;RouterState=$routerState;EntwareState=$entwareState;LifecycleState=$lifecycle;
        Ping=$ping;HttpAuth=$httpAuth;Tcp80=$tcp80;Tcp443=$tcp443;EntwareSshPort=$sshPort;EntwareSshState=$sshState;
        Hostname=$hostname;Kernel=$kernel;OpkgPath=$opkg;OptMount=$optMount;OptFs=$optFs;Packages=$packages;Updates=$updates;Initrc=$initrc
    }
}

function Merge-V7KeeneticInventory {
    param($Existing,[string]$Text,[string]$Action,[int]$ExitCode)
    $e=Parse-V7KeeneticEvidence -Text $Text -Action $Action
    $isEvidenceAction=($Action -in @('Probe','EntwareStatus','EntwareRefresh','EntwareUpgrade'))
    $now=(Get-Date).ToString('o')
    $obj=[ordered]@{
        SchemaVersion=2;LastEvidenceAt='';LastAction=$Action;LastExitCode=$ExitCode;LastOperationAt=$now;LastOperationState=$(if($ExitCode -eq 0){'PASS'}else{'FAILED'});
        RouterState='NOT_CHECKED';EntwareState='NOT_CHECKED';LifecycleState='NOT_CHECKED';
        Ping='';HttpAuth='';Tcp80='';Tcp443='';EntwareSshPort='';EntwareSshState='';
        Hostname='';Kernel='';OpkgPath='';OptMount='';OptFs='';Packages='';Updates='';Initrc='';
        LastProbeAt='';LastEntwareAt=''
    }
    if($Existing){
        # OrderedDictionary invalidates a live Keys enumerator when a value is assigned.
        # Snapshot the keys first; otherwise a successful probe can fail only while merging local inventory.
        foreach($p in @($obj.Keys)){
            try{if($Existing.PSObject.Properties[$p]){$obj[$p]=$Existing.$p}}catch{}
        }
        $obj.SchemaVersion=2;$obj.LastAction=$Action;$obj.LastExitCode=$ExitCode;$obj.LastOperationAt=$now;$obj.LastOperationState=$(if($ExitCode -eq 0){'PASS'}else{'FAILED'})
    }

    foreach($name in @('Ping','HttpAuth','Tcp80','Tcp443','EntwareSshPort','EntwareSshState','Hostname','Kernel','OpkgPath','OptMount','OptFs','Packages','Updates','Initrc')){
        $v='';try{$v=[string]$e.$name}catch{}
        if($v){$obj[$name]=$v}
    }
    if([string]$e.RouterState -ne 'NOT_CHECKED'){$obj.RouterState=[string]$e.RouterState;$obj.LastProbeAt=$now}
    if([string]$e.EntwareState -ne 'NOT_CHECKED'){$obj.EntwareState=[string]$e.EntwareState;$obj.LastEntwareAt=$now}
    if([string]$e.LifecycleState -ne 'NOT_CHECKED'){$obj.LifecycleState=[string]$e.LifecycleState}
    $hasParsedEvidence=([string]$e.RouterState -ne 'NOT_CHECKED' -or [string]$e.EntwareState -ne 'NOT_CHECKED' -or [string]$e.Hostname -or [string]$e.Kernel -or [string]$e.OpkgPath -or [string]$e.OptFs)
    if($isEvidenceAction -and $hasParsedEvidence){$obj.LastEvidenceAt=$now}

    # Operational failures are tracked separately and must not invent a router/Entware lifecycle state.
    return [pscustomobject]$obj
}

function Get-V7KeeneticRouterUi($Inventory) {
    if(-not $Inventory){return 'Не проверен'}
    switch([string]$Inventory.RouterState){'REACHABLE'{return 'Доступен'}'UNREACHABLE'{return 'Недоступен'}default{return 'Не проверен'}}
}
function Get-V7KeeneticEntwareUi($Inventory) {
    if(-not $Inventory){return 'Не проверен'}
    switch([string]$Inventory.EntwareState){'INSTALLED'{return 'Установлен'}'NOT_DETECTED'{return 'Не обнаружен'}default{return 'Не проверен'}}
}
function Get-V7KeeneticLifecycleUi($Inventory) {
    if(-not $Inventory){return 'НЕ ПРОВЕРЕН'}
    switch([string]$Inventory.LifecycleState){
        'HEALTHY'{return 'ИСПРАВНО'}'UPDATE_AVAILABLE'{return 'ЕСТЬ ОБНОВЛЕНИЯ'}'NOT_INSTALLED'{return 'НЕ УСТАНОВЛЕН'}
        'DEGRADED'{return 'УХУДШЕНО'}'FAILED'{return 'ОШИБКА'}'RECOVERY_REQUIRED'{return 'НУЖНО ВОССТАНОВЛЕНИЕ'}default{return 'НЕ ПРОВЕРЕН'}
    }
}
function Format-V7KeeneticInventorySummary($Inventory) {
    if(-not $Inventory){return 'Read-only inventory Keenetic ещё не выполнялся.'}
    $parts=New-Object Collections.ArrayList
    [void]$parts.Add("Состояние: $(Get-V7KeeneticLifecycleUi $Inventory)")
    [void]$parts.Add("роутер: $(Get-V7KeeneticRouterUi $Inventory)")
    [void]$parts.Add("Entware: $(Get-V7KeeneticEntwareUi $Inventory)")
    if([string]$Inventory.Packages){[void]$parts.Add("пакетов: $([string]$Inventory.Packages)")}
    if([string]$Inventory.Updates){[void]$parts.Add("обновлений: $([string]$Inventory.Updates)")}
    if([string]$Inventory.LastEvidenceAt){[void]$parts.Add("evidence: $([string]$Inventory.LastEvidenceAt)")}
    if([string]$Inventory.LastOperationState -eq 'FAILED'){[void]$parts.Add("последняя операция: ошибка (rc=$([string]$Inventory.LastExitCode))")}
    return (@($parts)-join ' · ')
}
