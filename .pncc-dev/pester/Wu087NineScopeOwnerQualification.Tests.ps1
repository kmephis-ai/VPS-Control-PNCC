#requires -Version 5.1
Set-StrictMode -Version 2.0

BeforeAll {
    $RepoRoot=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $RunnerPath=Join-Path $RepoRoot 'tools\runtime-agent\Invoke-PnccV701NineScopeOwnerQualification.ps1'
    $FixturePath=Join-Path $RepoRoot '.pncc-dev\tests\runtime-v701-nine-scope-plan.fixture.json'
    $RunnerRaw=[IO.File]::ReadAllText($RunnerPath)
}

Describe 'PIPE-WU-087 v7.0.1 nine-scope owner qualification runner' {
    It 'exists with UTF-8 BOM and parses under Windows PowerShell 5.1 grammar' {
        (Test-Path -LiteralPath $RunnerPath -PathType Leaf) | Should -BeTrue
        $bytes=[IO.File]::ReadAllBytes($RunnerPath)
        ($bytes.Length -ge 3) | Should -BeTrue
        $bytes[0] | Should -Be 0xEF
        $bytes[1] | Should -Be 0xBB
        $bytes[2] | Should -Be 0xBF
        $tokens=$null;$errors=$null
        [void][System.Management.Automation.Language.Parser]::ParseFile($RunnerPath,[ref]$tokens,[ref]$errors)
        @($errors).Count | Should -Be 0
    }

    It 'pins exact WU-087 control-plane and v7.0.1 identities' {
        $RunnerRaw.Contains("`$RunnerVersion='0.1.0'") | Should -BeTrue
        $RunnerRaw.Contains("`$ControlPlaneSha='157b32a407ff60acc0447b4f4e0229d74a886856'") | Should -BeTrue
        $RunnerRaw.Contains("`$ExpectedRequestId='PNCC-RQ-V7.0.1-D58023321360'") | Should -BeTrue
        $RunnerRaw.Contains("`$ExpectedCandidateId='PNCC-V7.0.1-D58023321360'") | Should -BeTrue
        $RunnerRaw.Contains("`$ExpectedSourceSha='d5802332136087339482c9b3171c1c5c9c18411e'") | Should -BeTrue
        $RunnerRaw.Contains("`$ExpectedCandidateSha='22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'") | Should -BeTrue
    }

    It 'pins actual protected-main provider artifact naming and digests' {
        $RunnerRaw.Contains("`$ExpectedCandidateProviderName='PNCC-CANDIDATE-d5802332136087339482c9b3171c1c5c9c18411e'") | Should -BeTrue
        $RunnerRaw.Contains("`$ExpectedRequestProviderName='PNCC-RUNTIME-REQUEST-d5802332136087339482c9b3171c1c5c9c18411e'") | Should -BeTrue
        $RunnerRaw.Contains('sha256:47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5') | Should -BeTrue
        $RunnerRaw.Contains('sha256:ac76b2cc60512c2a4a3b83095c82804f586d42d843439467f0d53fb52d71c844') | Should -BeTrue
        $RunnerRaw.Contains('9711822972') | Should -BeTrue
        $RunnerRaw.Contains('9711823182') | Should -BeTrue
        $RunnerRaw.Contains('33242642394') | Should -BeTrue
    }

    It 'contains exactly the nine governed runtime scope literals' {
        $scopes=@('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','WATCHDOG_LIFECYCLE','PROXIFIER_DESCENDANT_CLEANUP','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','CREDENTIAL_HOSTKEY','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')
        foreach($scope in $scopes){$RunnerRaw.Contains("'$scope'") | Should -BeTrue}
        $RunnerRaw.Contains("Assert-True (`$checks.Count -eq 9)") | Should -BeTrue
    }

    It 'composes only read-only Stable validators after Stage-A' {
        $RunnerRaw.Contains("Download-ControlFile 'tools/runtime-agent/Invoke-PnccRuntimeQualificationStageA.ps1'") | Should -BeTrue
        $RunnerRaw.Contains("Download-ControlFile 'tools/runtime-agent/Test-PnccStablePrimary1081Ownership.ps1'") | Should -BeTrue
        $RunnerRaw.Contains("Download-ControlFile 'tools/runtime-agent/Test-PnccStableWatchdogLifecycleV2.ps1'") | Should -BeTrue
        $RunnerRaw.Contains("Download-ControlFile 'tools/runtime-agent/Test-PnccStableCredentialHostkeyV4.ps1'") | Should -BeTrue
        $RunnerRaw.Contains("Download-ControlFile 'tools/runtime-agent/Test-PnccStableProxifierDescendantCleanup.ps1'") | Should -BeTrue
        $RunnerRaw.Contains("'-Mode','LiveObservation'") | Should -BeTrue
    }

    It 'does not contain PNCC tunnel lifecycle mutation primitives or broad process kill primitives' {
        $forbidden=@('RestartTunnel','StartTunnel','StopTunnel','StartReserve','StopReserve','taskkill','Stop-Process','Restart-Service','Stop-Service','Start-Service')
        foreach($token in $forbidden){$RunnerRaw.Contains($token) | Should -BeFalse}
    }

    It 'keeps 1080 and 1081 under run-level exact listener equality' {
        $RunnerRaw.Contains("`$PrimaryPort=1081") | Should -BeTrue
        $RunnerRaw.Contains("`$ReservePort=1080") | Should -BeTrue
        $RunnerRaw.Contains("'ports-before.json'") | Should -BeTrue
        $RunnerRaw.Contains("'ports-after.json'") | Should -BeTrue
        $RunnerRaw.Contains("'run-level 1080 listener snapshot'") | Should -BeTrue
        $RunnerRaw.Contains("'run-level 1081 listener snapshot'") | Should -BeTrue
    }

    It 'pins immutable V6.3.1 and exact generated Stable engine identity' {
        $RunnerRaw.Contains("`$ExpectedV631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'") | Should -BeTrue
        $RunnerRaw.Contains("`$ExpectedEngineSha='843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'") | Should -BeTrue
    }

    It 'requires private evidence and never grants promotion or repository authority' {
        $RunnerRaw.Contains("sanitation_state='PRIVATE'") | Should -BeTrue
        $RunnerRaw.Contains("qualification_state='RUNTIME_VERIFIED'") | Should -BeTrue
        $RunnerRaw.Contains("runtime_authority=`$true") | Should -BeTrue
        $RunnerRaw.Contains("promotion_eligible=`$false") | Should -BeTrue
        $RunnerRaw.Contains("repository_authority_mutation=`$false") | Should -BeTrue
        $RunnerRaw.Contains("release_or_tag_authorized=`$false") | Should -BeTrue
    }

    It 'does not use plaintext PuTTY password transport' {
        $plainPattern='(?i)(?:^|[\s''"])-pw(?:[\s''"=]|$)'
        $RunnerRaw | Should -Not -Match $plainPattern
        $RunnerRaw.Contains("'-pwfile'") | Should -BeTrue
    }

    It 'has an admitted Plan fixture and Plan mode cannot grant runtime authority' {
        (Test-Path -LiteralPath $FixturePath -PathType Leaf) | Should -BeTrue
        $fixture=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json
        foreach($name in @('request_identity','actual_provider_naming','stage_a_contract','primary_ownership_contract','watchdog_contract','proxifier_contract','credential_hostkey_contract','reserve_observation_only','private_result_contract','promotion_false')){[bool]$fixture.$name | Should -BeTrue}
        $RunnerRaw.Contains("runtime_execution_allowed=`$false") | Should -BeTrue
    }
}
