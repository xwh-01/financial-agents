$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Starting Market Impact Agent..." -ForegroundColor Green

uvicorn app.main:app --reload --port 8001