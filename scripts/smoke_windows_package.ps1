param(
    [string]$Executable = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Executable) {
    $Executable = Join-Path $repoRoot "dist\AniRec\AniRec.exe"
}
$Executable = [IO.Path]::GetFullPath($Executable)
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    throw "Packaged executable was not found: $Executable"
}

Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class AniRecWindowSmoke
{
    private delegate bool EnumWindowsProc(IntPtr handle, IntPtr state);
    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr state);
    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr handle, out uint processId);
    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr handle);
    [DllImport("user32.dll")]
    private static extern bool PostMessage(IntPtr handle, uint message, IntPtr wParam, IntPtr lParam);

    public static int CountVisibleWindows(uint targetProcessId)
    {
        int count = 0;
        EnumWindows(delegate(IntPtr handle, IntPtr state) {
            uint processId;
            GetWindowThreadProcessId(handle, out processId);
            if (processId == targetProcessId && IsWindowVisible(handle)) {
                count++;
            }
            return true;
        }, IntPtr.Zero);
        return count;
    }

    public static int RequestNormalClose(uint targetProcessId)
    {
        int count = 0;
        EnumWindows(delegate(IntPtr handle, IntPtr state) {
            uint processId;
            GetWindowThreadProcessId(handle, out processId);
            if (processId == targetProcessId) {
                PostMessage(handle, 0x0010, IntPtr.Zero, IntPtr.Zero);
                count++;
            }
            return true;
        }, IntPtr.Zero);
        return count;
    }
}
'@

$temporaryBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$temporaryRoot = Join-Path $temporaryBase ("anirec-package-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
$process = $null
$forced = $false
$visibleWindows = 0
try {
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Executable
    $startInfo.WorkingDirectory = Split-Path -Parent $Executable
    $startInfo.UseShellExecute = $false
    $startInfo.EnvironmentVariables["APPDATA"] = $temporaryRoot
    $process = [Diagnostics.Process]::Start($startInfo)

    $launchDeadline = [DateTime]::UtcNow.AddSeconds(20)
    while (-not $process.HasExited -and [DateTime]::UtcNow -lt $launchDeadline) {
        $visibleWindows = [AniRecWindowSmoke]::CountVisibleWindows([uint32]$process.Id)
        if ($visibleWindows -gt 0) {
            break
        }
        Start-Sleep -Milliseconds 250
        $process.Refresh()
    }

    $closeDeadline = [DateTime]::UtcNow.AddSeconds(20)
    while (-not $process.HasExited -and [DateTime]::UtcNow -lt $closeDeadline) {
        [AniRecWindowSmoke]::RequestNormalClose([uint32]$process.Id) | Out-Null
        Start-Sleep -Milliseconds 350
        $process.Refresh()
    }
    if (-not $process.HasExited) {
        $forced = $true
        $process.Kill()
        $process.WaitForExit()
    }

    [PSCustomObject]@{
        ProcessId = $process.Id
        VisibleWindows = $visibleWindows
        ForcedTermination = $forced
        ExitCode = $process.ExitCode
    } | Format-List

    if ($visibleWindows -lt 1 -or $forced -or $process.ExitCode -ne 0) {
        throw "Packaged application launch or normal-close smoke failed."
    }
}
finally {
    if ($null -ne $process -and -not $process.HasExited) {
        $process.Kill()
        $process.WaitForExit()
    }
    $resolvedRoot = [IO.Path]::GetFullPath($temporaryRoot)
    $safeName = (Split-Path -Leaf $resolvedRoot).StartsWith("anirec-package-smoke-")
    if ($safeName -and $resolvedRoot.StartsWith($temporaryBase, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
    }
}
