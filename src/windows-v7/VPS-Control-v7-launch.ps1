#requires -Version 5.1
[CmdletBinding()]
param([switch]$StartHidden,[switch]$Demo)

$LauncherVersion = '7.0.2'

$ErrorActionPreference='Stop'
$base=$PSScriptRoot
$fallbackLogDir=Join-Path $base 'VPS-Control-Data\logs'
try { if(-not(Test-Path -LiteralPath $fallbackLogDir)){New-Item -ItemType Directory -Path $fallbackLogDir -Force -ErrorAction Stop|Out-Null} }
catch { $fallbackLogDir=Join-Path $env:TEMP 'VPS-Control-v7'; if(-not(Test-Path -LiteralPath $fallbackLogDir)){New-Item -ItemType Directory -Path $fallbackLogDir -Force -ErrorAction SilentlyContinue|Out-Null} }
$script:LaunchLog=Join-Path $fallbackLogDir 'launch.log'
function Log([string]$Text){try{Add-Content -LiteralPath $script:LaunchLog -Encoding UTF8 -Value ('{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date),$Text)}catch{}}
function Fail([string]$Message,[int]$Code=10){
    Log "FAIL code=$Code :: $Message"
    try{Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue;[System.Windows.Forms.MessageBox]::Show("VPS Control Center не запущен.`r`n`r`n$Message`r`n`r`nЖурнал: $script:LaunchLog",'VPS Control Center',[System.Windows.Forms.MessageBoxButtons]::OK,[System.Windows.Forms.MessageBoxIcon]::Error)|Out-Null}catch{}
    exit $Code
}
function Sha([string]$Path){return ([string](Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()}

Log ("Launcher $LauncherVersion precheck start. demo="+[bool]$Demo)
# Verify package BEFORE dot-sourcing any helper from the package.
$manifest=Join-Path $base 'VPS-Control-v7-SHA256.txt'
if(-not(Test-Path -LiteralPath $manifest -PathType Leaf)){Fail 'Не найден файл контрольных сумм VPS-Control-v7-SHA256.txt.' 11}
foreach($line in Get-Content -LiteralPath $manifest -ErrorAction Stop){
    if(-not $line -or $line.TrimStart().StartsWith('#')){continue}
    if($line -notmatch '^([0-9a-fA-F]{64})\s+(.+)$'){Fail "Некорректная строка manifest: $line" 12}
    $expected=$Matches[1].ToLowerInvariant();$name=$Matches[2].Trim();$path=Join-Path $base $name
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){Fail "Отсутствует файл пакета: $name" 13}
    $actual=Sha $path;if($actual -ne $expected){Fail "Контрольная сумма не совпала: $name`r`nОжидалось: $expected`r`nПолучено: $actual" 14}
}

# Parse every distributable PowerShell file BEFORE dot-sourcing any package helper.
# A parser defect in Storage (or another helper) must stop here with a controlled preflight error.
$scripts=@(
 'VPS-Control-v7-launch.ps1','VPS-Control-v7.ps1','VPS-Control-v7-evidence-worker.ps1','VPS-Control-v7-engine-upgrade.ps1','VPS-Control-v7-vps-manager.ps1','VPS-Control-v7-keenetic.ps1','VPS-Control-v7-vm-gateway.ps1','VPS-Control-v7-browser-strict.ps1','VPS-Control-v7-tunnel-manager.ps1',
 'modules\V7-Storage.ps1','modules\V7-Events.ps1','modules\V7-Demo.ps1','modules\V7-KeeneticModel.ps1','modules\V7-Core.ps1','modules\V7-Observability.ps1','modules\V7-Runtime.ps1','modules\V7-DeepTelemetry.ps1','modules\V7-UiCommon.ps1','modules\V7-Readiness.ps1','modules\V7-StatusCenter.ps1','modules\V7-Consistency.ps1','modules\V7-Maintenance.ps1','modules\V7-Tunnels.ps1'
)
foreach($name in $scripts){$path=Join-Path $base $name;if(-not(Test-Path -LiteralPath $path -PathType Leaf)){Fail "Не найден обязательный скрипт: $name" 15};$tokens=$null;$errors=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors);if($errors -and $errors.Count){$detail=($errors|ForEach-Object{"строка $($_.Extent.StartLineNumber): $($_.Message)"}) -join "`r`n";Fail "PowerShell AST-проверка не пройдена: $name`r`n$detail" 16}}
Log 'Package PowerShell AST preflight PASS.'

$storageHelper=Join-Path $base 'modules\V7-Storage.ps1'
if(-not(Test-Path -LiteralPath $storageHelper -PathType Leaf)){Fail 'Не найден modules\V7-Storage.ps1.' 15}
. $storageHelper
$uiDir=Resolve-V7DataRoot -BaseDir $base
if(-not(Test-Path -LiteralPath $uiDir)){New-Item -ItemType Directory -Path $uiDir -Force|Out-Null}

# One-time legacy copy. Old data is deliberately left untouched as rollback evidence.
$legacyUiDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v7'
$preMigrationDir=Join-Path $uiDir 'migrations'
if(-not(Test-Path -LiteralPath $preMigrationDir)){New-Item -ItemType Directory -Path $preMigrationDir -Force|Out-Null}
$migrationMarker=Join-Path $preMigrationDir '.migrated-from-localappdata-v1'
if((Test-Path -LiteralPath $legacyUiDir -PathType Container) -and -not(Test-Path -LiteralPath $migrationMarker)){
    try {
        Get-ChildItem -LiteralPath $legacyUiDir -Force -ErrorAction Stop | ForEach-Object {$dst=Join-Path $uiDir $_.Name;if(-not(Test-Path -LiteralPath $dst)){Copy-Item -LiteralPath $_.FullName -Destination $dst -Recurse -Force -ErrorAction Stop}}
        [IO.File]::WriteAllText($migrationMarker,(Get-Date).ToString('o'),(New-Object Text.UTF8Encoding($true)))
    } catch { Fail ("Не удалось скопировать legacy-данные V7: "+$_.Exception.Message) 9 }
}
$layout=Initialize-V7StorageLayout -BaseDir $base -DataRoot $uiDir
$script:LaunchLog=Join-Path $layout.Logs 'launch.log'
Log ("Package SHA check PASS. data="+$uiDir)

if(-not $Demo){
    $legacy=Join-Path $base 'VPS-Control-v6.3.1.ps1';if(-not(Test-Path -LiteralPath $legacy -PathType Leaf)){Fail 'Рядом с V7 отсутствует стабильный VPS-Control-v6.3.1.ps1. V7 не содержит его копию и не стартует в рабочем режиме без rollback-базы.' 17}
    $tokens=$null;$errors=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($legacy,[ref]$tokens,[ref]$errors);if($errors -and $errors.Count){Fail ('Стабильный V6.3.1 не прошёл AST-проверку: '+(($errors|ForEach-Object{$_.Message}) -join '; ')) 18}
}
$modules=Join-Path $base 'VPS-Control-v6.5-modules.json';try{$doc=Get-Content -LiteralPath $modules -Raw -ErrorAction Stop|ConvertFrom-Json}catch{Fail "Каталог модулей повреждён: $($_.Exception.Message)" 19}
foreach($m in @('OpenAI','GitHub','DevPackages','Firefox','Claude','Gemini','Docker','Telegram','YandexBrowser','Edge','CustomExe','CustomSite')){if(-not $doc.PSObject.Properties[$m]){Fail "В каталоге модулей отсутствует $m." 20}}
$storageHealth=Test-V7StorageHealth -Layout $layout;if(-not $storageHealth.Ok){Fail ('Хранилище V7 не прошло стартовую проверку: '+(@($storageHealth.Issues)-join '; ')) 21}

# Verify the small set of framework primitives used during initial UI composition.
# This complements AST/source checks: namespace/type availability is a runtime concern.
try {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
    Add-Type -AssemblyName System.Drawing -ErrorAction Stop
    $null = New-Object -TypeName System.Windows.Forms.Padding -ArgumentList 1
    $null = New-Object -TypeName System.Drawing.Point -ArgumentList 1,1
    $null = New-Object -TypeName System.Drawing.Size -ArgumentList 1,1
    $null = New-Object -TypeName System.Drawing.Font -ArgumentList 'Segoe UI',8
    Log 'WinForms primitive type preflight PASS.'
} catch { Fail ('WinForms type preflight не пройден: '+$_.Exception.Message) 22 }

$main=Join-Path $base 'VPS-Control-v7.ps1';Log 'AST, storage and WinForms type checks PASS. Starting main UI.'
try{
    if($Demo){if($StartHidden){& $main -StartHidden -Demo}else{& $main -Demo}}
    else{if($StartHidden){& $main -StartHidden}else{& $main}}
    Log 'Main UI exited normally.';exit 0
}catch{Log "Main UI unhandled error: $($_.Exception.ToString())";Fail "Необработанная ошибка интерфейса: $($_.Exception.Message)" 30}
