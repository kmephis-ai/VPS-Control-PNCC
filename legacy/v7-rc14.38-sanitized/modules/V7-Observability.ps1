#requires -Version 5.1
# VPS Control Center RC14 internal module. Dot-sourced by VPS-Control-v7.ps1.

function Get-DefaultUiSettings {
    return [pscustomobject]@{
        AutoRefreshSeconds = 3
        TrayNotifications = $true
        ObservationModule = 'GitHub'
        ObservationPeriod = '24 часа'
    }
}

function Get-UiSettings {
    $defaults = Get-DefaultUiSettings
    $saved = Read-JsonFile $UiSettingsFile
    if (-not $saved) { return $defaults }
    $refresh = 3
    try { $refresh = [int]$saved.AutoRefreshSeconds } catch { $refresh = 3 }
    if (@(3,5,10,30) -notcontains $refresh) { $refresh = 3 }
    $notifications = $true
    if ($saved.TrayNotifications -ne $null) { $notifications = [bool]$saved.TrayNotifications }
    $module = [string]$saved.ObservationModule
    if ($ModuleNames -notcontains $module) { $module = 'GitHub' }
    $period = [string]$saved.ObservationPeriod
    if (@('1 час','6 часов','24 часа','7 дней') -notcontains $period) { $period = '24 часа' }
    return [pscustomobject]@{
        AutoRefreshSeconds = $refresh
        TrayNotifications = $notifications
        ObservationModule = $module
        ObservationPeriod = $period
    }
}

function Save-UiSettings($Settings) {
    try {
        $safe = [pscustomobject]@{
            AutoRefreshSeconds = [int]$Settings.AutoRefreshSeconds
            TrayNotifications = [bool]$Settings.TrayNotifications
            ObservationModule = [string]$Settings.ObservationModule
            ObservationPeriod = [string]$Settings.ObservationPeriod
        }
        Write-TextAtomic -Path $UiSettingsFile -Text ($safe | ConvertTo-Json -Depth 4)
        return $true
    }
    catch {
        Write-UiLog "UI settings save failed: $($_.Exception.Message)"
        return $false
    }
}

function Get-TelemetryWindowStats([string]$Module, [int]$Hours) {
    $cutoff = (Get-Date).AddHours(-1 * $Hours)
    $samples = Read-JsonLines -Path $TelemetryFile -Tail 30000
    $groups = @{
        DIRECT = New-Object System.Collections.ArrayList
        VPS = New-Object System.Collections.ArrayList
    }
    $healthy = @{ DIRECT = 0; VPS = 0 }
    $total = @{ DIRECT = 0; VPS = 0 }
    $last = @{ DIRECT = $null; VPS = $null }
    foreach ($s in $samples) {
        if ([string]$s.Module -ne $Module) { continue }
        try { $dt = [datetime]$s.Timestamp } catch { continue }
        if ($dt -lt $cutoff) { continue }
        $route = ([string]$s.Route).ToUpperInvariant()
        if (@('DIRECT','VPS') -notcontains $route) { continue }
        $total[$route]++
        if (([string]$s.State).ToUpperInvariant() -eq 'HEALTHY') { $healthy[$route]++ }
        try {
            $lat = [double]$s.LatencyMs
            if ($lat -gt 0) { [void]$groups[$route].Add($lat) }
        }
        catch { }
        $last[$route] = $s
    }

    $result = @{}
    foreach ($route in @('DIRECT','VPS')) {
        $vals = @($groups[$route] | Sort-Object)
        $avg = 0.0; $p95 = 0.0
        if ($vals.Count -gt 0) {
            $avg = [math]::Round((($vals | Measure-Object -Average).Average), 0)
            $idx = [math]::Ceiling($vals.Count * 0.95) - 1
            if ($idx -lt 0) { $idx = 0 }
            if ($idx -ge $vals.Count) { $idx = $vals.Count - 1 }
            $p95 = [math]::Round([double]$vals[$idx], 0)
        }
        $healthPct = 0.0
        if ($total[$route] -gt 0) { $healthPct = [math]::Round(($healthy[$route] / [double]$total[$route]) * 100, 1) }
        $result[$route] = [pscustomobject]@{
            Samples = [int]$total[$route]
            HealthyPercent = $healthPct
            AvgMs = $avg
            P95Ms = $p95
            Last = $last[$route]
        }
    }
    return $result
}

function Get-QuantitativeAutoExplanation([string]$Module, [int]$Hours, $Config, $Runtime) {
    $base = Get-AutoExplanation -Config $Config -Runtime $Runtime -Module $Module
    $mode = Normalize-Mode ([string]$Config.$Module) 'DIRECT'
    if ($mode -ne 'AUTO') { return $base }
    $stats = Get-TelemetryWindowStats -Module $Module -Hours $Hours
    $d = $stats.DIRECT
    $v = $stats.VPS
    $lines = New-Object System.Collections.ArrayList
    [void]$lines.Add($base)
    [void]$lines.Add('')
    [void]$lines.Add("За выбранный период ($Hours ч):")
    if ($d.Samples -gt 0) {
        [void]$lines.Add("• Напрямую: измерений=$($d.Samples), исправно=$($d.HealthyPercent)%, средняя=$([int]$d.AvgMs) мс, P95=$([int]$d.P95Ms) мс.")
    }
    else { [void]$lines.Add('• Напрямую: данных пока недостаточно.') }
    if ($v.Samples -gt 0) {
        [void]$lines.Add("• Через VPS: измерений=$($v.Samples), исправно=$($v.HealthyPercent)%, средняя=$([int]$v.AvgMs) мс, P95=$([int]$v.P95Ms) мс.")
    }
    else { [void]$lines.Add('• Через VPS: данных пока недостаточно.') }

    if ($d.Samples -ge 2 -and $v.Samples -ge 2 -and $d.AvgMs -gt 0 -and $v.AvgMs -gt 0) {
        $delta = [math]::Round($d.AvgMs - $v.AvgMs, 0)
        if ($delta -gt 0) { [void]$lines.Add("Сравнение: VPS в среднем быстрее примерно на $([int]$delta) мс, но режим «Авто» переключается только после выполнения унаследованных порогов и гистерезиса движка.") }
        elseif ($delta -lt 0) { [void]$lines.Add("Сравнение: DIRECT в среднем быстрее примерно на $([int][math]::Abs($delta)) мс; это соответствует принципу минимального использования VPS.") }
        else { [void]$lines.Add('Сравнение: средняя задержка маршрутов практически одинакова.') }
    }
    return ($lines -join "`r`n")
}

function Get-SafeSnapshotText($Config, $Runtime, $Overall, $Watchdog, [bool]$SocksUp, [bool]$ReserveSocksUp=$false, [string]$RoutingTunnelId='PRIMARY_AUTO', $ProxifierStatus) {
    $lines = New-Object System.Collections.ArrayList
    [void]$lines.Add("VPS Control Center v$UiVersion / engine V$EngineVersion$(if($Demo){' / ДЕМО'}else{''})")
    [void]$lines.Add("Время: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')")
    [void]$lines.Add("Общее состояние: $(Get-OverallUiName $Overall)")
    [void]$lines.Add("PRIMARY_AUTO 127.0.0.1:1081: $(if ($SocksUp) {'LISTEN'} else {'OFF'})")
    [void]$lines.Add("RESERVE_MANUAL 127.0.0.1:1080: $(if ($ReserveSocksUp) {'LISTEN'} else {'OFF (допустимо)'})")
    [void]$lines.Add("VPS-правила используют: $RoutingTunnelId")
    [void]$lines.Add("Proxifier: $(if ($ProxifierStatus.Running) {'RUNNING'} else {'OFF'})")
    [void]$lines.Add("Watchdog: $($Watchdog.State) · $($Watchdog.Detail)")
    [void]$lines.Add("LKG: $(if (Test-Path -LiteralPath $LastGoodProfilePath) {'PRESENT'} else {'MISSING'})")
    [void]$lines.Add('')
    [void]$lines.Add('Маршрутизация:')
    foreach ($module in $ModuleNames) {
        $cfgMode = Normalize-Mode ([string]$Config.$module) 'DIRECT'
        $eff = if ($Runtime) { [string]$Runtime.Effective.$module } else { 'UNKNOWN' }
        $health = if ($Runtime) { [string]$Runtime.Health.$module } else { 'UNKNOWN' }
        $lat = '—'
        if ($Runtime -and $Runtime.Metrics.$module -and $Runtime.Metrics.$module.LatencyMs) { $lat = "$([int]$Runtime.Metrics.$module.LatencyMs)ms" }
        [void]$lines.Add("- $(Get-ModuleUiName $module): config=$cfgMode effective=$eff health=$health latency=$lat")
    }
    [void]$lines.Add('')
    [void]$lines.Add('Снимок не содержит пароли, токены, содержимое LKG-профиля или controller source.')
    return ($lines -join "`r`n")
}

function Export-TelemetryCsv([string]$Module, [int]$Hours, [string]$Path) {
    $cutoff = (Get-Date).AddHours(-1 * $Hours)
    $rows = New-Object System.Collections.ArrayList
    $samples = Read-JsonLines -Path $TelemetryFile -Tail 30000
    foreach ($s in $samples) {
        if ([string]$s.Module -ne $Module) { continue }
        try { $dt = [datetime]$s.Timestamp } catch { continue }
        if ($dt -lt $cutoff) { continue }
        [void]$rows.Add([pscustomobject]@{
            Timestamp = $dt.ToString('yyyy-MM-dd HH:mm:ss')
            Module = $Module
            Route = [string]$s.Route
            State = [string]$s.State
            LatencyMs = [string]$s.LatencyMs
            FailureClass = [string]$s.FailureClass
        })
    }
    if ($rows.Count -eq 0) { return 0 }
    $rows | Export-Csv -LiteralPath $Path -NoTypeInformation -Encoding UTF8
    return $rows.Count
}

function Get-CombinedEvents([int]$Limit = 200) {
    $events = New-Object System.Collections.ArrayList
    foreach ($h in (Get-AutoHistory)) {
        [void]$events.Add([pscustomobject]@{
            Timestamp = [string]$h.Timestamp
            Type = 'AUTO'
            Module = [string]$h.Module
            Summary = "$(if ($h.From) {$h.From} else {'?'}) → $(if ($h.To) {$h.To} else {'?'})"
            Detail = Get-DecisionUiText ([string]$h.Reason)
        })
    }
    foreach ($s in (Read-JsonLines -Path $SelfTestHistoryFile -Tail 100)) {
        $ts = ''
        foreach ($p in @('Timestamp','At','UpdatedAt')) { if ($s.$p) { $ts = [string]$s.$p; break } }
        $state = if ($s.State) { [string]$s.State } elseif ($s.Result) { [string]$s.Result } else { 'UNKNOWN' }
        [void]$events.Add([pscustomobject]@{
            Timestamp = $ts
            Type = 'SELFTEST'
            Module = ''
            Summary = "Самопроверка только для чтения: $state"
            Detail = 'Автоматическая или ручная самопроверка движка V6.5 только для чтения.'
        })
    }
    foreach ($v in (Read-V7EventRecords -Path $V7EventsFile -Tail 500)) {
        [void]$events.Add([pscustomobject]@{
            Timestamp=[string]$v.Timestamp; Type='V7'; Module=[string]$v.Module;
            Summary=[string]$v.Summary; Detail=("[$([string]$v.Severity)] $([string]$v.Source) · $([string]$v.Detail)")
        })
    }
    $ordered = @($events | Sort-Object @{Expression={ try { [datetime]$_.Timestamp } catch { [datetime]::MinValue } }; Descending=$true})
    if ($ordered.Count -gt $Limit) { return @($ordered[0..($Limit-1)]) }
    return $ordered
}

function Save-ConfigSnapshot($Config) {
    if (-not (Test-CustomDefinitionsForConfig $Config)) { return $false }
    $mutex = $null
    $acquired = $false
    try {
        $mutex = New-Object System.Threading.Mutex($false, $MutationMutexName)
        try { $acquired = $mutex.WaitOne(15000, $false) }
        catch [System.Threading.AbandonedMutexException] { $acquired = $true }
        if (-not $acquired) { throw 'Истекло время ожидания блокировки изменения VPS Control.' }

        if (Test-Path -LiteralPath $ConfigFile) {
            Copy-Item -LiteralPath $ConfigFile -Destination $ConfigBackupFile -Force -ErrorAction SilentlyContinue
        }
        $h = [ordered]@{ Version = $EngineVersion }
        foreach ($module in $ModuleNames) {
            $fallback = if ($ModuleDefaultModes.ContainsKey($module)) { [string]$ModuleDefaultModes[$module] } else { 'DIRECT' }
            $h[$module] = Normalize-Mode ([string]$Config.$module) $fallback
        }
        $json = ([pscustomobject]$h) | ConvertTo-Json -Depth 5
        Write-TextAtomic -Path $ConfigFile -Text $json
        Write-UiLog 'Routing config saved by V7 UI.'
        Write-UiEvent 'CONFIG' 'Маршрутизация сохранена' 'Конфигурация сохранена интерфейсом V7.'
        return $true
    }
    catch {
        Write-UiLog "Routing config save failed: $($_.Exception.Message)"
        [System.Windows.Forms.MessageBox]::Show("Не удалось сохранить маршрутизацию.`r`n`r`n$($_.Exception.Message)", 'VPS Control Center', 'OK', 'Error') | Out-Null
        return $false
    }
    finally {
        if ($acquired -and $mutex) { try { $mutex.ReleaseMutex() } catch { } }
        if ($mutex) { try { $mutex.Dispose() } catch { } }
    }
}

function Get-LastSelfTestUi {
    $items = Read-JsonLines -Path $SelfTestHistoryFile -Tail 10
    if ($items.Count -eq 0) { return [pscustomobject]@{ State='NONE'; Text='Ещё не выполнялся'; Detail='История самопроверок пока пуста.' } }
    $last = $items[$items.Count - 1]
    $state = ([string]$last.State).ToUpperInvariant()
    if (-not $state -and $last.Result) { $state = ([string]$last.Result).ToUpperInvariant() }
    $ts = ''
    foreach ($p in @('Timestamp','At','UpdatedAt')) {
        if ($last.$p) { $ts = [string]$last.$p; break }
    }
    $when = ''
    if ($ts) { try { $when = ([datetime]$ts).ToString('dd.MM HH:mm') } catch { $when = $ts } }
    switch ($state) {
        'PASS' { $txt = 'Успешно' }
        'WARN' { $txt = 'Есть предупреждение' }
        'FAIL' { $txt = 'Ошибка' }
        default { $txt = 'Результат неизвестен' }
    }
    if ($when) { $txt += " · $when" }
    return [pscustomobject]@{ State=$state; Text=$txt; Detail='Последняя автоматическая или ручная самопроверка только для чтения.' }
}

function Get-DecisionUiText([string]$Reason) {
    $r = ($Reason + '').ToUpperInvariant()
    if (-not $r) { return 'Причина не записана' }
    switch ($r) {
        'CONFIG_DIRECT' { return 'В настройках выбран прямой маршрут.' }
        'CONFIG_VPS' { return 'В настройках принудительно выбран VPS.' }
        'AUTO_DIRECT_HEALTHY' { return 'Авто: прямой маршрут исправен и достаточно быстрый — VPS не нужен.' }
        'AUTO_DIRECT_PREFERRED' { return 'Авто: сравнение не показало достаточного преимущества VPS — оставлен прямой маршрут.' }
        'AUTO_DIRECT_FAILED' { return 'Авто: прямой маршрут не прошёл проверку, поэтому выбран рабочий VPS.' }
        'AUTO_VPS_FASTER' { return 'Авто: VPS показал устойчивое и существенное преимущество по задержке.' }
        'AUTO_VPS_UNAVAILABLE' { return 'Авто: VPS недоступен; сохранён прямой маршрут с его текущим состоянием.' }
    }
    if ($r -match 'FAILBACK|RECOVER') { return 'Авто: прямой маршрут устойчиво восстановился — выполнен возврат с VPS.' }
    if ($r -match 'FAILOVER' -and $r -match 'LATENCY') { return 'Авто: выполнено переключение на VPS из-за устойчивого выигрыша по задержке.' }
    if ($r -match 'FAILOVER|DIRECT_FAILED|FAILURE') { return 'Авто: прямой маршрут несколько раз подряд не прошёл проверку — выполнен переход на VPS.' }
    if ($r -match 'VPS_FASTER|LATENCY') { return 'Авто: VPS оказался существенно быстрее прямого маршрута.' }
    if ($r -match 'DIRECT_HEALTHY|DIRECT_PREFERRED') { return 'Авто: прямой маршрут исправен и предпочтителен.' }
    if ($r -match 'CONFIG_VPS') { return 'Применён явно заданный маршрут через VPS.' }
    if ($r -match 'CONFIG_DIRECT') { return 'Применён явно заданный прямой маршрут.' }
    return "Техническая причина: $Reason"
}

function Get-LastReasonUiText([string]$Reason) {
    $r = ($Reason + '').ToUpperInvariant()
    switch ($r) {
        'MANUAL_APPLY' { return 'сохранённая конфигурация применена вручную' }
        'MANUAL_DIRECT' { return 'включён временный режим «всё напрямую»' }
        'INITIAL' { return 'начальное состояние' }
        default {
            if ($r -match '^WATCHDOG_') { return 'маршрут обновлён watchdog по результатам проверки' }
            if ($Reason) { return $Reason }
            return 'причина не записана'
        }
    }
}

function Get-AutoHistory {
    $result = New-Object System.Collections.ArrayList
    $incidents = Read-JsonLines -Path $IncidentFile -Tail 500
    foreach ($item in $incidents) {
        $module = [string]$item.Module
        $reason = [string]$item.Reason
        if (-not $module -or -not $reason) { continue }
        $ts = ''
        foreach ($p in @('Timestamp','At','CreatedAt')) { if ($item.$p) { $ts = [string]$item.$p; break } }
        $from = [string]$item.From
        $to = [string]$item.To
        $detail = [string]$item.Detail
        [void]$result.Add([pscustomobject]@{
            Timestamp = $ts
            Module = $module
            From = $from
            To = $to
            Reason = $reason
            Detail = $detail
        })
    }

    if ($result.Count -eq 0 -and (Test-Path -LiteralPath $DecisionLogFile)) {
        try {
            $lines = Get-Content -LiteralPath $DecisionLogFile -Encoding UTF8 -Tail 500
            foreach ($line in $lines) {
                if ($line -notmatch 'reason=AUTO_') { continue }
                if ($line -match '^(?<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+module=(?<m>\S+) from=(?<f>\S+) to=(?<t>\S+) reason=(?<r>\S+)(?: detail=(?<d>.*))?$') {
                    [void]$result.Add([pscustomobject]@{
                        Timestamp = $Matches.ts
                        Module = $Matches.m
                        From = $Matches.f
                        To = $Matches.t
                        Reason = $Matches.r
                        Detail = $Matches.d
                    })
                }
            }
        }
        catch { }
    }
    return $result
}

function Get-LatestIncidentForModule([string]$Module) {
    $history = Get-AutoHistory
    for ($i = $history.Count - 1; $i -ge 0; $i--) {
        if ([string]$history[$i].Module -eq $Module) { return $history[$i] }
    }
    return $null
}

function Get-AutoExplanation($Config, $Runtime, [string]$Module) {
    $mode = Normalize-Mode ([string]$Config.$Module) 'DIRECT'
    if ($Runtime -and [string]$Runtime.Override -eq 'DIRECT') {
        return 'Сейчас действует временный общий режим: все управляемые сервисы направлены напрямую. Сохранённая конфигурация не изменена.'
    }
    if ($mode -eq 'DIRECT') { return 'В настройках выбран режим «Напрямую». VPS для этого сервиса не используется.' }
    if ($mode -eq 'VPS') { return 'В настройках выбран режим «Через VPS». Контроллер обязан использовать VPS и проверяет его доступность.' }
    if (-not $Runtime) { return 'Режим «Авто» включён, но фактический runtime ещё не прочитан.' }

    $auto = $Runtime.AutoState.$Module
    $decision = if ($auto -and $auto.LastDecision) { [string]$auto.LastDecision } else { '' }
    $effective = [string]$Runtime.Effective.$Module
    $base = Get-DecisionUiText $decision
    if (-not $decision -or $decision -eq 'INITIAL') {
        $incident = Get-LatestIncidentForModule $Module
        if ($incident) { $base = Get-DecisionUiText ([string]$incident.Reason) }
        elseif ($effective -eq 'DIRECT') { $base = 'Авто: сейчас используется прямой маршрут; записанного события переключения пока нет.' }
        else { $base = 'Авто: сейчас используется VPS; подробная причина будет взята из следующего события/решения watchdog.' }
    }

    $extra = @()
    if ($auto) {
        if ($auto.DirectFails -ne $null) { $extra += "счётчик ошибок DIRECT: $([int]$auto.DirectFails)" }
        if ($auto.DirectRecoveries -ne $null) { $extra += "счётчик восстановлений DIRECT: $([int]$auto.DirectRecoveries)" }
    }
    if ($extra.Count -gt 0) { $base += '  ' + ($extra -join '; ') + '.' }
    return $base
}

function Get-RouteShareText($Stats, [string]$Module) {
    if (-not $Stats -or -not $Stats.Modules -or -not $Stats.Modules.$Module) { return 'Недостаточно статистики' }
    $m = $Stats.Modules.$Module
    $direct = [double]$m.DirectSeconds
    $vps = [double]$m.VpsSeconds
    $total = $direct + $vps
    if ($total -le 0) { return 'Недостаточно статистики' }
    $d = [math]::Round(($direct / $total) * 100, 1)
    $v = [math]::Round(($vps / $total) * 100, 1)
    return "напрямую $d% · через VPS $v% · переключений: $([int]$m.Switches)"
}
