param(
    [string]$Version = "1.2.0"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $repoRoot "dist\AniRec"
$releaseRoot = Join-Path $repoRoot "release"
$bundleName = "AniRec-$Version-Windows-x64"
$bundleRoot = Join-Path $releaseRoot $bundleName
$archivePath = Join-Path $releaseRoot "$bundleName.zip"

if (-not (Test-Path -LiteralPath (Join-Path $distRoot "AniRec.exe") -PathType Leaf)) {
    throw "Build the onedir artifact first with scripts\build_windows.ps1."
}
if ((Test-Path -LiteralPath $bundleRoot) -or (Test-Path -LiteralPath $archivePath)) {
    throw "Release output already exists. Move or remove the exact versioned output before rebuilding: $bundleName"
}

New-Item -ItemType Directory -Path $bundleRoot -Force | Out-Null
Copy-Item -LiteralPath $distRoot -Destination (Join-Path $bundleRoot "AniRec") -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot "docs\USER_ACCEPTANCE_TEMPLATE.md") -Destination (Join-Path $bundleRoot "USER_ACCEPTANCE.md")
Copy-Item -LiteralPath (Join-Path $repoRoot "docs\RELEASE_CANDIDATE_REPORT.md") -Destination (Join-Path $bundleRoot "RELEASE_CANDIDATE_REPORT.md")
Copy-Item -LiteralPath (Join-Path $repoRoot "docs\EXE_SMOKE.md") -Destination (Join-Path $bundleRoot "DEVELOPMENT_MACHINE_SMOKE.md")
Copy-Item -LiteralPath (Join-Path $repoRoot "scripts\verify_windows_acceptance.ps1") -Destination (Join-Path $bundleRoot "verify_windows_acceptance.ps1")

$entries = Get-ChildItem -LiteralPath $bundleRoot -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {
        [PSCustomObject]@{
            Path = $_.FullName.Substring($bundleRoot.Length + 1).Replace("\", "/")
            SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            Bytes = $_.Length
        }
    }
$entries | Export-Csv -LiteralPath (Join-Path $bundleRoot "SHA256SUMS.csv") -NoTypeInformation -Encoding UTF8

Compress-Archive -Path (Join-Path $bundleRoot "*") -DestinationPath $archivePath -CompressionLevel Optimal
$archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
Write-Output "Bundle=$bundleRoot"
Write-Output "Archive=$archivePath"
Write-Output "ArchiveSHA256=$archiveHash"
