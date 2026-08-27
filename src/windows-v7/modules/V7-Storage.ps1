#requires -Version 5.1

function Resolve-V7DataRoot {
    param([Parameter(Mandatory=$true)][string]$BaseDir)
    $default = Join-Path $BaseDir 'VPS-Control-Data'
    $pointer = Join-Path $BaseDir 'VPS-Control-Data.location'
    if (-not (Test-Path -LiteralPath $pointer -PathType Leaf)) { return $default }
    try {
        $raw = ([IO.File]::ReadAllText($pointer,[Text.Encoding]::UTF8)).Trim()
        if (-not $raw) { return $default }
        $expanded = [Environment]::ExpandEnvironmentVariables($raw)
        if (-not [IO.Path]::IsPathRooted($expanded)) { $expanded = Join-Path $BaseDir $expanded }
        return [IO.Path]::GetFullPath($expanded)
    }
    catch { return $default }
}

function Initialize-V7StorageLayout {
    param(
        [Parameter(Mandatory=$true)][string]$BaseDir,
        [Parameter(Mandatory=$true)][string]$DataRoot
    )
    $dirs = [ordered]@{
        Root=$DataRoot
        Config=(Join-Path $DataRoot 'config')
        Secrets=(Join-Path $DataRoot 'secrets')
        Runtime=(Join-Path $DataRoot 'runtime')
        Telemetry=(Join-Path $DataRoot 'telemetry')
        Logs=(Join-Path $DataRoot 'logs')
        Backups=(Join-Path $DataRoot 'backups')
        Exports=(Join-Path $DataRoot 'exports')
        Nodes=(Join-Path $DataRoot 'nodes')
        Vps=(Join-Path $DataRoot 'nodes\vps')
        VpsHealth=(Join-Path $DataRoot 'nodes\vps\health')
        Keenetic=(Join-Path $DataRoot 'nodes\keenetic')
        Temp=(Join-Path $DataRoot 'temp')
        Migrations=(Join-Path $DataRoot 'migrations')
    }
    foreach($p in $dirs.Values){ if(-not(Test-Path -LiteralPath $p)){New-Item -ItemType Directory -Path $p -Force|Out-Null} }
    $vpsSecrets=Join-Path $dirs.Secrets 'vps'; if(-not(Test-Path -LiteralPath $vpsSecrets)){New-Item -ItemType Directory -Path $vpsSecrets -Force|Out-Null}

    $marker=Join-Path $dirs.Migrations 'layout-v2.complete'
    if(-not(Test-Path -LiteralPath $marker)){
        $fileMap=@{
            'ui-settings.json'=(Join-Path $dirs.Config 'ui-settings.json')
            'custom-routes.json'=(Join-Path $dirs.Config 'custom-routes.json')
            'vps-profiles.json'=(Join-Path $dirs.Vps 'vps-profiles.json')
            'active-vps.json'=(Join-Path $dirs.Vps 'active-vps.json')
            'engine-build-state.json'=(Join-Path $dirs.Runtime 'engine-build-state.json')
            'keenetic.json'=(Join-Path $dirs.Keenetic 'keenetic.json')
            'keenetic-entware.dpapi'=(Join-Path $dirs.Secrets 'keenetic-entware.dpapi')
            'ui.log'=(Join-Path $dirs.Logs 'ui.log')
            'launch.log'=(Join-Path $dirs.Logs 'launch.log')
        }
        foreach($name in $fileMap.Keys){
            $src=Join-Path $DataRoot $name;$dst=$fileMap[$name]
            if((Test-Path -LiteralPath $src -PathType Leaf) -and -not(Test-Path -LiteralPath $dst)){Copy-Item -LiteralPath $src -Destination $dst -Force}
        }
        $oldHealth=Join-Path $DataRoot 'vps-health'
        if(Test-Path -LiteralPath $oldHealth -PathType Container){Get-ChildItem -LiteralPath $oldHealth -File -ErrorAction SilentlyContinue|ForEach-Object{$dst=Join-Path $dirs.VpsHealth $_.Name;if(-not(Test-Path -LiteralPath $dst)){Copy-Item -LiteralPath $_.FullName -Destination $dst -Force}}}
        $oldSecrets=Join-Path $DataRoot 'vps-secrets'
        if(Test-Path -LiteralPath $oldSecrets -PathType Container){Get-ChildItem -LiteralPath $oldSecrets -File -ErrorAction SilentlyContinue|ForEach-Object{$dst=Join-Path $vpsSecrets $_.Name;if(-not(Test-Path -LiteralPath $dst)){Copy-Item -LiteralPath $_.FullName -Destination $dst -Force}}}
        [IO.File]::WriteAllText($marker,(Get-Date).ToString('o'),(New-Object Text.UTF8Encoding($true)))
    }
    return [pscustomobject]@{
        Root=$dirs.Root;Config=$dirs.Config;Secrets=$dirs.Secrets;Runtime=$dirs.Runtime;Telemetry=$dirs.Telemetry;Logs=$dirs.Logs;Backups=$dirs.Backups;Exports=$dirs.Exports;Nodes=$dirs.Nodes;Vps=$dirs.Vps;VpsHealth=$dirs.VpsHealth;Keenetic=$dirs.Keenetic;Temp=$dirs.Temp;Migrations=$dirs.Migrations;VpsSecrets=$vpsSecrets
    }
}

function Test-V7StorageHealth {
    param([Parameter(Mandatory=$true)]$Layout)
    $issues=New-Object Collections.ArrayList
    foreach($name in @('Root','Config','Secrets','Runtime','Telemetry','Logs','Backups','Exports','Nodes','Vps','Keenetic','Temp')){
        $p=[string]$Layout.$name
        if(-not(Test-Path -LiteralPath $p -PathType Container)){[void]$issues.Add("Нет каталога ${name}: $p")}
    }
    try{$probe=Join-Path $Layout.Temp ('.write-test-'+[guid]::NewGuid().ToString('N'));[IO.File]::WriteAllText($probe,'ok',[Text.Encoding]::ASCII);Remove-Item -LiteralPath $probe -Force}catch{[void]$issues.Add('Нет записи в хранилище: '+$_.Exception.Message)}
    $jsonFiles=@(
        (Join-Path $Layout.Config 'ui-settings.json'),(Join-Path $Layout.Config 'custom-routes.json'),
        (Join-Path $Layout.Vps 'vps-profiles.json'),(Join-Path $Layout.Vps 'active-vps.json'),
        (Join-Path $Layout.Keenetic 'keenetic.json')
    )
    foreach($p in $jsonFiles){if(Test-Path -LiteralPath $p){try{Get-Content -LiteralPath $p -Raw -ErrorAction Stop|ConvertFrom-Json|Out-Null}catch{[void]$issues.Add("Повреждён JSON: $p")}}}
    return [pscustomobject]@{Ok=($issues.Count -eq 0);Issues=@($issues);Root=[string]$Layout.Root}
}

function New-V7SafeBackup {
    param([Parameter(Mandatory=$true)][string]$BaseDir,[Parameter(Mandatory=$true)]$Layout)
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
    $stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
    $stage=Join-Path $Layout.Temp ('backup-'+$stamp+'-'+[guid]::NewGuid().ToString('N'))
    $zip=Join-Path $Layout.Backups ("VPS-Control-safe-$stamp.zip")
    New-Item -ItemType Directory -Path $stage -Force|Out-Null
    try{
        foreach($name in @('config','nodes')){
            $src=Join-Path $Layout.Root $name
            if(Test-Path -LiteralPath $src){Copy-Item -LiteralPath $src -Destination (Join-Path $stage $name) -Recurse -Force}
        }
        $eventFile=Join-Path $Layout.Logs 'events.jsonl';if(Test-Path -LiteralPath $eventFile){New-Item -ItemType Directory -Path (Join-Path $stage 'logs') -Force|Out-Null;Copy-Item -LiteralPath $eventFile -Destination (Join-Path $stage 'logs\events.jsonl') -Force}
        Get-ChildItem -LiteralPath $stage -Recurse -File -ErrorAction SilentlyContinue|Where-Object{$_.Extension -eq '.dpapi' -or $_.Name -match '(?i)secret|password|private'}|Remove-Item -Force -ErrorAction SilentlyContinue
        $meta=[pscustomobject]@{Version=1;CreatedAt=(Get-Date).ToString('o');Product='VPS Control Center';DataRoot=[string]$Layout.Root;SecretsIncluded=$false}
        [IO.File]::WriteAllText((Join-Path $stage 'backup-info.json'),($meta|ConvertTo-Json -Depth 4),(New-Object Text.UTF8Encoding($true)))
        if(Test-Path -LiteralPath $zip){Remove-Item -LiteralPath $zip -Force}
        [IO.Compression.ZipFile]::CreateFromDirectory($stage,$zip,[IO.Compression.CompressionLevel]::Optimal,$false)
        return $zip
    }
    finally{Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue}
}

function Set-V7DataRootPreference {
    param([Parameter(Mandatory=$true)][string]$BaseDir,[Parameter(Mandatory=$true)][string]$NewRoot,[string]$CurrentRoot,[switch]$CopyExisting)
    if(-not $NewRoot){throw 'Не выбрана папка данных.'}
    $full=[IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($NewRoot))
    if(-not(Test-Path -LiteralPath $full)){New-Item -ItemType Directory -Path $full -Force|Out-Null}
    if($CopyExisting -and $CurrentRoot -and (Test-Path -LiteralPath $CurrentRoot) -and ([IO.Path]::GetFullPath($CurrentRoot) -ne $full)){
        Get-ChildItem -LiteralPath $CurrentRoot -Force|ForEach-Object{$dst=Join-Path $full $_.Name;if(-not(Test-Path -LiteralPath $dst)){Copy-Item -LiteralPath $_.FullName -Destination $dst -Recurse -Force}}
    }
    $pointer=Join-Path $BaseDir 'VPS-Control-Data.location'
    [IO.File]::WriteAllText($pointer,$full,(New-Object Text.UTF8Encoding($true)))
    return $full
}
