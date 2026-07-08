param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$workflowPath = Join-Path $Root 'n8n\workflows\analyze-opportunities.json'
$schemaPath = Join-Path $Root 'config\n8n\ai-decision-engine.output-schema.json'
$contractPath = Join-Path $Root 'config\n8n\ai-decision-engine.md'

foreach ($requiredPath in @($workflowPath, $schemaPath, $contractPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        Write-Error "Required file not found: $requiredPath"
        exit 1
    }
}

$workflow = Get-Content -Raw $workflowPath | ConvertFrom-Json
$schema = Get-Content -Raw $schemaPath | ConvertFrom-Json

$requiredNodeNames = @(
    'Manual Trigger',
    'Schedule Trigger',
    'Init Decision Context',
    'Claim Analysis Batch',
    'Build OpenAI Request',
    'OpenAI | Analyze Opportunity',
    'Parse OpenAI Response',
    'Analysis Failed?',
    'Mark Analysis Failed',
    'Persist AI Analysis'
)

$nodeNames = @($workflow.nodes | ForEach-Object { $_.name })
$missingNodes = $requiredNodeNames | Where-Object { $_ -notin $nodeNames }

if ($workflow.name -ne 'Analyze Opportunities') {
    Write-Error "Unexpected workflow name: $($workflow.name)"
    exit 1
}

if ($missingNodes.Count -gt 0) {
    Write-Error ('Workflow is missing required nodes: ' + ($missingNodes -join ', '))
    exit 1
}

$requiredSchemaFields = @(
    'summary',
    'is_recommended',
    'why_fit',
    'why_not_fit',
    'risks',
    'fit_score',
    'probability_to_win_score',
    'difficulty_score',
    'income_potential_score',
    'urgency_score',
    'skills_match_score',
    'decision_confidence_score'
)

$schemaFields = @($schema.properties.PSObject.Properties | ForEach-Object { $_.Name })
$missingSchemaFields = $requiredSchemaFields | Where-Object { $_ -notin $schemaFields }

if ($missingSchemaFields.Count -gt 0) {
    Write-Error ('Decision output schema is missing fields: ' + ($missingSchemaFields -join ', '))
    exit 1
}

Write-Host 'AI decision workflow validation passed.' -ForegroundColor Green
Write-Host "Workflow: $($workflow.name)"
Write-Host "Required nodes checked: $($requiredNodeNames.Count)"
Write-Host "Decision schema fields checked: $($requiredSchemaFields.Count)"
