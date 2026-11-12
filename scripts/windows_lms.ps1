param(
    [ValidateSet('Setup','Start','Seed','Diagnose','Stop','Test')]
    [string]$Action = 'Setup'
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$TranscriptStarted = $false
try {
    Start-Transcript -Path (Join-Path $Root 'LMS_V33_LAST_RUN.log') -Force -ErrorAction Stop | Out-Null
    $TranscriptStarted = $true
} catch { Write-Host 'Info: unable to start transcript log; console output remains available.' }

function Invoke-Docker {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed (exit code $LASTEXITCODE): docker $($Arguments -join ' ')"
    }
}

function Require-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker CLI not found. Install/open Docker Desktop.'
    }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Engine is not running. Open Docker Desktop.' }
}

function Assert-NoForeignPortOwners {
    # Prevent confusing HTTP failures when old V1/V3 containers are still using the three ports.
    $rows = @(& docker ps --format '{{.Names}}|{{.Ports}}')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Docker port ownership.' }
    foreach ($line in $rows) {
        $parts = $line -split '\|', 2
        if ($parts.Count -ne 2) { continue }
        $owner = $parts[0]
        if ($owner -match '^lms_faceid_capstone_v33-') { continue }
        if ($parts[1] -match '(?:0\.0\.0\.0|127\.0\.0\.1|\[::\]):(5174|8001|3307)->') {
            throw "Ports 5174/8001/3307 are in use by Docker container '$owner'. Stop the OLD container/project in Docker Desktop (do not delete volumes), then run V3.3 setup again."
        }
    }
}

function New-SecureBytes([int]$Count) {
    $bytes = New-Object byte[] $Count
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ,$bytes
}

function New-RandomHex([int]$Count) {
    $bytes = New-SecureBytes $Count
    return [System.BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}

function New-FernetKey {
    $bytes = New-SecureBytes 32
    return [System.Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
}

function Assert-ConfigSecrets([string]$File) {
    # Validate without ever printing secret values; do not silently rotate them.
    $content = [System.IO.File]::ReadAllText($File)
    foreach ($key in @('DB_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'SECRET_KEY')) {
        $match = [regex]::Match($content, '(?m)^' + [regex]::Escape($key) + '=(.*)$')
        $value = $match.Groups[1].Value.Trim()
        if (-not $match.Success -or [string]::IsNullOrWhiteSpace($value) -or $value -eq '""' -or $value -eq "''") {
            throw "Your .env is missing $key (or it is empty). Restore the original .env for existing data."
        }
    }
}

function Initialize-Config {
    $dest = Join-Path $Root '.env'
    if (Test-Path $dest) {
        Write-Host 'Existing .env found. Keeping credentials/FaceID key unchanged.'
        Assert-ConfigSecrets $dest
        return
    }
    # This is a non-error inspection, even when no database volume exists yet.
    # `docker volume inspect <missing>` writes to stderr and can trigger an
    # exception under Windows PowerShell with ErrorActionPreference=Stop,
    # preventing .env creation on a fresh installation.
    $volumeNames = @(& docker volume ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to list Docker volumes. Verify Docker Desktop is running.'
    }
    if ($volumeNames -contains 'lms_faceid_capstone_v33_mysql_data') {
        throw 'V3.3 MySQL volume already exists but .env is missing. Restore the V3.3 .env to preserve its password. Do NOT delete data automatically.'
    }
    $source = Join-Path $Root '.env.example'
    if (-not (Test-Path $source)) { throw '.env.example is missing.' }
    $raw = [System.IO.File]::ReadAllText($source)
    $values = @{
        DB_PASSWORD = New-RandomHex 24
        MYSQL_ROOT_PASSWORD = New-RandomHex 24
        SECRET_KEY = New-RandomHex 48
        FACE_EMBEDDING_KEY = New-FernetKey
    }
    foreach ($item in $values.GetEnumerator()) {
        $key = [regex]::Escape($item.Key)
        $pattern = '(?m)^' + $key + '=.*$'
        if (-not [regex]::IsMatch($raw, $pattern)) { throw "Missing configuration key $($item.Key) in .env.example" }
        $raw = [regex]::Replace($raw, $pattern, $item.Key + '=' + $item.Value)
    }
    # Write without UTF-8 BOM (Compose env files must be readable on Windows).
    [System.IO.File]::WriteAllText($dest, $raw, (New-Object System.Text.UTF8Encoding($false)))
    Assert-ConfigSecrets $dest
    Write-Host 'Created .env with random passwords, JWT secret and Fernet key.'
    Write-Host 'IMPORTANT: back up .env securely. Never share it or regenerate it for existing data.'
}

function Verify-Endpoints([int]$WaitSeconds = 75) {
    $urls = @(
        @{Name='Backend health'; Url='http://127.0.0.1:8001/health'},
        @{Name='Swagger'; Url='http://127.0.0.1:8001/api/docs'},
        @{Name='OpenAPI'; Url='http://127.0.0.1:8001/openapi.json'},
        @{Name='Frontend'; Url='http://127.0.0.1:5174/'}
    )
    $end = (Get-Date).AddSeconds($WaitSeconds)
    do {
        $allGood = $true
        $outputs = @{}
        foreach ($item in $urls) {
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri $item.Url -TimeoutSec 5 -ErrorAction Stop
                if ([int]$response.StatusCode -ne 200) { throw 'HTTP status is not 200' }
                $outputs[$item.Name] = [string]$response.Content
            } catch {
                $allGood = $false
                break
            }
        }
        if ($allGood) {
            $health = $outputs['Backend health'] | ConvertFrom-Json
            if ($health.status -ne 'ok') { throw 'Unexpected /health content.' }
            if ($outputs['Swagger'] -notmatch 'swagger-ui') { throw 'Swagger content invalid.' }
            $spec = $outputs['OpenAPI']
            if ($spec -notmatch '/api/v1/auth/login') { throw 'Login endpoint missing.' }
            if ($spec -match '/api/v1/auth/register') { throw 'Public signup must be removed.' }
            Write-Host 'PASS: backend, Swagger, OpenAPI and frontend HTTP 200; public signup removed.' -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $end)
    throw 'API/frontend did not become healthy. Run DIAGNOSE_LMS_WINDOWS.bat.'
}

function Diagnose {
    $report = Join-Path $Root 'KET_QUA_DIAGNOSE.txt'
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('LMS FaceID local diagnostic - review logs before sharing; never share .env')
    $lines.Add(('Time: ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')))
    if (-not (Test-Path (Join-Path $Root '.env'))) {
        $lines.Add('=== SETUP CONFIGURATION ===')
        $lines.Add('No .env file exists. The previous setup stopped before credentials were generated.')
        $lines.Add('Check setup log for the first error, then run V3.3 SETUP_LMS_WINDOWS.bat again.')
        $lines.Add('No database was changed by this diagnosis.')
    } else {
        foreach ($section in @(
            @{Title='Docker containers'; Arguments=@('compose','ps','-a')},
            @{Title='Backend logs (last 120 lines)'; Arguments=@('compose','logs','--tail=120','backend')},
            @{Title='Demo accounts (read-only)'; Arguments=@('compose','exec','-T','backend','python','scripts/diagnose_accounts.py')}
        )) {
            $lines.Add('=== ' + $section.Title + ' ===')
            try {
                $dockerArgs = [string[]]$section.Arguments
                $output = & docker @dockerArgs 2>&1 | Out-String
                $lines.Add($output)
            } catch {
                $lines.Add('Unavailable: ' + $_.Exception.Message)
            }
        }
    }
    foreach ($item in @('http://127.0.0.1:8001/health', 'http://127.0.0.1:8001/api/docs', 'http://127.0.0.1:5174/')) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri $item -TimeoutSec 4
            $lines.Add("$item : HTTP $([int]$r.StatusCode)")
        } catch { $lines.Add("$item : FAILED $($_.Exception.GetType().Name)") }
    }
    [System.IO.File]::WriteAllLines($report, $lines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Saved diagnostic report to $report"
    Start-Process notepad.exe -ArgumentList ('"' + $report + '"')
}

try {
    if ($Action -eq 'Diagnose') {
        Require-Docker
        Diagnose
    } elseif ($Action -eq 'Stop') {
        Require-Docker
        Invoke-Docker -Arguments @('compose','down')
        Write-Host 'Stopped services. Database volume remains intact.'
    } elseif ($Action -eq 'Seed') {
        Require-Docker
        if (-not (Test-Path (Join-Path $Root '.env'))) { throw 'Run SETUP_LMS_WINDOWS.bat first.' }
        $confirm = Read-Host 'Type DEMO to seed an EMPTY local DB; any existing users will block seeding'
        if ($confirm -cne 'DEMO') { Write-Host 'Cancelled.'; exit 0 }
        Invoke-Docker -Arguments @('compose','exec','-T','backend','python','scripts/safe_seed.py')
        Invoke-Docker -Arguments @('compose','exec','-T','backend','python','scripts/diagnose_accounts.py')
        Invoke-Docker -Arguments @('compose','exec','-T','backend','python','scripts/check_demo_logins.py')
        Write-Host 'Demo credentials: admin/gv001/sv001 use Demo@123; others usually DevPass@123.'
    } elseif ($Action -eq 'Test') {
        Require-Docker
        if (-not (Test-Path (Join-Path $Root '.env'))) { throw 'Run SETUP_LMS_WINDOWS.bat first.' }
        Assert-NoForeignPortOwners
        Write-Host '[1/6] Checking HTTP endpoints...'
        Verify-Endpoints 45
        Write-Host '[2/6] Checking FastAPI import/password dependencies...'
        Invoke-Docker -Arguments @('compose','exec','-T','backend','python','scripts/preflight_import.py')
        Write-Host '[3/6] Checking real backend-to-MySQL connection...'
        Invoke-Docker -Arguments @('compose','exec','-T','backend','python','scripts/wait_for_mysql.py')
        Write-Host '[4/6] Inspecting accounts, then testing sample login (creates normal audit entries)...'
        Invoke-Docker -Arguments @('compose','exec','-T','backend','python','scripts/diagnose_accounts.py')
        Invoke-Docker -Arguments @('compose','exec','-T','backend','python','scripts/check_demo_logins.py','--optional')
        Write-Host '[5/6] Running offline FaceID logic + evaluator tests (no model files required)...'
        Invoke-Docker -Arguments @('compose','exec','-T','-e','USE_SQLITE=1','backend','python','scripts/test_faceid_unit.py')
        Write-Host '[6/6] Building React frontend for production (TypeScript + Vite)...'
        Invoke-Docker -Arguments @('compose','exec','-T','frontend','npm','run','build')
        Write-Host 'PASS: HTTP + DB + login account check + FaceID unit tests + frontend build.' -ForegroundColor Green
        Write-Host 'NOTE: camera/model quality and complete MySQL browser E2E are not covered.'
    } elseif ($Action -eq 'Start') {
        Require-Docker
        if (-not (Test-Path (Join-Path $Root '.env'))) { throw 'Run SETUP_LMS_WINDOWS.bat first.' }
        Assert-NoForeignPortOwners
        Invoke-Docker -Arguments @('compose','up','-d')
        Verify-Endpoints 80
        Write-Host 'LMS: http://127.0.0.1:5174 | Swagger: http://127.0.0.1:8001/api/docs'
    } elseif ($Action -eq 'Setup') {
        Require-Docker
        Initialize-Config
        Invoke-Docker -Arguments @('compose','config','--quiet')
        Assert-NoForeignPortOwners
        Write-Host '[1/6] Building containers (requires Internet on first setup)...'
        Invoke-Docker -Arguments @('compose','build','backend','frontend')
        Write-Host '[2/6] Checking app imports + bcrypt + email validation...'
        Invoke-Docker -Arguments @('compose','run','--rm','--no-deps','backend','python','scripts/preflight_import.py')
        Write-Host '[3/6] Starting MySQL...'
        Invoke-Docker -Arguments @('compose','up','-d','--wait','mysql')
        Write-Host '[4/6] Waiting for backend-to-MySQL TCP + credentials, then running migrations...'
        # Docker MySQL first-time initialization can expose a Unix socket before
        # the TCP server is ready. Verify the actual service-to-service path.
        Invoke-Docker -Arguments @('compose','run','--rm','--no-deps','backend','python','scripts/wait_for_mysql.py')
        Invoke-Docker -Arguments @('compose','run','--rm','--no-deps','backend','alembic','upgrade','head')
        Write-Host '[5/6] Downloading YuNet and SFace models (optional for LMS, required for real FaceID)...'
        & docker compose run --rm --no-deps backend python face_tools/download_face_models.py
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Face models could not be downloaded. LMS can still run. Real FaceID will stay not ready.'
            Write-Warning 'Run docker compose run --rm --no-deps backend python face_tools/download_face_models.py later.'
        }
        Write-Host '[6/6] Starting LMS services and checking HTTP endpoints...'
        Invoke-Docker -Arguments @('compose','up','-d','backend','frontend')
        Verify-Endpoints 90
        Write-Host 'SUCCESS: LMS http://127.0.0.1:5174 | API http://127.0.0.1:8001/api/docs' -ForegroundColor Green
        Write-Host 'For a NEW EMPTY demo DB, run SEED_DEMO_WINDOWS.bat ONCE.'
        Write-Host 'Then run TEST_LMS_WINDOWS.bat to check API, DB, login and FaceID unit tests.'
    }
    exit 0
} catch {
    Write-Host ('FAIL: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Database volume was not deleted. No automatic seed or password reset.'
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        # Docker Compose cannot parse the project without the required .env.
        # Avoid flooding the screen with secondary missing-variable errors.
        if (Test-Path (Join-Path $Root '.env')) {
            try {
                & docker compose ps -a
                & docker compose logs --tail=70 backend
            } catch {
                Write-Host 'Docker diagnostics unavailable. Run DIAGNOSE_LMS_WINDOWS.bat after restoring .env.'
            }
        } else {
            Write-Host 'No .env file exists yet: skipped Compose diagnostics to avoid misleading errors.'
            Write-Host 'Fix the first setup error, then rerun SETUP_LMS_WINDOWS.bat.'
        }
    }
    exit 1
} finally {
    if ($TranscriptStarted) { Stop-Transcript | Out-Null }
}
