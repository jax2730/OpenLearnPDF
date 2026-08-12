[CmdletBinding()]
param(
    [string]$WorkspaceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$DataRoot = 'I:\pdf_reaserch\data'
)

$ErrorActionPreference = 'Stop'
$workspace = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$python = Join-Path $workspace 'backend\.venv\Scripts\python.exe'
$questions = Join-Path $workspace 'evaluation\chapter-05\questions.json'
$rubric = Join-Path $workspace 'evaluation\chapter-05\rubric.json'
$report = Join-Path $workspace 'evaluation\chapter-05\report.md'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Backend Python not found: $python"
}

& $python -m rtr4_learning.chapter_evaluation `
    --data-root ([System.IO.Path]::GetFullPath($DataRoot)) `
    --book-id rtr4-cn `
    --questions $questions `
    --rubric $rubric `
    --report $report

if ($LASTEXITCODE -ne 0) {
    throw "Chapter evaluation failed. See $report"
}
