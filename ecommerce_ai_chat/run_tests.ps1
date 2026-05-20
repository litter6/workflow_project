# =============================================================
#  Ecommerce AI Tool - Full Integration Test Runner
#  Usage: cd d:\workflow_project && .\ecommerce_ai_chat\run_tests.ps1
# =============================================================

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND    = Join-Path $SCRIPT_DIR "backend"
$FRONTEND   = Join-Path $SCRIPT_DIR "frontend"

$results = @()   # PSCustomObject list: Name, Passed, Detail

function Write-Sep  { Write-Host ("=" * 54) -ForegroundColor Cyan }
function Write-Step($n, $total, $text) {
    Write-Host ""
    Write-Host "[$n/$total] $text" -ForegroundColor Cyan
    Write-Host ("-" * 46) -ForegroundColor DarkGray
}
function Write-Ok($msg)   { Write-Host "  [PASS] $msg" -ForegroundColor Green  }
function Write-Err($msg)  { Write-Host "  [FAIL] $msg" -ForegroundColor Red    }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Info($msg) { Write-Host "  [ -- ] $msg" -ForegroundColor DarkGray }

function Add-Result {
    param($name, $passed, $detail = "")
    $script:results += [PSCustomObject]@{ Name=$name; Passed=$passed; Detail=$detail }
}

# -----------------------------------------------------------------
Write-Sep
Write-Host "  Ecommerce AI Tool - Integration Test Suite" -ForegroundColor Cyan
Write-Sep

# =============================================================
# Step 1 - Install test dependencies
# =============================================================
Write-Step 1 3 "Install test deps (pytest + httpx)"

try {
    Write-Info "pip install pytest httpx ..."
    $null = & python -m pip install pytest httpx --quiet 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Test dependencies ready"
    } else {
        Write-Warn "pip returned non-zero. Continuing anyway..."
    }
} catch {
    Write-Warn "pip error: $($_.Exception.Message)"
}

# =============================================================
# Step 2 - Backend API tests (pytest)
# =============================================================
Write-Step 2 3 "Backend API tests (pytest)"

try {
    Push-Location $BACKEND
    Write-Info "Running pytest test_api.py ..."
    Write-Host ""

    & python -m pytest test_api.py -v --tb=short --no-header 2>&1 | Tee-Object -Variable pytestOut
    $pytestExit = $LASTEXITCODE

    Write-Host ""

    $summary    = $pytestOut | Where-Object { $_ -match "\d+ passed" } | Select-Object -Last 1
    $failedList = $pytestOut | Where-Object { $_ -match "^FAILED" }

    if ($pytestExit -eq 0) {
        Write-Ok "All tests passed.  $summary"
        Add-Result "Backend API tests" $true $summary
    } else {
        Write-Err "Tests failed.  $summary"
        $failedList | ForEach-Object { Write-Err "  -> $_" }
        Add-Result "Backend API tests" $false $summary

        Write-Host ""
        Write-Host "  How to fix:" -ForegroundColor White
        Write-Host "  1. Find the FAILED test name in the output above" -ForegroundColor White
        Write-Host "  2. Open backend/test_api.py, locate that test method" -ForegroundColor White
        Write-Host "  3. Open backend/main.py, find the matching route" -ForegroundColor White
        Write-Host "  4. Fix the bug, then re-run this script" -ForegroundColor White
    }
} catch {
    Write-Err "pytest execution error: $($_.Exception.Message)"
    Add-Result "Backend API tests" $false $_.Exception.Message
} finally {
    Pop-Location -ErrorAction SilentlyContinue
}

# =============================================================
# Step 3 - Frontend build check
# =============================================================
Write-Step 3 3 "Frontend build check (npm run build)"

try {
    Push-Location $FRONTEND

    if (-not (Test-Path "node_modules")) {
        Write-Info "First run - installing npm packages..."
        $null = & npm install --silent 2>&1
    }

    Write-Info "Running npm run build ..."
    Write-Host ""

    $buildOut  = & npm run build 2>&1
    $buildExit = $LASTEXITCODE

    Write-Host ""

    if ($buildExit -eq 0) {
        $distSize = ""
        if (Test-Path "dist") {
            $bytes    = (Get-ChildItem dist -Recurse -File | Measure-Object -Property Length -Sum).Sum
            $distSize = "$([math]::Round($bytes / 1KB)) KB total"
        }
        Write-Ok "Build succeeded.  $distSize"
        Add-Result "Frontend build" $true "No compile errors"
    } else {
        Write-Err "Build failed."
        $errLines = $buildOut | Where-Object { $_ -match "[Ee]rror" } | Select-Object -First 8
        $errLines | ForEach-Object { Write-Err "  -> $_" }
        Add-Result "Frontend build" $false ($errLines -join " | ")

        Write-Host ""
        Write-Host "  How to fix:" -ForegroundColor White
        Write-Host "  1. Find 'error' lines above - they include file path + line number" -ForegroundColor White
        Write-Host "  2. Common causes: JSX syntax, bad import path, missing CSS variable" -ForegroundColor White
        Write-Host "  3. Fix then re-run this script" -ForegroundColor White
    }
} catch {
    Write-Err "npm build error: $($_.Exception.Message)"
    Add-Result "Frontend build" $false $_.Exception.Message
} finally {
    Pop-Location -ErrorAction SilentlyContinue
}

# =============================================================
# Summary
# =============================================================
$totalPass = ($results | Where-Object { $_.Passed }).Count
$totalFail = ($results | Where-Object { -not $_.Passed }).Count
$allPassed = ($totalFail -eq 0)

Write-Host ""
Write-Sep

$summaryColor = if ($allPassed) { "Green" } else { "Red" }
Write-Host "  Test Results: $totalPass / $($results.Count) modules passed" -ForegroundColor $summaryColor
Write-Host ""

foreach ($r in $results) {
    $tag   = if ($r.Passed) { "[PASS]" } else { "[FAIL]" }
    $color = if ($r.Passed) { "Green"  } else { "Red"   }
    Write-Host ("  {0,-8}  {1,-26} {2}" -f $tag, $r.Name, $r.Detail) -ForegroundColor $color
}

Write-Sep

if ($allPassed) {
    Write-Host ""
    Write-Host "  All tests passed. No existing features broken." -ForegroundColor Green
    exit 0
} else {
    Write-Host ""
    Write-Host "  [!] $totalFail module(s) failed. Fix issues above then re-run." -ForegroundColor Red
    exit 1
}
