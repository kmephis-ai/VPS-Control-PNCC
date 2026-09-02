[CmdletBinding()]
param(
    [string]$Repository = 'kmephis-ai/VPS-Control-PNCC',
    [int]$PollSeconds = 5,
    [int]$TimeoutSeconds = 600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedRepository = 'kmephis-ai/VPS-Control-PNCC'
$WorkflowFile = 'wave6-wu149-bounded-dispatch-fallback.yml'
$WorkflowPath = ".github/workflows/$WorkflowFile"
$RequiredRunnerLabel = 'ubuntu-24.04'
$ApiVersion = '2026-03-10'

function Assert-Condition {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Invoke-GhApiJson {
    param([string[]]$Arguments)
    $raw = & gh @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw 'GitHub provider request failed.'
    }
    $text = ($raw -join "`n").Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw 'GitHub provider returned an empty response where JSON was required.'
    }
    try {
        return ($text | ConvertFrom-Json)
    }
    catch {
        throw 'GitHub provider returned invalid JSON.'
    }
}

Assert-Condition ($Repository -ceq $ExpectedRepository) 'Repository override is not authorized.'
Assert-Condition ($PollSeconds -ge 2 -and $PollSeconds -le 60) 'PollSeconds is outside the bounded range.'
Assert-Condition ($TimeoutSeconds -ge 30 -and $TimeoutSeconds -le 1800) 'TimeoutSeconds is outside the bounded range.'
Assert-Condition ($null -ne (Get-Command gh -ErrorAction SilentlyContinue)) 'GitHub CLI (gh) is required.'

& gh auth status --hostname github.com 1>$null 2>$null
Assert-Condition ($LASTEXITCODE -eq 0) 'Existing GitHub CLI authentication is unavailable.'

$mainRefEndpoint = "repos/$ExpectedRepository/git/ref/heads/main"
$workflowEndpoint = "repos/$ExpectedRepository/actions/workflows/$WorkflowFile"
$dispatchEndpoint = "repos/$ExpectedRepository/actions/workflows/$WorkflowFile/dispatches"

$mainBefore = Invoke-GhApiJson @('api', $mainRefEndpoint)
$expectedMainSha = [string]$mainBefore.object.sha
Assert-Condition ($expectedMainSha -cmatch '^[0-9a-f]{40}$') 'Fresh main SHA is invalid.'

$workflow = Invoke-GhApiJson @('api', $workflowEndpoint)
Assert-Condition ([string]$workflow.path -ceq $WorkflowPath) 'Target workflow path does not match the authorized WU149 fallback.'
Assert-Condition ([string]$workflow.state -ceq 'active') 'Target workflow is not active.'

$dispatchStartedUtc = [DateTime]::UtcNow
$dispatch = Invoke-GhApiJson @(
    'api',
    '--method', 'POST',
    '-H', "X-GitHub-Api-Version: $ApiVersion",
    $dispatchEndpoint,
    '-f', 'ref=main'
)

$runIdText = [string]$dispatch.workflow_run_id
Assert-Condition ($runIdText -cmatch '^[1-9][0-9]*$') 'Dispatch response did not provide one workflow_run_id.'
$runId = [Int64]$runIdText

$mainAfter = Invoke-GhApiJson @('api', $mainRefEndpoint)
$postDispatchMainSha = [string]$mainAfter.object.sha
Assert-Condition ($postDispatchMainSha -ceq $expectedMainSha) 'Main drifted across workflow_dispatch; evidence is not authoritative.'

$runEndpoint = "repos/$ExpectedRepository/actions/runs/$runId"
$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
$run = $null
while ([DateTime]::UtcNow -lt $deadline) {
    $run = Invoke-GhApiJson @('api', $runEndpoint)
    Assert-Condition ([Int64]$run.id -eq $runId) 'Provider returned a different workflow run.'
    Assert-Condition ([string]$run.event -ceq 'workflow_dispatch') 'Provider run event is not workflow_dispatch.'
    Assert-Condition ([string]$run.head_sha -ceq $expectedMainSha) 'Provider run head SHA does not match the pre-dispatch main SHA.'
    Assert-Condition ([string]$run.head_branch -ceq 'main') 'Provider run head branch is not main.'
    Assert-Condition ([string]$run.path -ceq $WorkflowPath) 'Provider run workflow path is not the authorized WU149 fallback.'
    if ([string]$run.status -ceq 'completed') { break }
    Start-Sleep -Seconds $PollSeconds
}

Assert-Condition ($null -ne $run) 'No provider run was observed.'
Assert-Condition ([string]$run.status -ceq 'completed') 'Workflow dispatch did not reach a terminal state before timeout.'
Assert-Condition (-not [string]::IsNullOrWhiteSpace([string]$run.conclusion)) 'Terminal provider run has no conclusion.'

$jobs = Invoke-GhApiJson @('api', "repos/$ExpectedRepository/actions/runs/$runId/jobs?per_page=100")
$jobList = @($jobs.jobs)
Assert-Condition ($jobList.Count -gt 0) 'No workflow jobs were returned; GitHub-hosted execution cannot be proven.'
foreach ($job in $jobList) {
    $labels = @($job.labels | ForEach-Object { [string]$_ })
    Assert-Condition ($labels -notcontains 'self-hosted') 'A self-hosted runner label was observed.'
    Assert-Condition ($labels -contains $RequiredRunnerLabel) 'Required GitHub-hosted runner image label was not observed.'
}

$createdAt = [DateTime]::Parse([string]$run.created_at).ToUniversalTime()
Assert-Condition ($createdAt -ge $dispatchStartedUtc.AddMinutes(-1)) 'Provider run predates the bounded dispatch window.'

$result = [ordered]@{
    schema_version = 1
    work_unit = 'PIPE-WU-151'
    target_workflow = $WorkflowPath
    event = [string]$run.event
    run_id = $runId
    run_url = [string]$run.html_url
    expected_main_sha = $expectedMainSha
    post_dispatch_main_sha = $postDispatchMainSha
    head_sha = [string]$run.head_sha
    head_branch = [string]$run.head_branch
    status = [string]$run.status
    conclusion = [string]$run.conclusion
    github_hosted_runner_proven = $true
    required_runner_label = $RequiredRunnerLabel
    repository_mutation_performed = $false
    scheduler_delivery_repaired = $false
    automatic_scheduler_replacement = $false
    terminal = 'REAL_WORKFLOW_DISPATCH_PROVIDER_PROOF_CAPTURED'
}

$result | ConvertTo-Json -Depth 6
