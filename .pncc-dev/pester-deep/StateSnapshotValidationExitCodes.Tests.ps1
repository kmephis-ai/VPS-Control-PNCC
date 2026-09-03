#requires -Version 5.1

Describe 'PIPE-WU-169 State Snapshot validation process exit codes' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $wrapper = Join-Path $repoRoot 'tools\cli\Invoke-PnccStateSnapshotInputCheck.ps1'
        $example = Join-Path $repoRoot 'tools\cli\examples\state-input.example.json'
        $powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

        function Invoke-PnccValidationChild {
            param([string]$ScriptPath, [string]$InputPath)
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $powershellExe
            $psi.Arguments = ('-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -InputPath "{1}" -Json' -f $ScriptPath, $InputPath)
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            $psi.RedirectStandardOutput = $true
            $psi.RedirectStandardError = $true
            $process = New-Object System.Diagnostics.Process
            $process.StartInfo = $psi
            [void]$process.Start()
            $stdout = $process.StandardOutput.ReadToEnd()
            $stderr = $process.StandardError.ReadToEnd()
            $process.WaitForExit()
            [pscustomobject]@{ ExitCode = $process.ExitCode; StdOut = $stdout.Trim(); StdErr = $stderr.Trim() }
        }
    }

    It 'returns exit 0 and normalized VALID machine output for valid input' {
        $r = Invoke-PnccValidationChild -ScriptPath $wrapper -InputPath $example
        $r.ExitCode | Should -Be 0
        $r.StdErr | Should -Be ''
        $result = $r.StdOut | ConvertFrom-Json
        $result.SchemaVersion | Should -Be 1
        $result.Contract | Should -Be 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION'
        $result.ReadOnly | Should -BeTrue
        $result.Valid | Should -BeTrue
        $result.Code | Should -Be 'VALID'
    }

    It 'returns exit 2 for malformed caller input without leaking path or parser details' {
        $path = Join-Path $TestDrive 'private-malformed.json'
        Set-Content -LiteralPath $path -Value '{ broken-json' -Encoding UTF8
        $r = Invoke-PnccValidationChild -ScriptPath $wrapper -InputPath $path
        $r.ExitCode | Should -Be 2
        $r.StdErr | Should -Be ''
        $result = $r.StdOut | ConvertFrom-Json
        $result.Valid | Should -BeFalse
        $result.Code | Should -Be 'JSON_INVALID'
        $r.StdOut | Should -Not -Match [regex]::Escape($path)
        $r.StdOut | Should -Not -Match 'broken-json|ConvertFrom-Json'
    }

    It 'returns exit 2 for a missing caller input without echoing its path' {
        $path = Join-Path $TestDrive 'private-missing.json'
        $r = Invoke-PnccValidationChild -ScriptPath $wrapper -InputPath $path
        $r.ExitCode | Should -Be 2
        $r.StdErr | Should -Be ''
        $result = $r.StdOut | ConvertFrom-Json
        $result.Valid | Should -BeFalse
        $result.Code | Should -Be 'INPUT_NOT_FOUND'
        $r.StdOut | Should -Not -Match [regex]::Escape($path)
    }

    It 'returns exit 3 with normalized dependency failure when validator is absent' {
        $isolated = Join-Path $TestDrive 'isolated'
        New-Item -ItemType Directory -Path $isolated -Force | Out-Null
        $isolatedWrapper = Join-Path $isolated 'Invoke-PnccStateSnapshotInputCheck.ps1'
        Copy-Item -LiteralPath $wrapper -Destination $isolatedWrapper
        $r = Invoke-PnccValidationChild -ScriptPath $isolatedWrapper -InputPath $example
        $r.ExitCode | Should -Be 3
        $r.StdErr | Should -Be ''
        $result = $r.StdOut | ConvertFrom-Json
        $result.Valid | Should -BeFalse
        $result.Code | Should -Be 'VALIDATOR_DEPENDENCY_MISSING'
        $r.StdOut | Should -Not -Match [regex]::Escape($example)
    }

    It 'keeps existing composable validator free of process exit semantics' {
        $validator = Join-Path $repoRoot 'tools\cli\Test-PnccStateSnapshotInput.ps1'
        $text = Get-Content -LiteralPath $validator -Raw -Encoding UTF8
        $text | Should -Not -Match '(?m)^\s*exit\s+[0-9]+'
    }
}
