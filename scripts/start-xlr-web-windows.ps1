param(
    [int] $Port = 7137,
    [switch] $NoBrowser,
    [switch] $Persistent,
    [switch] $Check
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$argsList = @("-m", "xlr_web.app", "--host", "127.0.0.1", "--port", "$Port")

if (-not $NoBrowser) {
    $argsList += "--open"
}

if ($Persistent) {
    $argsList += "--persistent"
}

if ($Check) {
    $argsList += "--check"
}

if ($pythonCommand -and $pythonCommand.Source -notlike "*\WindowsApps\python.exe") {
    & $pythonCommand.Source @argsList
    exit $LASTEXITCODE
}

$codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path -LiteralPath $codexPython) {
    & $codexPython @argsList
    exit $LASTEXITCODE
}

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
    & $pyLauncher.Source -3 @argsList
    exit $LASTEXITCODE
}

throw "Python wurde nicht gefunden. Bitte Python 3.11+ installieren oder ueber den Windows Store/winget bereitstellen."
