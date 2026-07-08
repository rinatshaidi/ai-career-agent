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
    'apps\README.md',
    'packages\README.md',
    'docs\README.md',
    'docs\adr\0001-foundation-architecture.md',
    'config\README.md',
    'database\README.md',
    'n8n\README.md',
    'scripts\README.md',
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
