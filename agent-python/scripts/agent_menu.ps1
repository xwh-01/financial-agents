$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Show-Menu {
    Write-Host ""
    Write-Host "===============================" -ForegroundColor Cyan
    Write-Host " Market Impact Agent 控制台"
    Write-Host "===============================" -ForegroundColor Cyan
    Write-Host "1. 健康检查"
    Write-Host "2. 手动输入新闻并分析"
    Write-Host "3. 搜索新闻"
    Write-Host "4. 批量搜索并分析 Top N 新闻"
    Write-Host "0. 退出"
    Write-Host ""
}

function Check-Health {
    $response = Invoke-RestMethod -Uri "http://localhost:8001/healthz"
    $response | ConvertTo-Json -Depth 10
}

function Analyze-News {
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

    Write-Host "`n===== 结构化结果 =====" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 30

    Write-Host "`n===== 中文报告 =====" -ForegroundColor Green
    $response.report

    $response.report | Out-File ".\last_report.txt" -Encoding utf8
    Write-Host "`n报告已保存到 last_report.txt" -ForegroundColor Yellow
}

function Search-News {
    $query = Read-Host "请输入搜索关键词，例如 Elon Musk Tesla robotaxi"
    $limit = Read-Host "请输入返回数量，例如 5"

    if ([string]::IsNullOrWhiteSpace($limit)) {
        $limit = 5
    }

    $body = @{
        query = $query
        limit = [int]$limit
        language = "en"
    } | ConvertTo-Json -Depth 10

    $response = Invoke-RestMethod `
      -Uri "http://localhost:8001/agent/search-news" `
      -Method POST `
      -ContentType "application/json; charset=utf-8" `
      -Body $body

    Write-Host "`n===== 新闻列表 =====" -ForegroundColor Cyan
    $response.items | Select-Object index,title,source,published_at,url
}

function Batch-Analyze-News {
    $query = Read-Host "请输入搜索关键词，例如 Elon Musk Tesla robotaxi"
    $limit = Read-Host "请输入批量分析数量，例如 3"

    if ([string]::IsNullOrWhiteSpace($limit)) {
        $limit = 3
    }

    $body = @{
        query = $query
        limit = [int]$limit
        language = "en"
    } | ConvertTo-Json -Depth 10

    $response = Invoke-RestMethod `
      -Uri "http://localhost:8001/agent/batch-analyze-news" `
      -Method POST `
      -ContentType "application/json; charset=utf-8" `
      -Body $body

    Write-Host "`n===== 批量分析摘要 =====" -ForegroundColor Cyan

    $response.results | ForEach-Object {
        [PSCustomObject]@{
            title = $_.news.title
            status = $_.status
            persons = ($_.analysis_result.entity_result.persons -join ",")
            tickers = ($_.analysis_result.ticker_links.direct_tickers -join ",")
            sentiment = $_.analysis_result.event_result.sentiment
            risk = $_.analysis_result.risk_result.risk_level
        }
    } | Format-Table -AutoSize

    $response | ConvertTo-Json -Depth 50 | Out-File ".\last_batch_result.json" -Encoding utf8
    Write-Host "`n完整批量结果已保存到 last_batch_result.json" -ForegroundColor Yellow
}

while ($true) {
    Show-Menu
    $choice = Read-Host "请选择功能"

    switch ($choice) {
        "1" { Check-Health }
        "2" { Analyze-News }
        "3" { Search-News }
        "4" { Batch-Analyze-News }
        "0" {
            Write-Host "退出。" -ForegroundColor Yellow
            break
        }
        default {
            Write-Host "无效选择，请重新输入。" -ForegroundColor Red
        }
    }
}