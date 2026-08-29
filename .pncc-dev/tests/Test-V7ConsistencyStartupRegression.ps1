#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$module=Join-Path $root 'src\windows-v7\modules\V7-Consistency.ps1'
. $module

function Assert-True([bool]$Condition,[string]$Message){
    if(-not $Condition){throw "ASSERT_TRUE_FAILED: $Message"}
}
function Assert-False([bool]$Condition,[string]$Message){
    if($Condition){throw "ASSERT_FALSE_FAILED: $Message"}
}
function Assert-Eq($Actual,$Expected,[string]$Message){
    if([string]$Actual -ne [string]$Expected){throw "ASSERT_EQ_FAILED: $Message actual=[$Actual] expected=[$Expected]"}
}

# Reproduces the released v7.0.0 defect shape: two safe Contains() calls on one line,
# with a normal PowerShell variable between them. The old greedy regex crosses call
# boundaries and falsely captures $engineUpgradeText as marker interpolation.
$safeMulti=@'
$localPuttyFirst=$readinessText.Contains("PuTTY PORTABLE\putty_portable.exe") -and $engineUpgradeText.Contains("PuTTY PORTABLE\putty_portable.exe")
'@
$legacyGreedy='\.Contains\(".*\$[A-Za-z_][A-Za-z0-9_]*.*"\)'
Assert-True ([regex]::IsMatch($safeMulti,$legacyGreedy)) 'regression fixture must reproduce old greedy false positive'
$r=Test-V7ContainsMarkerStrictModeSafety -SourceText $safeMulti
Assert-True ([bool]$r.Safe) 'multi-Contains line with intervening ordinary variable must be safe'
Assert-Eq $r.Reason 'PASS' 'safe multi-Contains reason'

$safeMulti2=@'
$first=$a.Contains("alpha") -and $ordinaryVariable -and $b.Contains("beta")
'@
$r=Test-V7ContainsMarkerStrictModeSafety -SourceText $safeMulti2
Assert-True ([bool]$r.Safe) 'ordinary variable between Contains calls must not be inspected as string interpolation'

$escapedMarkers=@'
$x.Contains("Join-Path `$BaseDir 'file'")
$x.Contains("Join-Path `$legacyPuttyDir 'plink.exe'")
$x.Contains("`$env:LOCALAPPDATA")
$x.Contains("`$false")
'@
$r=Test-V7ContainsMarkerStrictModeSafety -SourceText $escapedMarkers
Assert-True ([bool]$r.Safe) 'escaped marker variables must remain literal and safe'
Assert-Eq $r.Reason 'PASS' 'escaped marker reason'

$singleQuoted=@'
$x.Contains('$BaseDir remains literal')
'@
$r=Test-V7ContainsMarkerStrictModeSafety -SourceText $singleQuoted
Assert-True ([bool]$r.Safe) 'single-quoted marker must be safe'

$unsafe=@'
$x.Contains("Join-Path $Undefined 'file'")
'@
$r=Test-V7ContainsMarkerStrictModeSafety -SourceText $unsafe
Assert-False ([bool]$r.Safe) 'actual unescaped interpolation inside Contains string must fail closed'
Assert-Eq $r.Reason 'UNESCAPED_CONTAINS_INTERPOLATION' 'unsafe interpolation reason'
Assert-True (-not [string]::IsNullOrWhiteSpace([string]$r.UnsafeExtent)) 'unsafe extent must identify the callsite'

$subExpressionUnsafe=@'
$x.Contains("value=$(Get-Date)")
'@
$r=Test-V7ContainsMarkerStrictModeSafety -SourceText $subExpressionUnsafe
Assert-False ([bool]$r.Safe) 'subexpression interpolation inside Contains string must fail closed'

$r=Test-V7ContainsMarkerStrictModeSafety -SourceText 'if ('
Assert-False ([bool]$r.Safe) 'parser failure must fail closed'
Assert-Eq $r.Reason 'PARSE_ERROR' 'parse failure reason'

$canonical=[IO.File]::ReadAllText($module)
$r=Test-V7ContainsMarkerStrictModeSafety -SourceText $canonical
Assert-True ([bool]$r.Safe) 'canonical V7-Consistency source must pass its scoped marker safety check'
Assert-Eq $r.Reason 'PASS' 'canonical source reason'

Write-Host 'WU080_CONSISTENCY_STARTUP_REGRESSION=PASS'
Write-Host 'OLD_GREEDY_FALSE_POSITIVE_REPRODUCED=true'
Write-Host 'AST_ARGUMENT_SCOPED_CHECK=true'
Write-Host 'ACTUAL_UNESCAPED_INTERPOLATION_FAILS_CLOSED=true'
Write-Host 'RUNTIME_MUTATION=false'
Write-Host 'RESERVE_1080_MUTATION=false'
Write-Host 'PRIMARY_1081_MUTATION=false'
