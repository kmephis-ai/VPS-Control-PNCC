#requires -Version 5.1
# VPS Control Center RC14 package integrity and local maintenance helpers.

function Cleanup-UiTempFiles {
    try {
        $cutoff = (Get-Date).AddDays(-7)
        foreach ($pattern in @('engine-*.out.txt','engine-*.err.txt','engine-sync-*.out.txt','engine-sync-*.err.txt','vps-*.out.txt','vps-*.err.txt','strict-browser-*.out.txt','strict-browser-*.err.txt','engine-upgrade-*.out.txt','engine-upgrade-*.err.txt','keenetic-*.out.txt','keenetic-*.err.txt','vm-gateway-*.out.txt','vm-gateway-*.err.txt')) {
            Get-ChildItem -LiteralPath $UiTempDir -Filter $pattern -File -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -lt $cutoff } |
                Remove-Item -Force -ErrorAction SilentlyContinue
        }
    }
    catch { Write-UiLog "Temporary file cleanup failed: $($_.Exception.Message)" }
}

function Test-PackageIntegrity {
    param([Parameter(Mandatory=$true)][string]$BaseDir)
    if([string]::IsNullOrWhiteSpace($BaseDir)){ throw 'BaseDir пакета V7 не задан.' }
    $errors = New-Object System.Collections.ArrayList
    $warnings = New-Object System.Collections.ArrayList
    $requiredItems = @(
        [pscustomobject]@{ Name='Генератор V6.5'; Path=$EngineUpgradePath },
        [pscustomobject]@{ Name='Каталог модулей V6.5'; Path=$BundledModulesFile },
        [pscustomobject]@{ Name='VPS Manager'; Path=$VpsManagerHelperPath },
        [pscustomobject]@{ Name='Keenetic helper'; Path=$KeeneticHelperPath },
        [pscustomobject]@{ Name='VM Gateway'; Path=$VmGatewayHelperPath },
        [pscustomobject]@{ Name='Strict Browser helper'; Path=$StrictBrowserHelperPath },
        [pscustomobject]@{ Name='Storage module'; Path=$StorageHelperPath },
        [pscustomobject]@{ Name='Events module'; Path=$EventsHelperPath },
        [pscustomobject]@{ Name='Demo module'; Path=$DemoHelperPath },
        [pscustomobject]@{ Name='Keenetic model module'; Path=$KeeneticModelHelperPath },
        [pscustomobject]@{ Name='Core module'; Path=$CoreHelperPath },
        [pscustomobject]@{ Name='Observability module'; Path=$ObservabilityHelperPath },
        [pscustomobject]@{ Name='Runtime module'; Path=$RuntimeHelperPath },
        [pscustomobject]@{ Name='Deep telemetry module'; Path=$DeepTelemetryHelperPath },
        [pscustomobject]@{ Name='Background evidence worker'; Path=$EvidenceWorkerPath },
        [pscustomobject]@{ Name='UI common module'; Path=$UiCommonHelperPath },
        [pscustomobject]@{ Name='Readiness module'; Path=$ReadinessHelperPath },
        [pscustomobject]@{ Name='Status Center module'; Path=$StatusCenterHelperPath },
        [pscustomobject]@{ Name='Consistency module'; Path=$ConsistencyHelperPath },
        [pscustomobject]@{ Name='Capability Truth'; Path=$CapabilityTruthPath },
        [pscustomobject]@{ Name='Maintenance module'; Path=$MaintenanceHelperPath }
    )
    if(-not $Demo){ $requiredItems = @([pscustomobject]@{ Name='Стабильный движок V6.3.1'; Path=$EngineSourcePath }) + $requiredItems }
    foreach ($item in $requiredItems) {
        if (-not (Test-Path -LiteralPath $item.Path -PathType Leaf)) { [void]$errors.Add("$($item.Name): не найден $($item.Path)") }
    }
    if (-not (Test-Path -LiteralPath $PowerShellExe -PathType Leaf)) { [void]$errors.Add("Windows PowerShell 5.1 не найден: $PowerShellExe") }
    try {
        $manifestPath = Join-Path $BaseDir 'VPS-Control-v7-SHA256.txt'
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { [void]$errors.Add('Не найден VPS-Control-v7-SHA256.txt.') }
        else {
            foreach($line in Get-Content -LiteralPath $manifestPath -ErrorAction Stop) {
                if(-not $line -or $line.TrimStart().StartsWith('#')){continue}
                if($line -notmatch '^([0-9a-fA-F]{64})\s+(.+)$'){[void]$errors.Add("Некорректная строка manifest: $line");continue}
                $expected=$Matches[1].ToUpperInvariant();$packageFile=Join-Path $BaseDir $Matches[2].Trim()
                if(-not(Test-Path -LiteralPath $packageFile -PathType Leaf)){[void]$errors.Add("Отсутствует файл пакета: $($Matches[2].Trim())");continue}
                $actual=(Get-FileSha256 $packageFile).ToUpperInvariant();if($actual -ne $expected){[void]$errors.Add("SHA-256 не совпадает: $($Matches[2].Trim())")}
            }
        }
    } catch { [void]$errors.Add("Ошибка SHA-256 проверки пакета: $($_.Exception.Message)") }
    try {
        if (Test-Path -LiteralPath $BundledModulesFile) {
            $catalog = Read-JsonFile $BundledModulesFile
            if (-not $catalog) { [void]$errors.Add('VPS-Control-v6.5-modules.json не читается как JSON.') }
            else {
                foreach ($module in $ModuleNames) {
                    if (-not $catalog.PSObject.Properties[$module]) { [void]$errors.Add("В каталоге модулей отсутствует $module.") }
                }
            }
        }
    }
    catch { [void]$errors.Add("Ошибка проверки каталога модулей: $($_.Exception.Message)") }
    try {
        $probe = Join-Path $UiTempDir '.write-test.tmp'
        [IO.File]::WriteAllText($probe,'ok',[Text.Encoding]::ASCII)
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
    }
    catch { [void]$errors.Add("Нет записи в папку состояния интерфейса: $UiStateDir") }
    if (-not $script:ChartsAvailable) { [void]$warnings.Add('Компонент Windows Forms DataVisualization недоступен: графики будут отключены, остальной интерфейс продолжит работу.') }
    return [pscustomobject]@{ Ok=($errors.Count -eq 0); Errors=@($errors); Warnings=@($warnings) }
}
