param(
    [string]$Version = "0.1.0",
    [string]$WinSWVersion = "v2.12.0"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$TempDir = Join-Path $Root ".temp"
$EggInfoDir = Join-Path $TempDir "egg-info"
$env:UV_CACHE_DIR = Join-Path $TempDir "uv-cache"
$env:PYTHONPYCACHEPREFIX = Join-Path $TempDir "pycache"
$env:UV_PROJECT_ENVIRONMENT = Join-Path $TempDir ".venv"
$env:NPM_CONFIG_CACHE = Join-Path $TempDir "npm-cache"

$WinSWDir = Join-Path $Root "dist\windows\winsw"
$WinSWPath = Join-Path $WinSWDir "omedia-service.exe"

New-Item -ItemType Directory -Force $EggInfoDir, $env:UV_CACHE_DIR, $env:PYTHONPYCACHEPREFIX, $env:UV_PROJECT_ENVIRONMENT, $env:NPM_CONFIG_CACHE, $WinSWDir | Out-Null

Push-Location (Join-Path $Root "frontend")
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Push-Location $Root
try {
    & uv run --project backend --extra package pyinstaller --clean --noconfirm --distpath dist\windows --workpath .temp\pyinstaller packaging\windows\omedia.spec
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not (Test-Path -LiteralPath $WinSWPath)) {
        $url = "https://github.com/winsw/winsw/releases/download/$WinSWVersion/WinSW-x64.exe"
        Invoke-WebRequest -Uri $url -OutFile $WinSWPath
    }

    $iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    $isccPath = if ($iscc) { $iscc.Source } else { $null }
    if (-not $isccPath) {
        $candidate = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
        if (Test-Path -LiteralPath $candidate) {
            $isccPath = $candidate
        }
    }
    if (-not $isccPath) {
        throw "Unable to find ISCC.exe. Install Inno Setup 6 first."
    }

    & $isccPath "/DOMEDIA_VERSION=$Version" packaging\windows\omedia.iss
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
