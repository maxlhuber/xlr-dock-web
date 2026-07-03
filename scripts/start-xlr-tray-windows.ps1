param(
    [int] $Port = 7137,
    [switch] $Open,
    [switch] $Persistent
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Get-XlrPython {
    $pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pythonw -and $pythonw.Source -notlike "*\WindowsApps\pythonw.exe") {
        return $pythonw.Source
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike "*\WindowsApps\python.exe") {
        return $python.Source
    }

    $codexPythonw = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
    if (Test-Path -LiteralPath $codexPythonw) {
        return $codexPythonw
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

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
    Start-Process "http://127.0.0.1:$Port/"
    Write-Host "Die XLR-Dock-Web-App laeuft bereits auf Port $Port."
    exit 0
}

$python = Get-XlrPython
$argsList = @("-m", "xlr_web.tray", "--host", "127.0.0.1", "--port", "$Port")

if ($Open) {
    $argsList += "--open"
}

if ($Persistent) {
    $argsList += "--persistent"
}

if ((Split-Path -Leaf $python) -ieq "py.exe") {
    $argsList = @("-3") + $argsList
}

Start-Process -FilePath $python -ArgumentList $argsList -WorkingDirectory $repoRoot -WindowStyle Hidden
Write-Host "XLR-Dock-Tray-App gestartet. Webinterface: http://127.0.0.1:$Port/"
