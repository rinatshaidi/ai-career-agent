param(
    [ValidateSet('static', 'docker')]
    [string]$Mode = 'static',
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$PostgresImage = 'postgres:16-alpine',
    [string]$DbName = 'ai_career_agent_validation',
    [string]$DbUser = 'postgres',
    [string]$DbPassword = 'postgres',
    [string]$ContainerName = "ai-career-agent-migration-check-$PID",
    [switch]$KeepContainer
)

$migrationDir = Join-Path $Root 'database\migrations'
$verificationSqlFiles = @(
    (Join-Path $Root 'database\sql\verify_v1_schema.sql'),
    (Join-Path $Root 'database\sql\verify_block3_collection.sql')
)

if (-not (Test-Path -LiteralPath $migrationDir -PathType Container)) {
    Write-Error "Migration directory not found: $migrationDir"
    exit 1
}

foreach ($verificationSql in $verificationSqlFiles) {
    if (-not (Test-Path -LiteralPath $verificationSql -PathType Leaf)) {
        Write-Error "Verification SQL file not found: $verificationSql"
        exit 1
    }
}

$migrationFiles = Get-ChildItem -Path $migrationDir -Filter '*.sql' | Sort-Object Name

if ($migrationFiles.Count -eq 0) {
    Write-Error 'No SQL migration files were found.'
    exit 1
}

$requiredTables = @(
    'users',
    'user_profiles',
    'sources',
    'opportunities',
    'opportunity_ai_analysis',
    'opportunity_scores',
    'notifications',
    'google_sheets_journal',
    'source_run_logs',
    'system_logs'
)

$requiredFunctions = @(
    'collection_ensure_source',
    'collection_upsert_opportunity',
    'collection_ingest_source_batch'
)

$fullMigrationText = ($migrationFiles | ForEach-Object { Get-Content -Raw $_.FullName }) -join "`n"
$missingTableDefinitions = @()

foreach ($tableName in $requiredTables) {
    if ($fullMigrationText -notmatch ("CREATE TABLE\s+" + [regex]::Escape($tableName) + "\b")) {
        $missingTableDefinitions += $tableName
    }
}

$missingFunctionDefinitions = @()

foreach ($functionName in $requiredFunctions) {
    if ($fullMigrationText -notmatch ("FUNCTION\s+" + [regex]::Escape($functionName) + "\s*\(")) {
        $missingFunctionDefinitions += $functionName
    }
}

if ($missingTableDefinitions.Count -gt 0) {
    Write-Error ("Missing CREATE TABLE statements for: " + ($missingTableDefinitions -join ', '))
    exit 1
}

if ($missingFunctionDefinitions.Count -gt 0) {
    Write-Error ("Missing function definitions for: " + ($missingFunctionDefinitions -join ', '))
    exit 1
}

Write-Host 'Static migration validation passed.' -ForegroundColor Green
Write-Host 'Migration files:'
$migrationFiles | ForEach-Object { Write-Host ("- " + $_.Name) }

if ($Mode -eq 'static') {
    exit 0
}

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCommand) {
    Write-Error 'Docker was not found in PATH. Use -Mode static or install Docker CLI for disposable validation.'
    exit 1
}

$startedContainer = $false

try {
    $runArgs = @(
        'run',
        '-d',
        '--rm',
        '--name', $ContainerName,
        '-e', "POSTGRES_DB=$DbName",
        '-e', "POSTGRES_USER=$DbUser",
        '-e', "POSTGRES_PASSWORD=$DbPassword",
        $PostgresImage
    )

    $containerId = & $dockerCommand.Source @runArgs
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($containerId)) {
        throw 'Failed to start disposable PostgreSQL container.'
    }

    $startedContainer = $true
    Write-Host "Started disposable container: $ContainerName" -ForegroundColor Yellow

    $ready = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        & $dockerCommand.Source exec $ContainerName pg_isready -U $DbUser -d $DbName *> $null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }

        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        throw 'Disposable PostgreSQL container did not become ready in time.'
    }

    foreach ($migrationFile in $migrationFiles) {
        $containerPath = "/tmp/$($migrationFile.Name)"
        Write-Host "Applying $($migrationFile.Name)..." -ForegroundColor Cyan

        & $dockerCommand.Source cp $migrationFile.FullName "${ContainerName}:${containerPath}"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to copy migration file into container: $($migrationFile.Name)"
        }

        & $dockerCommand.Source exec $ContainerName psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName -f $containerPath
        if ($LASTEXITCODE -ne 0) {
            throw "Migration failed: $($migrationFile.Name)"
        }
    }

    foreach ($verificationSql in $verificationSqlFiles) {
        $verificationContainerPath = "/tmp/$([System.IO.Path]::GetFileName($verificationSql))"
        & $dockerCommand.Source cp $verificationSql "${ContainerName}:${verificationContainerPath}"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to copy verification SQL into container: $verificationSql"
        }

        Write-Host ("Running verification: " + [System.IO.Path]::GetFileName($verificationSql)) -ForegroundColor Cyan
        & $dockerCommand.Source exec $ContainerName psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName -f $verificationContainerPath
        if ($LASTEXITCODE -ne 0) {
            throw "Schema verification failed: $verificationSql"
        }
    }

    Write-Host 'Disposable migration validation passed.' -ForegroundColor Green
}
catch {
    Write-Error $_
    exit 1
}
finally {
    if ($startedContainer -and -not $KeepContainer) {
        & $dockerCommand.Source rm -f $ContainerName *> $null
    }
}
