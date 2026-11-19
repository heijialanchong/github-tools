param(
    [switch]$AllowOnline
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$environmentFilesRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $environmentFilesRoot
$requirementsPath = Join-Path $environmentFilesRoot "requirements.txt"
$wheelhousePath = Join-Path $environmentFilesRoot "wheels"

Set-Location -LiteralPath $projectRoot

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed (exit code: $LASTEXITCODE)"
    }
}

if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    throw "requirements.txt is missing"
}

if (-not (Test-Path -LiteralPath $wheelhousePath -PathType Container)) {
    throw "The wheels directory is missing"
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    throw "Python was not found. Open Anaconda Prompt and activate an environment first."
}

if (-not [string]::IsNullOrWhiteSpace($env:CONDA_PREFIX)) {
    Write-Host "Active Conda environment: $env:CONDA_PREFIX"
}
else {
    Write-Warning "No active Conda environment was detected; pip will use the current Python."
}

$versionText = & $pythonCommand.Source -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to run Python: $($pythonCommand.Source)"
}

$version = [version]$versionText.Trim()
if ($version -lt [version]"3.8.0") {
    throw "Python $version is too old; Python 3.8 or later is required"
}
Write-Host "Python ${version}: $($pythonCommand.Source)"

$pipArguments = @("-m", "pip", "install", "--disable-pip-version-check")
$dependencyLines = @(
    Get-Content -LiteralPath $requirementsPath |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -ne "" -and -not $_.StartsWith("#") }
)

if ($dependencyLines.Count -eq 0) {
    Write-Step "No third-party pip dependencies are required"
}
else {
    if (-not $AllowOnline) {
        $pipArguments += @("--no-index", "--find-links", $wheelhousePath)
    }
    $pipArguments += @("--requirement", $requirementsPath)

    Write-Step "Install Python dependencies"
    Invoke-Checked `
        -Executable $pythonCommand.Source `
        -Arguments $pipArguments `
        -Description "pip dependency installation"
}

Write-Step "Verify Python standard-library imports"
Invoke-Checked `
    -Executable $pythonCommand.Source `
    -Arguments @("-c", "import argparse, datetime, json, os, re, shutil, subprocess, sys, urllib.request; print('Python imports: OK')") `
    -Description "Python import check"

Write-Step "Check Git"
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if ($null -eq $gitCommand) {
    Write-Warning "Git was not found. Install Git before running the GitHub scripts."
}
else {
    Invoke-Checked `
        -Executable $gitCommand.Source `
        -Arguments @("--version") `
        -Description "Git check"
}

Write-Host ""
Write-Host "Conda/pip environment setup completed." -ForegroundColor Green
Write-Host "The project has no third-party Python packages at present."
exit 0
