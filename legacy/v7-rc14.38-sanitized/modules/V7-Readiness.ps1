#requires -Version 5.1
# Read-only local environment/readiness inspection for VPS Control Center RC14.11.

function Find-V7Executable {
    param([string[]]$Candidates,[string[]]$CommandName=@())
    foreach($p in @($Candidates)){
        if($p -and (Test-Path -LiteralPath $p -PathType Leaf)){ return [string]$p }
    }
    foreach($name in @($CommandName)){
        if(-not $name){continue}
        try { $c=Get-Command $name -ErrorAction SilentlyContinue; if($c -and $c.Source){ return [string]$c.Source } } catch { }
    }
    return ''
}

function Get-V7LegacyPuttyPath {
    param([string]$EngineSourcePath,[string]$BaseDir='')
    # RC14.11: the application root is authoritative for a colocated portable
    # toolchain. Historical absolute paths from V6.3.1 are fallback only.
    if(-not $BaseDir -and $EngineSourcePath){try{$BaseDir=Split-Path -Parent $EngineSourcePath}catch{}}
    foreach($candidate in @(
        $(if($BaseDir){Join-Path $BaseDir 'PuTTY PORTABLE\putty_portable.exe'}else{''}),
        $(if($BaseDir){Join-Path $BaseDir 'PuTTY PORTABLE\putty.exe'}else{''}),
        $(if($BaseDir){Join-Path $BaseDir 'putty_portable.exe'}else{''}),
        $(if($BaseDir){Join-Path $BaseDir 'putty.exe'}else{''})
    )){
        try{if($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)){return [string]$candidate}}catch{}
    }
    if(-not $EngineSourcePath -or -not(Test-Path -LiteralPath $EngineSourcePath -PathType Leaf)){return ''}
    try{
        $raw=Get-Content -LiteralPath $EngineSourcePath -Raw -ErrorAction Stop
        $m=[regex]::Match($raw,"(?m)^\s*\`$PuttyPath\s*=\s*'([^']+)'\s*$")
        if($m.Success -and (Test-Path -LiteralPath $m.Groups[1].Value -PathType Leaf)){return [string]$m.Groups[1].Value}
    }catch{}
    return ''
}

function Find-V7RunningProcessExecutable {
    param([string[]]$ProcessName=@())
    foreach($name in @($ProcessName)){
        if(-not $name){continue}
        try{
            foreach($proc in @(Get-Process -Name $name -ErrorAction SilentlyContinue)){
                try{$path=[string]$proc.MainModule.FileName;if($path -and(Test-Path -LiteralPath $path -PathType Leaf)){return $path}}catch{}
            }
        }catch{}
    }
    return ''
}

function Get-V7EnvironmentReadiness {
    param(
        [Parameter(Mandatory=$true)][string]$BaseDir,
        [Parameter(Mandatory=$true)][string]$PowerShellExe,
        [Parameter(Mandatory=$true)][string]$EngineSourcePath,
        [Parameter(Mandatory=$true)][string]$EnginePath,
        [Parameter(Mandatory=$true)][string]$StateDir,
        [Parameter(Mandatory=$true)]$StorageLayout,
        [switch]$Demo
    )
    $rows=New-Object Collections.ArrayList
    function Add-Row([string]$Name,[bool]$Ok,[string]$Detail,[bool]$Required=$false){
        [void]$rows.Add([pscustomobject]@{Component=$Name;Ok=$Ok;Required=$Required;Detail=$Detail})
    }

    $psOk=(Test-Path -LiteralPath $PowerShellExe -PathType Leaf)
    Add-Row 'Windows PowerShell 5.1' $psOk $(if($psOk){"$($PSVersionTable.PSVersion) · $PowerShellExe"}else{"не найден: $PowerShellExe"}) $true

    if($Demo){ Add-Row 'Rollback V6.3.1' $true 'ДЕМО: не требуется для синтетического режима.' $false }
    else { $ok=Test-Path -LiteralPath $EngineSourcePath -PathType Leaf; Add-Row 'Rollback V6.3.1' $ok $(if($ok){$EngineSourcePath}else{'стабильный VPS-Control-v6.3.1.ps1 не найден рядом с V7'}) $true }

    $generated=Test-Path -LiteralPath $EnginePath -PathType Leaf
    Add-Row 'Расширенный V6.5' $generated $(if($generated){$EnginePath}else{'ещё не сгенерирован или отсутствует; V7 создаёт его из V6.3.1'}) $false

    $prox=Find-V7Executable -Candidates @(
        (Join-Path ${env:ProgramFiles(x86)} 'Proxifier\Proxifier.exe'),
        (Join-Path $env:ProgramFiles 'Proxifier\Proxifier.exe')
    ) -CommandName 'Proxifier.exe'
    Add-Row 'Proxifier' ([bool]$prox) $(if($prox){$prox}else{'не найден; VPS-маршруты приложений работать не будут'}) $true

    $legacyPutty=Get-V7LegacyPuttyPath -EngineSourcePath $EngineSourcePath -BaseDir $BaseDir
    $legacyPuttyDir=$(if($legacyPutty){Split-Path -Parent $legacyPutty}else{''})
    $putty=Find-V7Executable -Candidates @(
        $legacyPutty,
        (Join-Path $env:ProgramFiles 'PuTTY\putty.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'PuTTY\putty.exe')
    ) -CommandName @('putty.exe','putty_portable.exe')
    Add-Row 'PuTTY' ([bool]$putty) $(if($putty){$putty}else{'не найден; legacy saved session/интерактивный SSH недоступны'}) $false
    $plink=Find-V7Executable -Candidates @(
        $(if($legacyPuttyDir){Join-Path $legacyPuttyDir 'plink.exe'}else{''}),
        $(if($legacyPuttyDir){Join-Path $legacyPuttyDir 'plink64.exe'}else{''}),
        $(if($legacyPuttyDir){Join-Path $legacyPuttyDir 'plink_portable.exe'}else{''}),
        (Join-Path $env:ProgramFiles 'PuTTY\plink.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'PuTTY\plink.exe')
    ) -CommandName @('plink.exe','plink64.exe','plink_portable.exe')
    Add-Row 'plink' ([bool]$plink) $(if($plink){$plink}else{'не найден; автоматизация VPS/Keenetic по SSH будет недоступна'}) $false
    $pageant=Find-V7Executable -Candidates @(
        $(if($legacyPuttyDir){Join-Path $legacyPuttyDir 'pageant.exe'}else{''}),
        (Join-Path $env:ProgramFiles 'PuTTY\pageant.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'PuTTY\pageant.exe')
    ) -CommandName 'pageant.exe'
    Add-Row 'Pageant' ([bool]$pageant) $(if($pageant){$pageant}else{'опционально; нужен только для режима SSH Agent'}) $false

    $git=Find-V7Executable -Candidates @() -CommandName 'git.exe'; Add-Row 'Git' ([bool]$git) $(if($git){$git}else{'не найден; GitHub READ diagnostics будут ограничены'}) $false
    $gh=Find-V7Executable -Candidates @() -CommandName 'gh.exe'; Add-Row 'GitHub CLI' ([bool]$gh) $(if($gh){$gh}else{'не найден; не критично для основной маршрутизации'}) $false

    $hyper=$false;try{$hyper=[bool](Get-Command Get-VM -ErrorAction SilentlyContinue)}catch{}
    Add-Row 'Hyper-V PowerShell' $hyper $(if($hyper){'cmdlet Get-VM доступен'}else{'не найден; VM Gateway остаётся опционально недоступным'}) $false

    $edge=Find-V7Executable -Candidates @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe')
    ) -CommandName 'msedge.exe'
    Add-Row 'Microsoft Edge' ([bool]$edge) $(if($edge){$edge}else{'не обнаружен в стандартных путях'}) $false

    $yandex=Find-V7Executable -Candidates @(
        (Join-Path $env:LOCALAPPDATA 'Yandex\YandexBrowser\Application\browser.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Yandex\YandexBrowser\Application\browser.exe'),
        (Join-Path $env:ProgramFiles 'Yandex\YandexBrowser\Application\browser.exe'),
        (Find-V7RunningProcessExecutable -ProcessName @('browser','yandexbrowser'))
    ) -CommandName 'browser.exe'
    Add-Row 'Яндекс Браузер' ([bool]$yandex) $(if($yandex){$yandex}else{'не обнаружен в стандартных путях'}) $false

    $storage=Test-V7StorageHealth -Layout $StorageLayout
    Add-Row 'Хранилище V7' ([bool]$storage.Ok) $(if($storage.Ok){[string]$storage.Root}else{(@($storage.Issues)-join '; ')}) $true
    $stateOk=Test-Path -LiteralPath $StateDir -PathType Container
    Add-Row 'Runtime state' $stateOk $(if($stateOk){$StateDir}else{'каталог runtime пока отсутствует'}) $(if($Demo){$false}else{$true})

    $requiredProblems=@($rows|Where-Object{$_.Required -and -not $_.Ok}).Count
    $optionalProblems=@($rows|Where-Object{-not $_.Required -and -not $_.Ok}).Count
    return [pscustomobject]@{
        Timestamp=(Get-Date).ToString('o'); Demo=[bool]$Demo; Rows=@($rows);
        RequiredProblems=$requiredProblems; OptionalProblems=$optionalProblems;
        Ready=($requiredProblems -eq 0)
    }
}

function Format-V7EnvironmentReadinessText {
    param([Parameter(Mandatory=$true)]$Report)
    $lines=New-Object Collections.ArrayList
    [void]$lines.Add('ПРОВЕРКА ЛОКАЛЬНОГО ОКРУЖЕНИЯ — ТОЛЬКО ЧТЕНИЕ')
    [void]$lines.Add(('Время: '+(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')))
    [void]$lines.Add(('Итог: '+$(if($Report.Ready){'ОБЯЗАТЕЛЬНАЯ БАЗА ГОТОВА'}else{'ЕСТЬ ОБЯЗАТЕЛЬНЫЕ ПРОБЛЕМЫ'})))
    [void]$lines.Add("Обязательных проблем: $($Report.RequiredProblems) · опциональных предупреждений: $($Report.OptionalProblems)")
    [void]$lines.Add('')
    foreach($r in @($Report.Rows)){
        $mark=if($r.Ok){'[OK]'}elseif($r.Required){'[FAIL]'}else{'[WARN]'}
        $req=if($r.Required){'обязательно'}else{'опционально'}
        [void]$lines.Add("$mark $($r.Component) · $req")
        [void]$lines.Add("     $($r.Detail)")
    }
    [void]$lines.Add('')
    [void]$lines.Add('Проверка ничего не устанавливает, не меняет маршруты, firewall, VPS, Keenetic или Hyper-V.')
    return ($lines -join "`r`n")
}
