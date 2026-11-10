<#
.SYNOPSIS
  One-command local Baaki demo: backend on :8020, production web on :3020, fresh demo story.

.DESCRIPTION
  1. Starts the FastAPI backend on 127.0.0.1:8020 (log: baaki-demo-backend.log in the temp folder printed at start).
  2. Builds the web app with BACKEND_URL=http://127.0.0.1:8020 (baked in at build time). The build is
     skipped when .next is newer than every source file and was built with the same settings;
     -NoBuild always skips it, -Rebuild always builds.
  3. Runs `next start -p 3020` (log: baaki-demo-web.log).
  4. POST /api/demo/reset (Lakshmi's three homes, Rafiq and Rao garu).
  5. Prints the local URLs, including the seeded employer link /e/{token}.
  PIDs go to baaki-demo-pids.json in the same folder; scripts\stop-demo.ps1 stops only those processes.
  Local only: nothing is exposed to the internet.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start-demo.ps1
  powershell -ExecutionPolicy Bypass -File scripts\start-demo.ps1 -NoBuild
  powershell -ExecutionPolicy Bypass -File scripts\start-demo.ps1 -NoInterim   # meter only after stop (fewer STT calls)
#>
[CmdletBinding()]
param(
  [switch]$NoBuild,
  [switch]$Rebuild,
  [switch]$NoInterim,
  [switch]$NoReset,
  [int]$BackendPort = 8020,
  [int]$WebPort = 3020,
  # Public origin used in link previews and in the links Baaki writes into messages.
  [string]$SiteUrl = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Web = Join-Path $Root "web"
# Logs and PIDs: B:\tmp on the author's PC (C: is nearly full), else %TEMP%\baaki-demo.
$OnB = Test-Path "B:\"
$TmpDir = if ($OnB) { "B:\tmp" } else { Join-Path $env:TEMP "baaki-demo" }
$PidFile = Join-Path $TmpDir "baaki-demo-pids.json"
$StampFile = Join-Path $Web ".next-demo\baaki-demo-build.json"
if (-not $SiteUrl) { $SiteUrl = "http://localhost:$WebPort" }
$SiteUrl = $SiteUrl.TrimEnd("/")
$BackendUrl = "http://127.0.0.1:$BackendPort"
$WebUrl = "http://localhost:$WebPort"

New-Item -ItemType Directory -Force $TmpDir | Out-Null
Write-Host "Logs and PIDs: $TmpDir"
if ($OnB) {
  $env:TMP = $TmpDir; $env:TEMP = $TmpDir
  $env:PIP_CACHE_DIR = "B:\pip-cache"; $env:npm_config_cache = "B:\npm-cache"
}
$env:NEXT_TELEMETRY_DISABLED = "1"
$env:NEXT_DIST_DIR = ".next-demo"   # own build folder, safe from other builds

function Test-PortInUse([int]$Port) {
  $c = New-Object System.Net.Sockets.TcpClient
  try { $c.Connect("127.0.0.1", $Port); return $true } catch { return $false } finally { $c.Close() }
}

function Wait-Http([string]$Url, [int]$Seconds, [System.Diagnostics.Process]$Proc, [string]$Log) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if ($Proc -and $Proc.HasExited) { throw "Process exited early; see $Log" }
    try {
      $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($r.StatusCode -lt 500) { return }
    } catch { }
    Start-Sleep -Milliseconds 700
  }
  throw "Timed out waiting for $Url; see $Log"
}

function Save-Pids($Data) { $Data | ConvertTo-Json | Set-Content -Path $PidFile -Encoding UTF8 }

# ------------------------------------------------------------------ already running?
if (Test-Path $PidFile) {
  $old = Get-Content $PidFile -Raw | ConvertFrom-Json
  $alive = @($old.backend, $old.web) | Where-Object { $_ -and (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
  if ($alive) { throw "A demo is already running (PIDs $($alive -join ', ')). Run scripts\stop-demo.ps1 first." }
  Remove-Item $PidFile -Force
}
foreach ($p in @($BackendPort, $WebPort)) {
  if (Test-PortInUse $p) { throw "Port $p is already in use by another program. Free it or pass -BackendPort / -WebPort." }
}

$Python = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Backend venv not found at $Python (see README: Run)." }
$NextBin = Join-Path $Web "node_modules\next\dist\bin\next"
if (-not (Test-Path $NextBin)) { throw "web\node_modules missing: run 'npm ci' in web first." }
$Node = (Get-Command node -ErrorAction Stop).Source

$pids = [ordered]@{ backend = $null; web = $null; backend_port = $BackendPort; web_port = $WebPort; started = (Get-Date).ToString("s") }

# ------------------------------------------------------------------ 1. backend
$BackendLog = Join-Path $TmpDir "baaki-demo-backend.log"
$env:PUBLIC_BASE_URL = $SiteUrl   # links in messages and share text
Write-Host "Starting backend on $BackendUrl (log: $BackendLog)"
$be = Start-Process -FilePath $Python -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
  -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "$BackendPort") `
  -RedirectStandardOutput $BackendLog -RedirectStandardError "$BackendLog.err"
$pids.backend = $be.Id
Save-Pids $pids
try {
  Wait-Http "$BackendUrl/health" 60 $be "$BackendLog.err"

  # ---------------------------------------------------------------- 2. web build (only when needed)
  $settings = [ordered]@{
    BACKEND_URL = $BackendUrl
    NEXT_PUBLIC_SITE_URL = $SiteUrl
    NEXT_PUBLIC_BAAKI_INTERIM_MS = $(if ($NoInterim) { "0" } else { "4500" })
  }
  $needBuild = $true
  $buildId = Join-Path $Web ".next-demo\BUILD_ID"
  if ($NoBuild) {
    if (-not (Test-Path $buildId)) { throw "-NoBuild given but there is no build in web\.next-demo. Run once without -NoBuild." }
    $needBuild = $false
  } elseif (-not $Rebuild -and (Test-Path $buildId) -and (Test-Path $StampFile)) {
    $built = (Get-Item $buildId).LastWriteTimeUtc
    $sources = @("app", "components", "hooks", "lib", "public") | ForEach-Object { Join-Path $Web $_ } | Where-Object { Test-Path $_ } |
      ForEach-Object { Get-ChildItem $_ -Recurse -File }
    $sources += @("next.config.ts", "package.json", "package-lock.json", "tsconfig.json", "postcss.config.mjs") |
      ForEach-Object { Join-Path $Web $_ } | Where-Object { Test-Path $_ } | ForEach-Object { Get-Item $_ }
    $newest = ($sources | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
    $stamp = Get-Content $StampFile -Raw | ConvertFrom-Json
    $same = ($stamp.BACKEND_URL -eq $settings.BACKEND_URL) -and ($stamp.NEXT_PUBLIC_SITE_URL -eq $settings.NEXT_PUBLIC_SITE_URL) -and
      ($stamp.NEXT_PUBLIC_BAAKI_INTERIM_MS -eq $settings.NEXT_PUBLIC_BAAKI_INTERIM_MS)
    if ($same -and $newest -le $built) { $needBuild = $false }
  }
  foreach ($k in $settings.Keys) { Set-Item -Path "env:$k" -Value $settings[$k] }
  if ($needBuild) {
    $BuildLog = Join-Path $TmpDir "baaki-demo-build.log"
    Write-Host "Building web (BACKEND_URL=$BackendUrl; log: $BuildLog) ..."
    Push-Location $Web
    $eap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"   # Windows PowerShell turns native stderr lines into errors
    try {
      # cmd does the redirect so the log stays plain UTF-8 (PowerShell 5.1 would write UTF-16)
      & cmd.exe /d /c "`"$Node`" `"$NextBin`" build > `"$BuildLog`" 2>&1"
      $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $eap; Pop-Location }
    if ($code -ne 0) { throw "next build failed; see $BuildLog" }
    $settings | ConvertTo-Json | Set-Content -Path $StampFile -Encoding UTF8
  } else {
    Write-Host "Web build is up to date (use -Rebuild to force)."
  }

  # ---------------------------------------------------------------- 3. next start
  $WebLog = Join-Path $TmpDir "baaki-demo-web.log"
  Write-Host "Starting web on $WebUrl (log: $WebLog)"
  $wb = Start-Process -FilePath $Node -WorkingDirectory $Web -WindowStyle Hidden -PassThru `
    -ArgumentList @("`"$NextBin`"", "start", "-p", "$WebPort", "-H", "127.0.0.1") `
    -RedirectStandardOutput $WebLog -RedirectStandardError "$WebLog.err"
  $pids.web = $wb.Id
  Save-Pids $pids
  Wait-Http "$WebUrl/api/health" 90 $wb "$WebLog.err"

  # ---------------------------------------------------------------- 4. fresh demo story
  $token = $null
  if (-not $NoReset) {
    # Public mode (BAAKI_PUBLIC=1) needs the admin token on demo resets; pass it through the environment if set.
    $adm = @{}; if ($env:BAAKI_ADMIN_TOKEN) { $adm["X-Admin-Token"] = $env:BAAKI_ADMIN_TOKEN }
    $seed = Invoke-RestMethod -Method Post -Uri "$BackendUrl/api/demo/reset" -Headers $adm -TimeoutSec 60
    $token = $seed.employer_tokens.sharma
    $sharmaCase = $seed.cases.sharma
    $lakshmi = $seed.workers.lakshmi
    # Add-on demos: Haq Raise (Mehta madam) and "Baaki for every promise" (milkman, chit).
    try { $raise = Invoke-RestMethod -Method Post -Uri "$BackendUrl/api/raise/demo" -Headers $adm -ContentType "application/json" -Body '{"audio":true}' -TimeoutSec 120 } catch { Write-Warning "Haq Raise demo seed failed: $_" }
    try { $null = Invoke-RestMethod -Method Post -Uri "$BackendUrl/api/dues/demo" -Headers $adm -TimeoutSec 60 } catch { Write-Warning "Dues demo seed failed: $_" }
  }
} catch {
  Write-Warning $_
  Write-Warning "Stopping what this script started."
  & (Join-Path $PSScriptRoot "stop-demo.ps1")
  exit 1
}

# ------------------------------------------------------------------ 5. URLs
Write-Host ""
Write-Host "Baaki demo is running (local only)." -ForegroundColor Green
Write-Host "  Website        $WebUrl/"
Write-Host "  Worker app     $WebUrl/app"
Write-Host "  Fair Pay Check $WebUrl/check"
Write-Host "  Fair or Not    $WebUrl/quiz"
Write-Host "  Be Sharma ji   $WebUrl/try/employer   (public sandbox, cached audio only)"
Write-Host "  Noise proof    $WebUrl/proof"
if ($token) {
  Write-Host "  Employer link  $WebUrl/e/$token   (Sharma ji, case $sharmaCase)"
  if ($raise) { Write-Host "  Haq Raise      $WebUrl$($raise.worker_path)   (worker)  |  $WebUrl$($raise.employer_path)   (employer)" } else { Write-Host "  Haq Raise      $WebUrl/raise/<case>   (POST /api/raise/demo failed; see the warning above)" }
  Write-Host "  Other dues     $WebUrl/dues   (milkman, chit)"
  Write-Host "  Case           $WebUrl/case/$sharmaCase"
  Write-Host "  Case Replay    $WebUrl/story/$sharmaCase"
  Write-Host "  Hisaab Milao   $WebUrl/hisaab/$sharmaCase   (worker)  |  $WebUrl/hisaab/e/$token   (employer)"
  Write-Host "  Replies inbox  $WebUrl/inbox/$sharmaCase"
  Write-Host "  Exit Kit       $WebUrl/exit?case=$sharmaCase"
  if ($lakshmi) { Write-Host "  Voice consent  $WebUrl/voice/consent?worker=$lakshmi   (spoken consent; uses live Prisma STT)" }
}
Write-Host "  Backend        $BackendUrl/health"
Write-Host ""
Write-Host "Mic: works on localhost in desktop Chrome (use DevTools device mode for a phone frame)."
Write-Host "Stop with: powershell -ExecutionPolicy Bypass -File scripts\stop-demo.ps1"
