<#
.SYNOPSIS
  Re-warm the demo's voice clips on filming morning (needs scripts\start-demo.ps1 running).

.DESCRIPTION
  Runs backend\scripts\warm_demo.py against the local backend: makes Sharma ji's Polite note, the
  filming-story read-back and the "Paisa aa gaya" alert, then resets the demo story. Clips already in
  the cache cost nothing; the Polite note's reply-by date changes daily, so expect 1 Timbre call per day.
  -Export also copies the date-independent clips into backend\seed_cache (commit them afterwards).
  -LiveConsent also warms Rafiq's Hinglish voice-consent sentence (/voice/consent): 1 live Timbre call the
  first time, then cached. Off by default.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\warm-demo.ps1
  powershell -ExecutionPolicy Bypass -File scripts\warm-demo.ps1 -Export -Rao
  powershell -ExecutionPolicy Bypass -File scripts\warm-demo.ps1 -LiveConsent -Export
#>
param([switch]$Export, [switch]$Rao, [switch]$LiveConsent, [int]$BackendPort = 8020)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:TMP = "B:\tmp"; $env:TEMP = "B:\tmp"; $env:PIP_CACHE_DIR = "B:\pip-cache"
$env:PYTHONIOENCODING = "utf-8"
$py = Join-Path $Root "backend\.venv\Scripts\python.exe"
$argv = @((Join-Path $Root "backend\scripts\warm_demo.py"), "--base", "http://127.0.0.1:$BackendPort")
if ($Export) { $argv += "--export" }
if ($Rao) { $argv += "--rao" }
if ($LiveConsent) { $argv += "--live-consent" }
& $py @argv
exit $LASTEXITCODE
