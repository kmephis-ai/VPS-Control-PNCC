Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Describe 'WU-090 PS5.1 release publication compatibility shim' {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
        $path = Join-Path $repoRoot 'tools\release\Invoke-PnccV701StableReleasePublicationPs51.ps1'
        $executorPath = Join-Path $repoRoot 'tools\release\Invoke-PnccV701StableReleasePublication.ps1'
        $raw = Get-Content -LiteralPath $path -Raw
        $executorRaw = Get-Content -LiteralPath $executorPath -Raw
        $tokens = $null
        $errors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
        $script:ShimRaw = $raw
        $script:ShimErrors = @($errors)
        $script:ExecutorRaw = $executorRaw
    }

    It 'is Windows PowerShell 5.1 parse-safe' {
        $script:ShimErrors.Count | Should -Be 0
        $script:ShimRaw.Contains('#requires -Version 5.1') | Should -BeTrue
    }

    It 'pins the exact previously merged executor bytes' {
        $script:ShimRaw.Contains("`$PinnedExecutorCommit = '2837c624234cb2cf29fb0c0524759bd56c3e15e3'") | Should -BeTrue
        $script:ShimRaw.Contains("`$PinnedExecutorBlob = '1484442efe1b6495b2018e4ca39145a092bb109c'") | Should -BeTrue
        $script:ShimRaw.Contains("`$PinnedExecutorPath = 'tools/release/Invoke-PnccV701StableReleasePublication.ps1'") | Should -BeTrue
    }

    It 'applies the exact native gh patch once to the executor text' {
        $pattern = '(?m)^    \$raw = @\(& \$script:GhPath @Arguments 2>&1\)\r?\n    \$code = \$LASTEXITCODE$'
        $matches = [regex]::Matches($script:ExecutorRaw,$pattern)
        $matches.Count | Should -Be 1
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
        $patched = [regex]::Replace($script:ExecutorRaw,$pattern,[System.Text.RegularExpressions.MatchEvaluator]{ param($m) $replacement },1)
        $patched | Should -Not -Be $script:ExecutorRaw
        $patched.Contains("`$ErrorActionPreference = 'Continue'") | Should -BeTrue
        $patched.Contains('$ErrorActionPreference = $savedErrorActionPreference') | Should -BeTrue
        $tokens=$null; $errors=$null
        [void][System.Management.Automation.Language.Parser]::ParseInput($patched,[ref]$tokens,[ref]$errors)
        @($errors).Count | Should -Be 0
    }

    It 'uses literal invariant checks that cannot interpolate ErrorActionPreference' {
        $script:ShimRaw.Contains('if (-not $patched.Contains("`$ErrorActionPreference = ''Continue''"))') | Should -BeTrue
        $script:ShimRaw.Contains("[regex]::Matches(`$patched,\"\`$ErrorActionPreference = 'Continue'\"") | Should -BeFalse
        $script:ShimRaw.Contains('PS51_NATIVE_COMMAND_PATCH=PASS') | Should -BeTrue
    }

    It 'does not weaken the outer fail-fast policy' {
        $script:ShimRaw.Contains('$ErrorActionPreference = ''Stop''') | Should -BeTrue
        $script:ShimRaw.Contains('PATCHED_EXECUTOR_PS51_AST_FAILED') | Should -BeTrue
        $script:ShimRaw.Contains('PATCHED_EXECUTOR_EXIT_CODE=') | Should -BeTrue
    }

    It 'requires explicit Execute and otherwise delegates Plan mode' {
        $script:ShimRaw.Contains('[switch]$Execute') | Should -BeTrue
        $script:ShimRaw.Contains('if ($Execute) { $args += ''-Execute'' }') | Should -BeTrue
    }

    It 'does not add any release overwrite or tunnel lifecycle primitive' {
        $script:ShimRaw | Should -Not -Match '(?i)--clobber'
        $script:ShimRaw | Should -Not -Match '(?i)release\s+delete'
        $script:ShimRaw | Should -Not -Match '(?i)git\s+tag\s+-f'
        $script:ShimRaw | Should -Not -Match '(?i)git\s+push.*--force'
        $script:ShimRaw | Should -Not -Match '(?i)RestartTunnel|Stop-Process|taskkill|TerminateProcess'
    }
}
