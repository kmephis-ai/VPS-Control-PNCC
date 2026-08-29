#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$OutputRoot = 'E:\!Chrome_Downloads'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Repo = 'kmephis-ai/VPS-Control-PNCC'
$PinnedExecutorCommit = '2837c624234cb2cf29fb0c0524759bd56c3e15e3'
$PinnedExecutorBlob = '1484442efe1b6495b2018e4ca39145a092bb109c'
$PinnedExecutorPath = 'tools/release/Invoke-PnccV701StableReleasePublication.ps1'
$RawUri = 'https://raw.githubusercontent.com/{0}/{1}/{2}' -f $Repo,$PinnedExecutorCommit,$PinnedExecutorPath
$RunId = [guid]::NewGuid().ToString('N')
$WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ('PNCC-WU090-PS51-HOTFIX-' + $RunId)
$OriginalPath = Join-Path $WorkRoot 'Invoke-PnccV701StableReleasePublication.original.ps1'
$PatchedPath = Join-Path $WorkRoot 'Invoke-PnccV701StableReleasePublication.ps1'

New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null

function Get-GitBlobSha1 {
    param([Parameter(Mandatory=$true)][string]$Path)
    $bytes = [IO.File]::ReadAllBytes($Path)
    $header = [Text.Encoding]::ASCII.GetBytes(('blob {0}' -f $bytes.Length) + [char]0)
    $stream = New-Object IO.MemoryStream
    try {
        $stream.Write($header,0,$header.Length)
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Position = 0
        $sha1 = [Security.Cryptography.SHA1]::Create()
        try { return ([BitConverter]::ToString($sha1.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
        finally { $sha1.Dispose() }
    }
    finally { $stream.Dispose() }
}

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri $RawUri -OutFile $OriginalPath
    $actualBlob = Get-GitBlobSha1 -Path $OriginalPath
    if ($actualBlob -ne $PinnedExecutorBlob) {
        throw ('PINNED_EXECUTOR_BLOB_MISMATCH expected={0} actual={1}' -f $PinnedExecutorBlob,$actualBlob)
    }
    Write-Host ('PINNED_EXECUTOR_BLOB_PASS=' + $actualBlob)

    $reader = New-Object IO.StreamReader($OriginalPath,[Text.Encoding]::UTF8,$true)
    try { $text = $reader.ReadToEnd() }
    finally { $reader.Dispose() }

    $pattern = '(?m)^    \$raw = @\(& \$script:GhPath @Arguments 2>&1\)\r?\n    \$code = \$LASTEXITCODE$'
    $matches = [regex]::Matches($text,$pattern)
    if ($matches.Count -ne 1) {
        throw ('PS51_NATIVE_COMMAND_PATCH_SITE_COUNT expected=1 actual=' + $matches.Count)
    }

    $replacement = @'
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = @(& $script:GhPath @Arguments 2>&1)
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
'@
    $patched = [regex]::Replace($text,$pattern,[System.Text.RegularExpressions.MatchEvaluator]{ param($m) $replacement },1)
    if ($patched -eq $text) { throw 'PS51_NATIVE_COMMAND_PATCH_NOT_APPLIED' }
    if (([regex]::Matches($patched,"\$ErrorActionPreference = 'Continue'" )).Count -ne 1) {
        throw 'PS51_NATIVE_COMMAND_PATCH_INVARIANT_FAILED'
    }

    Set-Content -LiteralPath $PatchedPath -Value $patched -Encoding UTF8
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($PatchedPath,[ref]$tokens,[ref]$errors)
    if (@($errors).Count -ne 0) {
        @($errors) | ForEach-Object { Write-Error $_.Message }
        throw 'PATCHED_EXECUTOR_PS51_AST_FAILED'
    }
    Write-Host 'PATCHED_EXECUTOR_PS51_AST=PASS'

    $args = @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$PatchedPath,'-OutputRoot',$OutputRoot)
    if ($Execute) { $args += '-Execute' }
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" @args
    $rc = $LASTEXITCODE
    Write-Host ('PATCHED_EXECUTOR_EXIT_CODE=' + $rc)
    exit $rc
}
finally {
    try {
        if (Test-Path -LiteralPath $WorkRoot) { Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction Stop }
    }
    catch {
        Write-Host ('PS51_HOTFIX_TEMP_CLEANUP_WARNING=' + $_.Exception.Message)
    }
}
