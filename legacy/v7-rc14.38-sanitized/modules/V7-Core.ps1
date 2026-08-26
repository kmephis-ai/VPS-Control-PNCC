#requires -Version 5.1
# VPS Control Center RC14 internal module. Dot-sourced by VPS-Control-v7.ps1.

function Write-UiLog([string]$Text) {
    try {
        $line = '{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date), $Text
        Add-Content -LiteralPath $UiLogFile -Value $line -Encoding UTF8
    }
    catch { }
}

function Write-UiEvent([string]$Type,[string]$Summary,[string]$Detail='',[string]$Severity='INFO',[string]$Module='') {
    try { Write-V7EventRecord -Path $V7EventsFile -Type $Type -Source 'V7' -Severity $Severity -Module $Module -Summary $Summary -Detail $Detail } catch { }
}

function Read-TextFileSmart([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return '' }
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        if ($bytes.Length -eq 0) { return '' }

        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            return [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
        }
        if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
            return [System.Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2)
        }
        if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
            return [System.Text.Encoding]::BigEndianUnicode.GetString($bytes, 2, $bytes.Length - 2)
        }

        $zeroCount = 0
        foreach ($b in $bytes) { if ($b -eq 0) { $zeroCount++ } }
        if ($zeroCount -gt ($bytes.Length / 5)) {
            return [System.Text.Encoding]::Unicode.GetString($bytes)
        }

        try {
            $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
            return $strictUtf8.GetString($bytes)
        }
        catch {
            try {
                $oem = [System.Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage
                return [System.Text.Encoding]::GetEncoding($oem).GetString($bytes)
            }
            catch {
                return [System.Text.Encoding]::Default.GetString($bytes)
            }
        }
    }
    catch {
        return ''
    }
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
        if (-not $raw) { return $null }
        return ($raw | ConvertFrom-Json)
    }
    catch {
        try {
            $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
            if (-not $raw) { return $null }
            return ($raw | ConvertFrom-Json)
        }
        catch {
            Write-UiLog "JSON read failed: $Path :: $($_.Exception.Message)"
            return $null
        }
    }
}

function Read-JsonLines([string]$Path, [int]$Tail = 5000) {
    $result = New-Object System.Collections.ArrayList
    if (-not (Test-Path -LiteralPath $Path)) { return $result }
    try {
        $lines = Get-Content -LiteralPath $Path -Encoding UTF8 -Tail $Tail -ErrorAction Stop
        foreach ($line in $lines) {
            if (-not $line) { continue }
            try { [void]$result.Add(($line | ConvertFrom-Json)) } catch { }
        }
    }
    catch {
        Write-UiLog "JSONL read failed: $Path :: $($_.Exception.Message)"
    }
    return $result
}

function Normalize-Mode([string]$Mode, [string]$Fallback) {
    if ($Mode) {
        $m = $Mode.Trim().ToUpperInvariant()
        if ($ValidModes -contains $m) { return $m }
    }
    return $Fallback
}

function Get-ModuleUiName([string]$Module) {
    if ($ModuleUiNames.ContainsKey($Module)) { return [string]$ModuleUiNames[$Module] }
    return $Module
}

function Get-ModeUiName([string]$Mode) {
    $m = Normalize-Mode $Mode 'DIRECT'
    return [string]$ModeCodeToUi[$m]
}

function Get-HealthUiName([string]$Health) {
    switch (($Health + '').ToUpperInvariant()) {
        'HEALTHY' { return 'Исправно' }
        'DEGRADED' { return 'Ухудшено' }
        'FAILED' { return 'Ошибка' }
        default { return 'Неизвестно' }
    }
}

function Get-FailureUiName([string]$Failure) {
    $f = ($Failure + '').ToUpperInvariant()
    switch ($f) {
        '' { return 'Нет' }
        'NONE' { return 'Нет' }
        'DNS' { return 'Ошибка DNS' }
        'CONNECT' { return 'Нет соединения' }
        'TLS' { return 'Ошибка TLS' }
        'TIMEOUT' { return 'Тайм-аут' }
        'SOCKS' { return 'Ошибка SOCKS' }
        'SOCKS_IDENTITY' { return 'Неверный выходной IP VPS' }
        default {
            if ($f -match '^HTTP_(\d+)$') { return "HTTP $($Matches[1])" }
            return $f
        }
    }
}

function Get-FileSha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    try { return [string](Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash }
    catch {
        try {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try {
                $stream = [System.IO.File]::OpenRead($Path)
                try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','') }
                finally { $stream.Dispose() }
            }
            finally { $sha.Dispose() }
        }
        catch { return '' }
    }
}

function Write-TextAtomic([string]$Path, [string]$Text) {
    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    $temp = Join-Path $directory (([IO.Path]::GetFileName($Path)) + '.v7tmp.' + $PID + '.' + [guid]::NewGuid().ToString('N'))
    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    try {
        [IO.File]::WriteAllText($temp, $Text, $utf8Bom)
        if (Test-Path -LiteralPath $Path) {
            try {
                [IO.File]::Replace($temp, $Path, $null, $true)
                return
            }
            catch {
                Move-Item -LiteralPath $temp -Destination $Path -Force
                return
            }
        }
        Move-Item -LiteralPath $temp -Destination $Path -Force
    }
    finally {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }
}
