<#
.SYNOPSIS
  Stops the Baaki demo started by scripts\start-demo.ps1, and nothing else.

.DESCRIPTION
  Reads the PIDs from B:\tmp\baaki-demo-pids.json and ends each one with its child processes
  (the venv python launcher and Next.js both start children). Other programs on other ports are untouched.
#>
$ErrorActionPreference = "Continue"
$PidFile = "B:\tmp\baaki-demo-pids.json"
if (-not (Test-Path $PidFile)) {
  Write-Host "No demo PID file ($PidFile): nothing to stop."
  exit 0
}
$data = Get-Content $PidFile -Raw | ConvertFrom-Json
foreach ($name in @("web", "backend")) {
  $id = $data.$name
  if (-not $id) { continue }
  $p = Get-Process -Id $id -ErrorAction SilentlyContinue
  if (-not $p) {
    Write-Host "$name (PID $id) is not running."
    continue
  }
  # A recycled PID would belong to some other program: only stop python/node processes.
  if ($p.ProcessName -notin @("python", "node")) {
    Write-Warning "PID $id is now '$($p.ProcessName)', not the demo $name; leaving it alone."
    continue
  }
  & taskkill.exe /PID $id /T /F | Out-Null
  Write-Host "Stopped $name (PID $id)."
}
Remove-Item $PidFile -Force
