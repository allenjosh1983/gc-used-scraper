# Show how often the local daily scraper has run.
# Usage: powershell -File scripts\run-status.ps1

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "output\logs"
$DailyDir = Join-Path $Root "output\daily"

Write-Host "GC Used Scraper — run status" -ForegroundColor Cyan
Write-Host "Project: $Root"
Write-Host ""

$task = Get-ScheduledTask -TaskName "GC-Used-Gear-Scraper" -ErrorAction SilentlyContinue
if ($task) {
    $info = Get-ScheduledTaskInfo -TaskName "GC-Used-Gear-Scraper"
    Write-Host "Scheduled task: $($task.State)"
    Write-Host "  Last run: $($info.LastRunTime)"
    Write-Host "  Last result: $($info.LastTaskResult) (0 = success)"
    Write-Host "  Next run: $($info.NextRunTime)"
} else {
    Write-Host "Scheduled task: not installed"
}
Write-Host ""

if (-not (Test-Path $LogDir)) {
    Write-Host "No logs yet. Run scripts\run-daily.ps1 first."
    exit 0
}

$logs = Get-ChildItem $LogDir -Filter "run-*.log" | Sort-Object Name
$runs = foreach ($log in $logs) {
    $text = Get-Content $log.FullName -Raw -ErrorAction SilentlyContinue
    $completed = $text -match "=== Done\."
    [PSCustomObject]@{
        Date      = $log.BaseName -replace "^run-", ""
        RanAt     = $log.LastWriteTime
        Status    = if ($completed) { "Completed" } else { "Incomplete" }
    }
}

$dataDays = if (Test-Path $DailyDir) {
    (Get-ChildItem $DailyDir -Directory).Count
} else { 0 }

$completed = @($runs | Where-Object Status -eq "Completed").Count
Write-Host "Run days (logs): $($runs.Count)"
Write-Host "Completed runs:  $completed"
Write-Host "Data days:       $dataDays"
Write-Host ""
$runs | Format-Table -AutoSize
