param([string]$ShortcutDirectory = [Environment]::GetFolderPath('Desktop'))

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$iconSource = Join-Path $projectRoot 'src\yys_helper\assets\app-icon.ico'
$iconHash = (Get-FileHash -LiteralPath $iconSource -Algorithm SHA256).Hash.Substring(0, 12)
$iconCache = Join-Path $projectRoot 'data\icons'
New-Item -ItemType Directory -Path $iconCache -Force | Out-Null
$cachedIcon = Join-Path $iconCache "app-icon-$iconHash.ico"
if (-not (Test-Path -LiteralPath $cachedIcon)) {
    Copy-Item -LiteralPath $iconSource -Destination $cachedIcon
}
$shortcutPath = Join-Path (Resolve-Path -LiteralPath $ShortcutDirectory).Path '御魂匠.lnk'
$expectedTarget = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut($shortcutPath)
if (Test-Path -LiteralPath $shortcutPath) {
    if ($shortcut.TargetPath -ne $expectedTarget) {
        throw "该快捷方式不指向当前项目，未修改：$shortcutPath"
    }
} else {
    $shortcut.TargetPath = $expectedTarget
    $shortcut.Arguments = '-m yys_helper'
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = '御魂匠 · 本地御魂规划与任务助手'
}
# A content-addressed icon filename refreshes Explorer's icon cache without clearing it.
$shortcut.IconLocation = "$cachedIcon,0"
$shortcut.Save()
$verified = $shellObject.CreateShortcut($shortcutPath)
[pscustomobject]@{ Path=$shortcutPath; Target=$verified.TargetPath; Arguments=$verified.Arguments; Icon=$verified.IconLocation } | ConvertTo-Json
