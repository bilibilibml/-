$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$url = 'http://127.0.0.1:8765/'
try {
    $status = Invoke-RestMethod -Uri ($url + 'api/status') -TimeoutSec 2
    if ($status.engine -ne 'Kirikiroid2 Web') { throw 'Port 8765 is occupied by another application.' }
} catch {
    $python = (Get-Command python -ErrorAction Stop).Source
    Start-Process -FilePath $python -ArgumentList @(('"' + (Join-Path $root 'server.py') + '"')) -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'case/startup.log') -RedirectStandardError (Join-Path $root 'case/startup-error.log') | Out-Null
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 300
        try {
            $status = Invoke-RestMethod -Uri ($url + 'api/status') -TimeoutSec 1
            if ($status.engine -eq 'Kirikiroid2 Web') { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) { throw 'Startup failed. See case/startup-error.log.' }
}
Start-Process $url
