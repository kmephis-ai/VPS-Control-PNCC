#requires -Version 5.1

Describe 'PIPE-WU-170 State Snapshot validation fail-closed exit taxonomy' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $wrapper = Join-Path $repoRoot 'tools\cli\Invoke-PnccStateSnapshotInputCheck.ps1'
        $powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

        function Invoke-PnccTaxonomyChild {
            param([bool]$Valid, [string]$Code)
            $isolated = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $isolated -Force | Out-Null
            $isolatedWrapper = Join-Path $isolated 'Invoke-PnccStateSnapshotInputCheck.ps1'
            $stub = Join-Path $isolated 'Test-PnccStateSnapshotInput.ps1'
            $input = Join-Path $isolated 'input.json'
            Copy-Item -LiteralPath $wrapper -Destination $isolatedWrapper
            Set-Content -LiteralPath $input -Value '{}' -Encoding UTF8
            $validLiteral = if ($Valid) { '$true' } else { '$false' }
            $escapedCode = $Code.Replace("'", "''")
            $stubText = @"
param([string]`$InputPath,[switch]`$Json,[int]`$JsonDepth=12)
[ordered]@{ SchemaVersion=1; Contract='PNCC_STATE_SNAPSHOT_INPUT_VALIDATION'; ReadOnly=`$true; Valid=$validLiteral; Code='$escapedCode' } | ConvertTo-Json -Compress
"@
            Set-Content -LiteralPath $stub -Value $stubText -Encoding UTF8

            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $powershellExe
            $psi.Arguments = ('-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -InputPath "{1}" -Json' -f $isolatedWrapper, $input)
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
    }

    It 'keeps VALID as the only successful validator result' {
        $r = Invoke-PnccTaxonomyChild -Valid $true -Code 'VALID'
        $r.ExitCode | Should -Be 0
        $r.StdErr | Should -Be ''
        $o = $r.StdOut | ConvertFrom-Json
        $o.Valid | Should -BeTrue
        $o.Code | Should -Be 'VALID'
    }

    It 'keeps known caller input failures on exit 2' {
        foreach ($code in @('INPUT_NOT_FOUND','INPUT_UNREADABLE','INPUT_EMPTY','JSON_INVALID','SEMANTIC_INVALID')) {
            $r = Invoke-PnccTaxonomyChild -Valid $false -Code $code
            $r.ExitCode | Should -Be 2
            $r.StdErr | Should -Be ''
            $o = $r.StdOut | ConvertFrom-Json
            $o.Valid | Should -BeFalse
            $o.Code | Should -Be $code
        }
    }

    It 'routes known validator dependency and internal contract failures to exit 3' {
        foreach ($code in @('VALIDATOR_DEPENDENCY_MISSING','SNAPSHOT_CONTRACT_INVALID','VALIDATION_FAILED')) {
            $r = Invoke-PnccTaxonomyChild -Valid $false -Code $code
            $r.ExitCode | Should -Be 3
            $r.StdErr | Should -Be ''
            $o = $r.StdOut | ConvertFrom-Json
            $o.Valid | Should -BeFalse
            $o.Code | Should -Be $code
        }
    }

    It 'fails closed for an unknown false validator code' {
        $r = Invoke-PnccTaxonomyChild -Valid $false -Code 'FUTURE_UNKNOWN_CODE'
        $r.ExitCode | Should -Be 3
        $r.StdErr | Should -Be ''
        $o = $r.StdOut | ConvertFrom-Json
        $o.Valid | Should -BeFalse
        $o.Code | Should -Be 'VALIDATOR_INTERNAL_FAILURE'
        $r.StdOut | Should -Not -Match 'FUTURE_UNKNOWN_CODE'
    }

    It 'fails closed for an inconsistent true non-VALID result' {
        $r = Invoke-PnccTaxonomyChild -Valid $true -Code 'JSON_INVALID'
        $r.ExitCode | Should -Be 3
        $r.StdErr | Should -Be ''
        $o = $r.StdOut | ConvertFrom-Json
        $o.Valid | Should -BeFalse
        $o.Code | Should -Be 'VALIDATOR_INTERNAL_FAILURE'
    }

    It 'keeps normalized output contract and avoids private path leakage' {
        $r = Invoke-PnccTaxonomyChild -Valid $false -Code 'SNAPSHOT_CONTRACT_INVALID'
        $o = $r.StdOut | ConvertFrom-Json
        $o.SchemaVersion | Should -Be 1
        $o.Contract | Should -Be 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION'
        $o.ReadOnly | Should -BeTrue
        $r.StdOut | Should -Not -Match [regex]::Escape($TestDrive)
    }
}
