$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$schemaPom = Join-Path $projectRoot 'db\pom.xml'
$psqlCommand = Get-Command psql.exe -ErrorAction SilentlyContinue
$psqlExe = if ($psqlCommand) { $psqlCommand.Source } else { 'C:\Program Files\PostgreSQL\18\bin\psql.exe' }
if (-not (Test-Path -LiteralPath $psqlExe)) {
    throw 'psql.exe was not found. Add PostgreSQL bin to PATH.'
}
$mavenCommand = Get-Command mvn.cmd -ErrorAction Stop

$securePassword = Read-Host 'Local PostgreSQL postgres password' -AsSecureString
$credential = [pscredential]::new('postgres', $securePassword)
$previousPassword = [Environment]::GetEnvironmentVariable('PGPASSWORD', 'Process')

try {
    [Environment]::SetEnvironmentVariable('PGPASSWORD', $credential.GetNetworkCredential().Password, 'Process')

    $databaseCount = & $psqlExe -w -X -A -t -P pager=off -v ON_ERROR_STOP=1 `
        -h 127.0.0.1 -p 5432 -U postgres -d postgres `
        -c "SELECT count(*) FROM pg_database WHERE datname = 'deckwise_python_dev'"
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect local PostgreSQL databases.' }

    if ($databaseCount.Trim() -eq '0') {
        & $psqlExe -w -X -P pager=off -v ON_ERROR_STOP=1 `
            -h 127.0.0.1 -p 5432 -U postgres -d postgres `
            -c 'CREATE DATABASE deckwise_python_dev'
        if ($LASTEXITCODE -ne 0) { throw 'Could not create deckwise_python_dev.' }
    }

    & $mavenCommand.Source -f $schemaPom flyway:migrate flyway:validate
    if ($LASTEXITCODE -ne 0) { throw 'Flyway migrate/validate failed.' }

    & $psqlExe -w -X -A -t -P pager=off -v ON_ERROR_STOP=1 `
        -h 127.0.0.1 -p 5432 -U postgres -d deckwise_python_dev `
        -c "SELECT 'versioned_migrations=' || count(*) FROM backend_data.flyway_schema_history WHERE success AND type = 'SQL'"
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify Flyway history.' }

    & $psqlExe -w -X -A -t -P pager=off -v ON_ERROR_STOP=1 `
        -h 127.0.0.1 -p 5432 -U postgres -d deckwise_python_dev `
        -c "SELECT 'domain_tables=' || count(*) FROM pg_tables WHERE schemaname = 'backend_data' AND tablename <> 'flyway_schema_history'"
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify migrated tables.' }

    Push-Location $projectRoot
    try {
        & uv run python -m app.db.session
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python database connection check failed.' }
} finally {
    [Environment]::SetEnvironmentVariable('PGPASSWORD', $previousPassword, 'Process')
}
