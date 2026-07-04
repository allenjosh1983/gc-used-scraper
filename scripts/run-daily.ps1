# Daily scrape: new used SKUs since last 36h, dedupe via known-skus, plus deals + presets.
# Run manually or via install-scheduled-task.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$Stamp = Get-Date -Format "yyyy-MM-dd"
$OutDir = Join-Path $Root "output\daily\$Stamp"
$LogDir = Join-Path $Root "output\logs"
New-Item -ItemType Directory -Force -Path $OutDir, $LogDir | Out-Null

$LogFile = Join-Path $LogDir "run-$Stamp.log"
function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

Log "=== GC used scraper daily run ==="

# 36h window covers UTC morning drop regardless of local timezone / DST
$SinceHours = 36

# 1) All new listings (deduped)
$KnownSkus = Join-Path $Root "data\seen_skus.txt"
$AllJson = Join-Path $OutDir "new-all.json"
Log "Fetching all new used (last ${SinceHours}h)..."
& $Python (Join-Path $Root "scraper.py") `
    --since-hours $SinceHours `
    --known-skus $KnownSkus `
    --update-known `
    -o $AllJson
if ($LASTEXITCODE -ne 0) { Log "ERROR: scraper failed"; exit $LASTEXITCODE }
Log "Wrote $AllJson"

# 2) All used price drops on the site (not limited to new SKUs)
$DealsJson = Join-Path $OutDir "used-price-drops.json"
Log "Fetching all used price drops..."
& $Python (Join-Path $Root "scraper.py") `
    --since-hours 1 `
    --all-ages `
    --price-drop `
    -o $DealsJson
if ($LASTEXITCODE -ne 0) { Log "ERROR: price-drop scrape failed"; exit $LASTEXITCODE }
Log "Wrote $DealsJson"

# 2b) New listings with any discount
$NewDealsJson = Join-Path $OutDir "new-on-sale.json"
Log "Fetching discounted new listings..."
& $Python (Join-Path $Root "scraper.py") `
    --since-hours $SinceHours `
    --on-sale `
    -o $NewDealsJson
if ($LASTEXITCODE -ne 0) { Log "ERROR: new on-sale scrape failed"; exit $LASTEXITCODE }
Log "Wrote $NewDealsJson"

# 3) Per-category preset exports
$PresetDir = Join-Path $OutDir "by-category"
Log "Running category presets..."
& $Python (Join-Path $Root "run_presets.py") `
    --since-hours $SinceHours `
    --output-dir $PresetDir `
    --format csv
if ($LASTEXITCODE -ne 0) { Log "ERROR: presets failed"; exit $LASTEXITCODE }

Log "=== Done. Output: $OutDir ==="
