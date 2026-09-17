param(
    [switch]$Demo
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "尚未安装环境，请先运行 scripts\setup.ps1。"
}

Set-Location -LiteralPath $projectRoot
if ($Demo) {
    & $venvPython -m yys_helper --demo
} else {
    & $venvPython -m yys_helper
}
