param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[1/4] 创建 Python 虚拟环境..." -ForegroundColor Cyan
    & $Python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "无法创建虚拟环境。请安装 Python 3.11 或 3.12，并用 -Python 指定 python.exe。"
    }
}

Write-Host "[2/4] 更新安装工具..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "pip 更新失败。" }

Write-Host "[3/4] 安装御魂匠桌面依赖..." -ForegroundColor Cyan
& $venvPython -m pip install -e ".[desktop]"
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败。" }

Write-Host "[4/4] 准备中文 OCR 模型（首次约 30 MB）..." -ForegroundColor Cyan
& $venvPython -c "from yys_helper.infrastructure.vision import RapidOcrEngine; RapidOcrEngine()._load(); print('OCR ready')"
if ($LASTEXITCODE -ne 0) { throw "OCR 模型初始化失败。请检查网络后重新运行安装脚本。" }

Write-Host "安装完成。运行 scripts\start.ps1 -Demo 先体验演示模式。" -ForegroundColor Green
