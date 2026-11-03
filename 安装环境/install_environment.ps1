param(
    [ValidateSet("auto", "conda", "venv")]
    [string]$Mode = "auto"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$environmentFilesRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $environmentFilesRoot
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

function Test-PythonVersion {
    param([Parameter(Mandatory = $true)][string]$PythonExecutable)

    $versionText = & $PythonExecutable -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to run Python: $PythonExecutable"
    }

    $version = [version]$versionText.Trim()
    if ($version -lt [version]"3.8.0") {
        throw "Python $version is too old; Python 3.8 or later is required"
    }

    Write-Host "Python ${version}: $PythonExecutable"
    return $version
}

$requirementsPath = Join-Path $environmentFilesRoot "requirements.txt"
$environmentPath = Join-Path $environmentFilesRoot "environment.yml"

if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    throw "requirements.txt is missing"
}

$condaCommand = Get-Command conda -ErrorAction SilentlyContinue
$useConda = $Mode -eq "conda" -or ($Mode -eq "auto" -and $null -ne $condaCommand)

try {
    if ($useConda -and $null -eq $condaCommand) {
        throw "Conda was not found. Install Miniconda or run install_environment.ps1 -Mode venv"
    }

    if ($useConda) {
        if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
            throw "environment.yml is missing"
        }

        Write-Step "Create or update the Conda environment: github-tools"
        Invoke-Checked `
            -Executable $condaCommand.Source `
            -Arguments @("env", "update", "--name", "github-tools", "--file", $environmentPath) `
            -Description "Conda environment installation"

        Write-Step "Install Python dependencies from requirements.txt"
        Invoke-Checked `
            -Executable $condaCommand.Source `
            -Arguments @("run", "--name", "github-tools", "python", "-m", "pip", "install", "--disable-pip-version-check", "--requirement", $requirementsPath) `
            -Description "Python dependency installation"

        $targetPython = $condaCommand.Source
        $pythonArguments = @("run", "--name", "github-tools", "python")
        $pythonLabel = "conda run --name github-tools python"

        Write-Step "Check Git"
        Invoke-Checked `
            -Executable $condaCommand.Source `
            -Arguments @("run", "--name", "github-tools", "git", "--version") `
            -Description "Git check"
    }
    else {
        $systemPython = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $systemPython) {
            throw "Python and Conda were not found. Install Python 3.8+ and Git, or install Miniconda, then retry."
        }

        Write-Step "Check system Python"
        [void](Test-PythonVersion -PythonExecutable $systemPython.Source)

        $venvPath = Join-Path $projectRoot ".venv"
        $venvPython = Join-Path $venvPath "Scripts\python.exe"

        if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
            Write-Step "Create the project virtual environment: .venv"
            Invoke-Checked `
                -Executable $systemPython.Source `
                -Arguments @("-m", "venv", $venvPath) `
                -Description "Virtual environment creation"
        }
        else {
            Write-Step "Reuse the existing virtual environment: .venv"
        }

        [void](Test-PythonVersion -PythonExecutable $venvPython)

        Write-Step "Install Python dependencies from requirements.txt"
        Invoke-Checked `
            -Executable $venvPython `
            -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "--requirement", $requirementsPath) `
            -Description "Python dependency installation"

        $targetPython = $venvPython
        $pythonArguments = @()
        $pythonLabel = ".\.venv\Scripts\python.exe"

        Write-Step "Check Git"
        $gitCommand = Get-Command git -ErrorAction SilentlyContinue
        if ($null -eq $gitCommand) {
            throw "Git was not found. Install Git for Windows: https://git-scm.com/download/win"
        }
        Invoke-Checked `
            -Executable $gitCommand.Source `
            -Arguments @("--version") `
            -Description "Git check"
    }

    Write-Step "Validate project Python syntax"
    $projectPythonFiles = Get-ChildItem -LiteralPath $projectRoot -Filter "*.py" -File
    foreach ($pythonFile in $projectPythonFiles) {
        $compileArguments = @($pythonArguments) + @("-m", "py_compile", $pythonFile.FullName)
        Invoke-Checked `
            -Executable $targetPython `
            -Arguments $compileArguments `
            -Description "Syntax check: $($pythonFile.Name)"
    }

    Write-Host ""
    Write-Host "Environment installation completed." -ForegroundColor Green
    if ($useConda) {
        Write-Host "Activate it with: conda activate github-tools"
    }
    else {
        Write-Host "Activate it with: .\.venv\Scripts\Activate.ps1"
    }
    Write-Host "Python command: $pythonLabel"
    Write-Host "Before the first run, configure projects.json and config.py as described in README.md."
    exit 0
}
catch {
    Write-Host ""
    Write-Host "Installation failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
