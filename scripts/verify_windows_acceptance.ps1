param(
    [switch]$Launch
)

$ErrorActionPreference = "Stop"
$packageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$appRoot = Join-Path $packageRoot "AniRec"
$executable = Join-Path $appRoot "AniRec.exe"
$manifestPath = Join-Path $packageRoot "SHA256SUMS.csv"
$resultPath = Join-Path $packageRoot "ACCEPTANCE_STATIC_RESULTS.txt"
$results = [Collections.Generic.List[string]]::new()
$failures = [Collections.Generic.List[string]]::new()

function Add-Result {
    param(
        [bool]$Passed,
        [string]$Name,
        [string]$Detail
    )
    $status = if ($Passed) { "PASS" } else { "FAIL" }
    $line = "$status | $Name | $Detail"
    $results.Add($line)
    Write-Output $line
    if (-not $Passed) {
        $failures.Add($Name)
    }
}

Write-Output "AniRec 1.2.2 Windows acceptance preflight"
Write-Output "Package root: $packageRoot"

$os = Get-CimInstance Win32_OperatingSystem
$windowsBuild = [Environment]::OSVersion.Version.Build
$windowsSupported = $os.Version -like "10.*" -and $windowsBuild -ge 10240
Add-Result $windowsSupported "Windows version" "$($os.Caption), version $($os.Version), build $windowsBuild"
Add-Result ([Environment]::Is64BitOperatingSystem) "64-bit Windows" "Required by the x64 AniRec executable"

$required = @(
    "AniRec\AniRec.exe",
    "AniRec\LICENSE",
    "AniRec\README.md",
    "AniRec\_internal\gui\resources\ASSET_LICENSES.md",
    "AniRec\_internal\gui\resources\icons\anirec.ico",
    "AniRec\_internal\gui\resources\icons\anirec.svg",
    "AniRec\_internal\gui\resources\images\anime-cover-placeholder.svg",
    "AniRec\_internal\gui\resources\images\anime-placeholder.svg",
    "AniRec\_internal\gui\resources\styles\dark.qss",
    "AniRec\_internal\gui\resources\styles\light.qss",
    "SHA256SUMS.csv",
    "USER_ACCEPTANCE.md"
)
foreach ($relative in $required) {
    $path = Join-Path $packageRoot $relative
    Add-Result (Test-Path -LiteralPath $path -PathType Leaf) "Required file" $relative
}

if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    $manifest = @(Import-Csv -LiteralPath $manifestPath)
    $verified = 0
    foreach ($entry in $manifest) {
        $relative = [string]$entry.Path
        if ([IO.Path]::IsPathRooted($relative) -or $relative -match "(^|[\\/])\.\.([\\/]|$)") {
            Add-Result $false "Manifest path safety" $relative
            continue
        }
        $candidate = [IO.Path]::GetFullPath((Join-Path $packageRoot ($relative -replace "/", [IO.Path]::DirectorySeparatorChar)))
        if (-not $candidate.StartsWith($packageRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            Add-Result $false "Manifest path safety" $relative
            continue
        }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            Add-Result $false "Manifest file" "$relative is missing"
            continue
        }
        $actual = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash
        if ($actual -ne $entry.SHA256) {
            Add-Result $false "Manifest hash" "$relative does not match"
            continue
        }
        if ((Get-Item -LiteralPath $candidate).Length -ne [long]$entry.Bytes) {
            Add-Result $false "Manifest size" "$relative does not match"
            continue
        }
        $verified++
    }
    Add-Result ($verified -eq $manifest.Count -and $manifest.Count -gt 0) "SHA-256 manifest" "$verified of $($manifest.Count) files verified"
}

if (Test-Path -LiteralPath $executable -PathType Leaf) {
    $versionInfo = (Get-Item -LiteralPath $executable).VersionInfo
    Add-Result ($versionInfo.FileVersion -eq "1.2.2" -and $versionInfo.ProductVersion -eq "1.2.2") "EXE version" "File $($versionInfo.FileVersion), product $($versionInfo.ProductVersion)"

    $bytes = [IO.File]::ReadAllBytes($executable)
    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    $machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
    $subsystem = [BitConverter]::ToUInt16($bytes, $peOffset + 24 + 68)
    Add-Result ($machine -eq 0x8664) "EXE architecture" ("Machine 0x{0:X4}" -f $machine)
    Add-Result ($subsystem -eq 2) "No-console GUI subsystem" "PE subsystem $subsystem"

    $signature = Get-AuthenticodeSignature -LiteralPath $executable
    $signatureDetail = "Authenticode status $($signature.Status)"
    Add-Result $true "Code-signing disclosure" $signatureDetail
}

$results.Insert(0, "Generated: $([DateTimeOffset]::Now.ToString('o'))")
$results.Insert(1, "OS: $($os.Caption) $($os.Version), build $windowsBuild")
$results | Set-Content -LiteralPath $resultPath -Encoding UTF8
Write-Output "Static result file: $resultPath"

if ($failures.Count -gt 0) {
    Write-Error "Acceptance preflight failed: $($failures -join ', ')"
    exit 1
}

if ($Launch) {
    Write-Output "Launching AniRec for the interactive checklist. Keep the complete AniRec directory together."
    Start-Process -FilePath $executable -WorkingDirectory $appRoot
}

Write-Output "Preflight completed successfully. Continue with USER_ACCEPTANCE.md."
exit 0
