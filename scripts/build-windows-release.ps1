param(
    [string] $Version = "0.1.0"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Get-XlrPython {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike "*\WindowsApps\python.exe") {
        return $python.Source
    }

    $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $codexPython) {
        return $codexPython
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return $pyLauncher.Source
    }

    throw "Python wurde nicht gefunden. Bitte Python 3.11+ installieren."
}

$python = Get-XlrPython
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $python -m venv .venv
}

& $venvPython -m pip install --upgrade pip pyinstaller

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "XlrDockTray" `
    --add-data "xlr_web\static;xlr_web\static" `
    xlr_dock_tray.py

$releaseDir = Join-Path $repoRoot "dist\release"
$releaseName = "xlr-dock-web-$Version-windows-x64"
$packageDir = Join-Path $releaseDir $releaseName
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $releaseDir
New-Item -ItemType Directory -Force $packageDir | Out-Null

Copy-Item (Join-Path $repoRoot "dist\XlrDockTray.exe") (Join-Path $packageDir "XlrDockTray.exe")
Copy-Item (Join-Path $repoRoot "README.md") $packageDir
Copy-Item (Join-Path $repoRoot "docs\web-app-windows.md") $packageDir

$zipPath = Join-Path $releaseDir "$releaseName.zip"
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force

[pscustomobject]@{
    Exe = (Join-Path $packageDir "XlrDockTray.exe")
    Zip = $zipPath
} | Format-List
