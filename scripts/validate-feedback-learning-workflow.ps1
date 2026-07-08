param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$callbackWorkflowPath = Join-Path $Root 'n8n\workflows\handle-opportunity-notification-actions.json'
$retentionWorkflowPath = Join-Path $Root 'n8n\workflows\maintain-working-memory-retention.json'
$contractPath = Join-Path $Root 'config\n8n\feedback-learning.md'
$sheetColumnsPath = Join-Path $Root 'config\n8n\feedback-learning.sheet-columns.json'

foreach ($requiredPath in @($callbackWorkflowPath, $retentionWorkflowPath, $contractPath, $sheetColumnsPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        Write-Error "Required file not found: $requiredPath"
        exit 1
    }
}

$callbackWorkflow = Get-Content -Raw $callbackWorkflowPath | ConvertFrom-Json
$retentionWorkflow = Get-Content -Raw $retentionWorkflowPath | ConvertFrom-Json
$sheetColumns = Get-Content -Raw $sheetColumnsPath | ConvertFrom-Json

$requiredCallbackNodeNames = @(
    'Webhook Trigger',
    'Parse Callback Action',
    'Callback Action Supported?',
    'Record Notification Action',
    'Archive Required?',
    'Build Google Sheets Row',
    'Google Sheets | Upsert Archive',
    'Parse Google Sheets Sync',
    'Archive Sync Failed?',
    'Mark Google Sheets Sync Failed',
    'Mark Google Sheets Synced',
    'Respond Callback Action',
    'Respond Unsupported Action',
    'Return Response'
)

$requiredRetentionNodeNames = @(
    'Manual Trigger',
    'Schedule Trigger',
    'Init Retention Context',
    'Purge Expired Working Memory'
)

$callbackNodeNames = @($callbackWorkflow.nodes | ForEach-Object { $_.name })
$retentionNodeNames = @($retentionWorkflow.nodes | ForEach-Object { $_.name })

$missingCallbackNodes = $requiredCallbackNodeNames | Where-Object { $_ -notin $callbackNodeNames }
$missingRetentionNodes = $requiredRetentionNodeNames | Where-Object { $_ -notin $retentionNodeNames }

if ($callbackWorkflow.name -ne 'Handle Opportunity Notification Actions') {
    Write-Error "Unexpected callback workflow name: $($callbackWorkflow.name)"
    exit 1
}

if ($retentionWorkflow.name -ne 'Maintain Working Memory Retention') {
    Write-Error "Unexpected retention workflow name: $($retentionWorkflow.name)"
    exit 1
}

if ($missingCallbackNodes.Count -gt 0) {
    Write-Error ('Feedback callback workflow is missing required nodes: ' + ($missingCallbackNodes -join ', '))
    exit 1
}

if ($missingRetentionNodes.Count -gt 0) {
    Write-Error ('Retention workflow is missing required nodes: ' + ($missingRetentionNodes -join ', '))
    exit 1
}

$requiredSheetColumns = @(
    'archive_key',
    'date',
    'source',
    'opportunity_type',
    'title',
    'score',
    'ai_recommendation',
    'user_action',
    'result',
    'url'
)

if ($sheetColumns.matchingColumn -ne 'archive_key') {
    Write-Error "Unexpected matching column in feedback-learning.sheet-columns.json: $($sheetColumns.matchingColumn)"
    exit 1
}

$missingSheetColumns = $requiredSheetColumns | Where-Object { $_ -notin @($sheetColumns.columns) }
if ($missingSheetColumns.Count -gt 0) {
    Write-Error ('Feedback sheet column contract is missing required columns: ' + ($missingSheetColumns -join ', '))
    exit 1
}

Write-Host 'Feedback and learning workflow validation passed.' -ForegroundColor Green
Write-Host "Callback workflow: $($callbackWorkflow.name)"
Write-Host "Retention workflow: $($retentionWorkflow.name)"
Write-Host "Required callback nodes checked: $($requiredCallbackNodeNames.Count)"
Write-Host "Required retention nodes checked: $($requiredRetentionNodeNames.Count)"
