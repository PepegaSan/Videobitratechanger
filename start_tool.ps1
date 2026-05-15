param()

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "mass_bitrate_gui.py"

function Require-Tool {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name wurde nicht gefunden. Bitte installieren und in PATH aufnehmen."
    }
}

try {
    Require-Tool -Name "python"
    Require-Tool -Name "ffmpeg"
    Require-Tool -Name "ffprobe"

    & python $pyScript
    if ($LASTEXITCODE -ne 0) {
        throw "Python-Skript beendet mit ExitCode $LASTEXITCODE"
    }
}
catch {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Enter zum Schliessen"
    exit 1
}
