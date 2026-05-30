param(
    [ValidateSet("start", "stop", "restart")]
    [string]$Action = "start",
    [string]$HostName = "127.0.0.1",
    [int]$BackendPort = 7100,
    [int]$FrontendPort = 7108
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$TempDir = Join-Path $Root ".temp"
$LogDir = Join-Path $TempDir "run-logs"
$PidDir = Join-Path $TempDir "run-pids"
$EggInfoDir = Join-Path $TempDir "egg-info"
$UvCacheDir = Join-Path $TempDir "uv-cache"
$PyCacheDir = Join-Path $TempDir "pycache"
$ProjectEnvDir = Join-Path $TempDir ".venv"
$NpmCacheDir = Join-Path $TempDir "npm-cache"

function Ensure-DevDirs {
    New-Item -ItemType Directory -Force $LogDir, $PidDir, $EggInfoDir, $UvCacheDir, $PyCacheDir, $ProjectEnvDir, $NpmCacheDir | Out-Null
}

function Get-DevPidPath([string]$Name) {
    Join-Path $PidDir "$Name.pid"
}

function Test-DevProcess([int]$ProcessId) {
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        return -not $process.HasExited
    }
    catch {
        return $false
    }
}

function Stop-DevProcessTree([int]$ProcessId) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-DevProcessTree ([int]$child.ProcessId)
    }
    if (Test-DevProcess $ProcessId) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-DevProcess([string]$Name) {
    $pidPath = Get-DevPidPath $Name
    if (-not (Test-Path -LiteralPath $pidPath)) {
        Write-Host "$Name is not running."
        return
    }

    $rawPid = (Get-Content -LiteralPath $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($rawPid -and (Test-DevProcess ([int]$rawPid))) {
        Stop-DevProcessTree ([int]$rawPid)
        Write-Host "Stopped $Name process $rawPid."
    }
    else {
        Write-Host "$Name pid file was stale."
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

function Start-DevProcess(
    [string]$Name,
    [string]$WorkingDirectory,
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$OutLog,
    [string]$ErrLog
) {
    $pidPath = Get-DevPidPath $Name
    if (Test-Path -LiteralPath $pidPath) {
        $rawPid = (Get-Content -LiteralPath $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($rawPid -and (Test-DevProcess ([int]$rawPid))) {
            Write-Host "$Name is already running as process $rawPid."
            return
        }
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    }

    $process = Start-Process $FilePath `
        -WorkingDirectory $WorkingDirectory `
        -ArgumentList $ArgumentList `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ASCII
    Write-Host "Started $Name process $($process.Id)."
}

function Resolve-Executable([string[]]$Names) {
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            return $command.Source
        }
    }
    throw "Unable to find executable: $($Names -join ', ')"
}

Ensure-DevDirs

if ($Action -eq "stop" -or $Action -eq "restart") {
    Stop-DevProcess "frontend"
    Stop-DevProcess "backend"
}

if ($Action -eq "start" -or $Action -eq "restart") {
    $backendOut = Join-Path $LogDir "backend-dev.out.log"
    $backendErr = Join-Path $LogDir "backend-dev.err.log"
    $frontendOut = Join-Path $LogDir "frontend-dev.out.log"
    $frontendErr = Join-Path $LogDir "frontend-dev.err.log"

    $env:UV_CACHE_DIR = $UvCacheDir
    $env:PYTHONPYCACHEPREFIX = $PyCacheDir
    $env:UV_PROJECT_ENVIRONMENT = $ProjectEnvDir
    $env:NPM_CONFIG_CACHE = $NpmCacheDir
    $env:VITE_OMEDIA_PROXY_TARGET = "http://$HostName`:$BackendPort"
    $uvCommand = Resolve-Executable @("uv.exe", "uv")
    $npmCommand = Resolve-Executable @("npm.cmd", "npm.exe", "npm")

    Start-DevProcess -Name "backend" -WorkingDirectory $Root -FilePath $uvCommand -ArgumentList @(
        "run",
        "--project",
        "backend",
        "--extra",
        "dev",
        "uvicorn",
        "app.main:app",
        "--host",
        $HostName,
        "--port",
        "$BackendPort",
        "--reload"
    ) -OutLog $backendOut -ErrLog $backendErr
    Start-DevProcess -Name "frontend" -WorkingDirectory (Join-Path $Root "frontend") -FilePath $npmCommand -ArgumentList @(
        "run",
        "dev",
        "--",
        "--host=$HostName",
        "--port=$FrontendPort"
    ) -OutLog $frontendOut -ErrLog $frontendErr

    Write-Host "Backend:  http://$HostName`:$BackendPort"
    Write-Host "Frontend: http://$HostName`:$FrontendPort"
    Write-Host "Logs:     $LogDir"
}
