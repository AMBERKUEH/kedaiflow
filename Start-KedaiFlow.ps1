param([switch]$SkipBuild, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$localDir = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Force -Path $localDir | Out-Null
if (Test-Path -LiteralPath (Join-Path $localDir 'processes.json')) { throw 'A prior launch is recorded. Run Stop-KedaiFlow.ps1 before starting again.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv; if ($LASTEXITCODE) { throw 'Python environment creation failed.' } }
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $pythonExe -m pip install -r requirements.lock.txt
if ($LASTEXITCODE) { throw 'Backend dependency installation failed.' }
& $pythonExe -m scripts.migrate
if ($LASTEXITCODE) { throw 'Database migration failed.' }
& $pythonExe -m services.api.seed
if ($LASTEXITCODE) { throw 'Fixture seed failed.' }
$webDir = Join-Path $projectRoot 'apps\companion'
Push-Location -LiteralPath $webDir
try {
    npm.cmd ci
    if ($LASTEXITCODE) { throw 'Frontend dependency installation failed.' }
    if (-not $SkipBuild) { npm.cmd run build; if ($LASTEXITCODE) { throw 'Frontend build failed.' } }
} finally { Pop-Location }
$launches = @()
$apiProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','services.api.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localDir 'api.log') -RedirectStandardError (Join-Path $localDir 'api-error.log')
$launches += @{Id=$apiProcess.Id;StartTime=$apiProcess.StartTime.ToUniversalTime().ToString('o')}
$workerProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','services.api.worker' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localDir 'worker.log') -RedirectStandardError (Join-Path $localDir 'worker-error.log')
$launches += @{Id=$workerProcess.Id;StartTime=$workerProcess.StartTime.ToUniversalTime().ToString('o')}
$nodeExe = (Get-Command node.exe).Source
$webProcess = Start-Process -FilePath $nodeExe -ArgumentList 'node_modules\next\dist\bin\next','start','--hostname','127.0.0.1' -WorkingDirectory $webDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localDir 'web.log') -RedirectStandardError (Join-Path $localDir 'web-error.log')
$launches += @{Id=$webProcess.Id;StartTime=$webProcess.StartTime.ToUniversalTime().ToString('o')}
$launches | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $localDir 'processes.json')
Write-Host 'KedaiFlow is starting at http://localhost:3000. API documentation: http://localhost:8000/docs'
Write-Host 'Choose Explore a sample kedai, or register a separate business for your own records.'
if (-not $NoBrowser) { Start-Process 'http://localhost:3000' }
