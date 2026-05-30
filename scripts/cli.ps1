param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$TempDir = Join-Path $Root ".temp"
$EggInfoDir = Join-Path $TempDir "egg-info"
$env:UV_CACHE_DIR = Join-Path $TempDir "uv-cache"
$env:PYTHONPYCACHEPREFIX = Join-Path $TempDir "pycache"
$env:UV_PROJECT_ENVIRONMENT = Join-Path $TempDir ".venv"

New-Item -ItemType Directory -Force $EggInfoDir, $env:UV_CACHE_DIR, $env:PYTHONPYCACHEPREFIX, $env:UV_PROJECT_ENVIRONMENT | Out-Null

& uv run --project backend omedia @CliArgs
exit $LASTEXITCODE
