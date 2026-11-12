# 喊话小喇叭 - 大屏端启动脚本
# 用法：右键点击此文件 → "使用 PowerShell 运行"

Write-Host "正在启动大屏端..." -ForegroundColor Green
Write-Host "请确保后端和教师端已启动" -ForegroundColor Yellow
Write-Host ""

# 进入大屏端目录
Set-Location $PSScriptRoot

# 启动 Vite + Electron
npm run dev

# 如果出错，暂停显示
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "启动失败！请检查错误信息" -ForegroundColor Red
    Write-Host "按任意键退出..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
