# Register a Windows Scheduled Task to run the daily scraper.
# Run PowerShell as Administrator for best results (optional for -User $env:USERNAME).

param(
    [string]$Time = "07:00",
    [string]$TaskName = "GC-Used-Gear-Scraper"
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$DailyScript = Join-Path $ScriptDir "run-daily.ps1"

if (-not (Test-Path $DailyScript)) {
    throw "Missing run-daily.ps1 at $DailyScript"
}

$ProjectRoot = Split-Path -Parent $ScriptDir
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Warning "No .venv found. Run: cd $ProjectRoot; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$DailyScript`"" `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger -Daily -At $Time

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Updating existing task: $TaskName"
    Set-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal | Out-Null
} else {
    Write-Host "Creating scheduled task: $TaskName"
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Scrape new Guitar Center used gear listings daily." | Out-Null
}

Write-Host ""
Write-Host "Scheduled task '$TaskName' will run daily at $Time"
Write-Host "Script: $DailyScript"
Write-Host ""
Write-Host "Test now:  powershell -File `"$DailyScript`""
Write-Host "Remove:    Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
