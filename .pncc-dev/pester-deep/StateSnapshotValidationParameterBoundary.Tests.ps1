#requires -Version 5.1

Describe 'PIPE-WU-171 State Snapshot validation process parameter boundary' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $wrapper = Join-Path $repoRoot 'tools\cli\Invoke-PnccStateSnapshotInputCheck.ps1'
        $example = Join-Path $repoRoot 'tools\cli\examples\state-input.example.json'
        $powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

        function Invoke-PnccParameterChild {
            param([string]$Arguments)
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $powershellExe
            $psi.Arguments = ('-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" {1}' -f $wrapper, $Arguments)
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
            [pscustomobject]@{ ExitCode=$process.ExitCode; StdOut=$stdout.Trim(); StdErr=$stderr.Trim() }
        }

        function Assert-NormalizedInvalid {
            param($Result, [string]$Code)
            $Result.ExitCode | Should -Be 2
            $Result.StdErr | Should -Be ''
            $o = $Result.StdOut | ConvertFrom-Json
            $o.SchemaVersion | Should -Be 1
            $o.Contract | Should -Be 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION'
            $o.ReadOnly | Should -BeTrue
            $o.Valid | Should -BeFalse
            $o.Code | Should -Be $Code
            $Result.StdOut | Should -Not -Match 'ParameterBinding|MissingMandatoryParameter|Cannot process argument|ValidateRange'
        }
    }

    It 'normalizes omitted InputPath without interactive mandatory prompt' {
        $r = Invoke-PnccParameterChild -Arguments '-Json'
        Assert-NormalizedInvalid -Result $r -Code 'INPUT_PATH_REQUIRED'
    }

    It 'normalizes whitespace InputPath as required' {
        $r = Invoke-PnccParameterChild -Arguments '-InputPath "   " -Json'
        Assert-NormalizedInvalid -Result $r -Code 'INPUT_PATH_REQUIRED'
    }

    It 'normalizes non-integer JsonDepth instead of binder conversion failure' {
        $r = Invoke-PnccParameterChild -Arguments ('-InputPath "{0}" -JsonDepth abc -Json' -f $example)
        Assert-NormalizedInvalid -Result $r -Code 'JSON_DEPTH_INVALID'
    }

    It 'normalizes out-of-range JsonDepth instead of ValidateRange failure' {
        $r = Invoke-PnccParameterChild -Arguments ('-InputPath "{0}" -JsonDepth 3 -Json' -f $example)
        Assert-NormalizedInvalid -Result $r -Code 'JSON_DEPTH_INVALID'
    }

    It 'uses default JsonDepth 12 and preserves valid process contract' {
        $r = Invoke-PnccParameterChild -Arguments ('-InputPath "{0}" -Json' -f $example)
        $r.ExitCode | Should -Be 0
        $r.StdErr | Should -Be ''
        $o = $r.StdOut | ConvertFrom-Json
        $o.Valid | Should -BeTrue
        $o.Code | Should -Be 'VALID'
    }

    It 'preserves an explicit valid JsonDepth' {
        $r = Invoke-PnccParameterChild -Arguments ('-InputPath "{0}" -JsonDepth 16 -Json' -f $example)
        $r.ExitCode | Should -Be 0
        $r.StdErr | Should -Be ''
        $o = $r.StdOut | ConvertFrom-Json
        $o.Valid | Should -BeTrue
        $o.Code | Should -Be 'VALID'
    }

    It 'removes binder-level validation attributes from the process wrapper only' {
        $text = Get-Content -LiteralPath $wrapper -Raw -Encoding UTF8
        $text | Should -Not -Match '\[Parameter\(Mandatory\s*=\s*\$true\)\]'
        $text | Should -Not -Match '\[ValidateNotNullOrEmpty\(\)\]'
        $text | Should -Not -Match '\[ValidateRange\(4,32\)\]'
        $text | Should -Match '\[object\]\$JsonDepth\s*=\s*12'
    }
}
