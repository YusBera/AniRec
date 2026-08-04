param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable was not found: $Python"
}

Push-Location $repoRoot
try {
    & $Python -m PyInstaller --noconfirm --clean "AniRec.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
    $distRoot = Join-Path $repoRoot "dist\AniRec"
    $executable = Join-Path $distRoot "AniRec.exe"
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "Expected executable was not produced: $executable"
    }
    Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination (Join-Path $distRoot "LICENSE") -Force
    Copy-Item -LiteralPath (Join-Path $repoRoot "README.md") -Destination (Join-Path $distRoot "README.md") -Force
    Write-Output $executable
}
finally {
    Pop-Location
}
