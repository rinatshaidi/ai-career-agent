param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$workflowPath = Join-Path $Root 'n8n\workflows\send-opportunity-notifications.json'
$callbackWorkflowPath = Join-Path $Root 'n8n\workflows\handle-opportunity-notification-actions.json'
$contractPath = Join-Path $Root 'config\n8n\telegram-delivery.md'

foreach ($requiredPath in @($workflowPath, $callbackWorkflowPath, $contractPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        Write-Error "Required file not found: $requiredPath"
        exit 1
    }
}

$workflow = Get-Content -Raw $workflowPath | ConvertFrom-Json
$callbackWorkflow = Get-Content -Raw $callbackWorkflowPath | ConvertFrom-Json

$requiredNodeNames = @(
    'Manual Trigger',
    'Schedule Trigger',
    'Init Delivery Context',
    'Sync Telegram Outbox',
    'Claim Notification Batch',
    'Build Telegram Message',
    'Telegram | Send Opportunity',
    'Parse Telegram Response',
    'Delivery Failed?',
    'Mark Notification Failed',
    'Mark Notification Sent'
)

$requiredCallbackNodeNames = @(
    'Webhook Trigger',
    'Parse Callback Action',
    'Callback Action Supported?',
    'Record Notification Action',
    'Respond Callback Action',
    'Respond Unsupported Action',
    'Return Response'
)

$nodeNames = @($workflow.nodes | ForEach-Object { $_.name })
$callbackNodeNames = @($callbackWorkflow.nodes | ForEach-Object { $_.name })

$missingNodes = $requiredNodeNames | Where-Object { $_ -notin $nodeNames }
$missingCallbackNodes = $requiredCallbackNodeNames | Where-Object { $_ -notin $callbackNodeNames }

if ($workflow.name -ne 'Send Opportunity Notifications') {
    Write-Error "Unexpected workflow name: $($workflow.name)"
    exit 1
}

if ($callbackWorkflow.name -ne 'Handle Opportunity Notification Actions') {
    Write-Error "Unexpected callback workflow name: $($callbackWorkflow.name)"
    exit 1
}

if ($missingNodes.Count -gt 0) {
    Write-Error ('Telegram delivery workflow is missing required nodes: ' + ($missingNodes -join ', '))
    exit 1
}

if ($missingCallbackNodes.Count -gt 0) {
    Write-Error ('Telegram callback workflow is missing required nodes: ' + ($missingCallbackNodes -join ', '))
    exit 1
}

Write-Host 'Telegram delivery workflow validation passed.' -ForegroundColor Green
Write-Host "Workflow: $($workflow.name)"
Write-Host "Callback workflow: $($callbackWorkflow.name)"
Write-Host "Required delivery nodes checked: $($requiredNodeNames.Count)"
Write-Host "Required callback nodes checked: $($requiredCallbackNodeNames.Count)"
