param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$workflowPath = Join-Path $Root 'n8n\workflows\collect-opportunities.json'
$configPath = Join-Path $Root 'config\n8n\collect-opportunities.sources.json'

if (-not (Test-Path -LiteralPath $workflowPath -PathType Leaf)) {
    Write-Error "Workflow file not found: $workflowPath"
    exit 1
}

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    Write-Error "Source config file not found: $configPath"
    exit 1
}

$workflow = Get-Content -Raw $workflowPath | ConvertFrom-Json
$sourceConfig = Get-Content -Raw $configPath | ConvertFrom-Json

$requiredNodeNames = @(
    'Manual Trigger',
    'Schedule Trigger',
    'RSS | We Work Remotely | Ensure Source',
    'RSS | Remote OK | Ensure Source',
    'HH | Automation | Ensure Source',
    'HH | OpenAI | Ensure Source',
    'RSS | We Work Remotely | Ingest Batch',
    'RSS | Remote OK | Ingest Batch',
    'HH | Automation | Ingest Batch',
    'HH | OpenAI | Ingest Batch'
)

$nodeNames = @($workflow.nodes | ForEach-Object { $_.name })
$missingNodes = $requiredNodeNames | Where-Object { $_ -notin $nodeNames }

if ($workflow.name -ne 'Collect Opportunities') {
    Write-Error "Unexpected workflow name: $($workflow.name)"
    exit 1
}

if ($missingNodes.Count -gt 0) {
    Write-Error ('Workflow is missing required nodes: ' + ($missingNodes -join ', '))
    exit 1
}

$rssCount = @($sourceConfig.implementedSources.rss).Count
$hhCount = @($sourceConfig.implementedSources.headhunter).Count

if ($rssCount -lt 1 -or $hhCount -lt 1) {
    Write-Error 'Source config must define at least one RSS source and one HeadHunter source.'
    exit 1
}

Write-Host 'Collection workflow validation passed.' -ForegroundColor Green
Write-Host "Workflow: $($workflow.name)"
Write-Host "RSS sources configured: $rssCount"
Write-Host "HeadHunter sources configured: $hhCount"
