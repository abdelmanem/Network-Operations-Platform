# Simple Windows Inspection for TLS Certificate Architecture
# No embedded Python - calls external Python file instead

Write-Host "======================================================================" -ForegroundColor Green
Write-Host "M30.x - NetBox TLS Certificate INSPECTION (Windows)" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportFile = "inspection_$timestamp.txt"

Write-Host "[INSPECTION] AD Certificate Services..." -ForegroundColor Yellow
Get-WindowsFeature -Name AD-Certificate 2>$null | Select-Object Name, InstallState | Tee-Object -FilePath $reportFile -Append

Write-Host ""
Write-Host "[INSPECTION] Trusted Root CAs on This Machine..." -ForegroundColor Yellow
$rootCerts = Get-ChildItem -Path Cert:\LocalMachine\Root\ 2>$null
Write-Host "  Total: $($rootCerts.Count)"

# Look for internal CAs
$internalCAs = @()
foreach ($cert in $rootCerts) {
    if ($cert.Subject -match "internal|corp|root|self|local|caizh" -or $cert.Subject -eq $cert.Issuer) {
        $internalCAs += $cert
    }
}

if ($internalCAs.Count -gt 0) {
    Write-Host "  [INTERNAL CAs] Found $($internalCAs.Count) internal/self-signed CA(s):" -ForegroundColor Cyan
    $internalCAs | ForEach-Object {
        Write-Host "    Subject: $($_.Subject)"
        Write-Host "    Valid until: $($_.NotAfter)"
    }
} else {
    Write-Host "  [INFO] No internal CAs found"
}

Write-Host ""
Write-Host "[INSPECTION] Testing HTTPS to NetBox..." -ForegroundColor Yellow

$token = "nbt_SBTm9Eg6H3oz.OHmdynS8XL0crmpj3Fj7ZkE8dIGdTtEKRqAJPNZv"
$headers = @{"Authorization" = "Bearer $token"}

try {
    $response = Invoke-WebRequest `
        -Uri "https://caizh.netbox.com/api/status/" `
        -Headers $headers `
        -UseBasicParsing `
        -ErrorAction Stop
    
    Write-Host "  [SUCCESS] TLS PASSED - HTTP $($response.StatusCode)" -ForegroundColor Green
} catch {
    if ($_.Exception.Message -match "certificate|trust|verify|SSL") {
        Write-Host "  [FAIL] TLS Certificate Issue - Windows cannot verify" -ForegroundColor Red
    } else {
        Write-Host "  [ERROR] $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "[INSPECTION] Python TLS Verification..." -ForegroundColor Yellow
$pythonResult = .\.venv\Scripts\python.exe test_netbox_tls.py 2>&1
Write-Host "  $pythonResult"

Write-Host ""
Write-Host "=== INSPECTION COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next: Run Part B commands from INSPECTION-PLAN file on NetBox host" -ForegroundColor Cyan
