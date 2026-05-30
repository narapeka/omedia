param(
    [switch]$SkipCompile,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$TempDir = Join-Path $Root ".temp"
$EggInfoDir = Join-Path $TempDir "egg-info"
$env:UV_CACHE_DIR = Join-Path $TempDir "uv-cache"
$env:PYTHONPYCACHEPREFIX = Join-Path $TempDir "pycache"
$env:UV_PROJECT_ENVIRONMENT = Join-Path $TempDir ".venv"
$PytestCacheDir = Join-Path $TempDir "pytest-cache"

New-Item -ItemType Directory -Force $EggInfoDir, $env:UV_CACHE_DIR, $env:PYTHONPYCACHEPREFIX, $env:UV_PROJECT_ENVIRONMENT, $PytestCacheDir | Out-Null

if (-not $PytestArgs -or $PytestArgs.Count -eq 0) {
    $PytestArgs = @("backend/tests")
}

if (-not $SkipCompile) {
    & uv run --project backend --extra dev python -m compileall -q backend\app
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& uv run --project backend --extra dev python -m pytest -o "cache_dir=$PytestCacheDir" @PytestArgs
exit $LASTEXITCODE
