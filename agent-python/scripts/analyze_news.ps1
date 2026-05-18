$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$title = Read-Host "请输入新闻标题"
$content = Read-Host "请输入新闻正文"
$source = Read-Host "请输入来源，例如 news"
$publishedAt = Read-Host "请输入发布时间，例如 2026-05-15T10:00:00Z"

if ([string]::IsNullOrWhiteSpace($source)) {
    $source = "news"
}

if ([string]::IsNullOrWhiteSpace($publishedAt)) {
    $publishedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$body = @{
    title = $title
    content = $content
    source = $source
    published_at = $publishedAt
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod `
  -Uri "http://localhost:8001/agent/analyze" `
  -Method POST `
  -ContentType "application/json; charset=utf-8" `
  -Body $body

Write-Host "`n===== 分析结果 =====" -ForegroundColor Cyan
$response | ConvertTo-Json -Depth 30

Write-Host "`n===== 中文报告 =====" -ForegroundColor Green
$response.report

$response.report | Out-File ".\last_report.txt" -Encoding utf8
Write-Host "`n报告已保存到 agent-python/last_report.txt" -ForegroundColor Yellow