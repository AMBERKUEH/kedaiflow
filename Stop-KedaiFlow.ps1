$ErrorActionPreference = 'Stop'
$manifestPath = Join-Path $PSScriptRoot '.local\processes.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { Write-Host 'No launcher-owned processes recorded.'; exit }
$records = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($record in $records) {
    $running = Get-Process -Id $record.Id -ErrorAction SilentlyContinue
    if ($running -and $running.StartTime.ToUniversalTime().ToString('o') -eq $record.StartTime) {
        # Stop only children of this exact recorded process, then the parent.
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $($record.Id)" | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $record.Id -ErrorAction SilentlyContinue
    }
}
Remove-Item -LiteralPath $manifestPath
Write-Host 'Launcher-owned KedaiFlow services stopped. Business records preserved.'
