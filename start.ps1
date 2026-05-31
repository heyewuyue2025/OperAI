# OperAI 决赛 Demo — 一键启动品牌首页 (8080) + 工作台 (8501)
# 用法：在 operai-mvp 目录执行  .\start.ps1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "未找到 python，请先安装 Python 并加入 PATH。" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "OperAI 启动中…" -ForegroundColor Cyan
Write-Host "  工作目录: $Root"
Write-Host ""

# 品牌首页 :8080
Start-Process -FilePath "python" -ArgumentList "serve.py" -WorkingDirectory $Root

Start-Sleep -Seconds 1

# Streamlit 工作台 :8501
Start-Process -FilePath "python" -ArgumentList @("-m", "streamlit", "run", "app.py", "--server.headless", "true") -WorkingDirectory $Root

Write-Host "  品牌首页   http://127.0.0.1:8080" -ForegroundColor Green
Write-Host "  决赛工作台 http://127.0.0.1:8501" -ForegroundColor Green
Write-Host ""
Write-Host "提示：关闭弹出的两个终端窗口即可停止对应服务。" -ForegroundColor Yellow
Write-Host "若 Streamlit 报 starlette/gzip 错误，请执行：" -ForegroundColor DarkGray
Write-Host '  pip install "streamlit>=1.32,<1.40" "starlette>=0.37"' -ForegroundColor DarkGray
Write-Host ""
