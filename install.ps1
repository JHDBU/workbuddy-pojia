#requires -version 5.1
<#
  workbuddy-pojia 一键安装
  用法：
    .\install.ps1              # 体检 + 演练
    .\install.ps1 -Apply       # 体检 + 正式写入 + 重启 WorkBuddy
    .\install.ps1 -Apply -Gate # 同时开启 L3 命令闸门
    .\install.ps1 -Off         # 关闭 L3 闸门并重启
#>
param(
    [switch]$Apply,
    [switch]$Gate,
    [switch]$Off,
    [string]$InstallDir = "",
    [string]$DataDir = ""
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root 'scripts\pojia.py'
if (-not (Test-Path $py)) { throw "找不到 scripts\pojia.py，请在仓库根目录运行" }

$common = @()
if ($InstallDir) { $common += @('-i', $InstallDir) }
if ($DataDir)    { $common += @('-d', $DataDir) }

Write-Host "== 环境体检 ==" -ForegroundColor Cyan
python $py doctor @common
if ($LASTEXITCODE -ne 0) { throw "doctor 失败，检查路径（可加 -InstallDir / -DataDir）" }

Write-Host "`n== 演练 ==" -ForegroundColor Cyan
python $py apply --dry-run @common

if (-not $Apply -and -not $Off) {
    Write-Host "`n演练完成。确认无误后执行： .\install.ps1 -Apply" -ForegroundColor Yellow
    return
}

if ($Off) {
    Write-Host "`n== 关闭 L3 闸门 ==" -ForegroundColor Cyan
    python $py gate off @common
    python $py gate off @common --restart
    return
}

Write-Host "`n== 写入并重启 ==" -ForegroundColor Cyan
if ($Gate) {
    python $py restart --gate @common
} else {
    python $py restart @common
}

Write-Host "`n== 结果 ==" -ForegroundColor Cyan
python $py status @common
Write-Host "`n验收：新会话发「破甲自检」应回「破甲未开启」；发「开启破甲」后再自检应回「破甲自检成功」。" -ForegroundColor Green
