param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$requiredFiles = @(
    'README.md',
    'PRD.md',
    'ARCHITECTURE.md',
    'CHANGELOG.md',
    '.env.example',
    '.gitignore',
    'docker-compose.yml',
    'docs\database.md',
    'apps\README.md',
    'packages\README.md',
    'docs\README.md',
    'docs\adr\0001-foundation-architecture.md',
    'config\README.md',
    'database\README.md',
    'database\migrations\20260708141000__create_v1_core_tables.sql',
    'database\migrations\20260708141100__create_v1_indexes.sql',
    'database\migrations\20260708141200__create_v1_updated_at_triggers.sql',
    'database\migrations\20260708153000__add_block3_collection_functions.sql',
    'database\sql\verify_v1_schema.sql',
    'database\sql\verify_block3_collection.sql',
    'docs\opportunity-collection.md',
    'docs\runbooks\import-collect-opportunities.md',
    'n8n\README.md',
    'n8n\workflows\collect-opportunities.json',
    'config\n8n\collect-opportunities.sources.json',
    'config\n8n\collect-opportunities.md',
    'scripts\README.md',
    'scripts\validate-migrations.ps1',
    'scripts\validate-collection-workflow.ps1',
    'tests\README.md'
)

$requiredDirectories = @(
    'apps\api',
    'apps\worker',
    'packages\shared',
    'docs\adr',
    'docs\runbooks',
    'config\env',
    'config\docker',
    'config\n8n',
    'database\migrations',
    'database\sql',
    'n8n\workflows',
    'n8n\exports',
    'tests\architecture',
    'tests\integration',
    'logs'
)

$missing = New-Object System.Collections.Generic.List[string]

foreach ($relativePath in $requiredFiles) {
    $fullPath = Join-Path $Root $relativePath
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        $missing.Add("Missing file: $relativePath")
    }
}

foreach ($relativePath in $requiredDirectories) {
    $fullPath = Join-Path $Root $relativePath
    if (-not (Test-Path -LiteralPath $fullPath -PathType Container)) {
        $missing.Add("Missing directory: $relativePath")
    }
}

if ($missing.Count -gt 0) {
    Write-Host 'Foundation validation failed.' -ForegroundColor Red
    $missing | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    exit 1
}

Write-Host 'Foundation structure is valid.' -ForegroundColor Green
Write-Host "Validated root: $Root"
