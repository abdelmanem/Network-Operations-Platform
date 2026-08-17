# Simplified Windows Inspection Script for TLS Certificate Architecture
# PowerShell only - no mixed Python syntax

Write-Host "======================================================================" -ForegroundColor Green
Write-Host "M30.x — NetBox TLS Certificate Architecture INSPECTION" -ForegroundColor Green
Write-Host "Windows Network Operations Platform - Inspection Only" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportFile = "inspection_report_windows_$timestamp.txt"

# Simple logging function
function Log-Finding {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
    Add-Content -Path $reportFile -Value $Message
}

# Initialize report
"=============================================================================" | Add-Content -Path $reportFile
"M30.x — NetBox TLS Certificate Architecture INSPECTION" | Add-Content -Path $reportFile
"Date: $(Get-Date)" | Add-Content -Path $reportFile
"=============================================================================" | Add-Content -Path $reportFile
""| Add-Content -Path $reportFile

Log-Finding ""
Log-Finding "=== PART A: Active Directory Certificate Services ===" "Cyan"

Log-Finding ""
Log-Finding "[A.1] Checking AD CS Installation Status..." "Yellow"
try {
    $adcs = Get-WindowsFeature -Name AD-Certificate -ErrorAction Stop
    Log-Finding "  Result: $($adcs.InstallState)"
    if ($adcs.InstallState -eq "Installed") {
        Log-Finding "  ✅ AD CS IS INSTALLED" "Green"
    } else {
        Log-Finding "  ℹ️  AD CS not installed" "Gray"
    }
} catch {
    Log-Finding "  ⚠️  Could not check: $($_.Exception.Message)" "Yellow"
}

Log-Finding ""
Log-Finding "[A.2] Checking for AD Certification Authorities..." "Yellow"
try {
    $rootDSE = [ADSI]"LDAP://RootDSE"
    $configPath = $rootDSE.configurationNamingContext
    $caPath = "LDAP://CN=Certification Authorities,CN=Public Key Services,CN=Services,$configPath"
    $searcher = New-Object System.DirectoryServices.DirectorySearcher
    $searcher.SearchRoot = [ADSI]$caPath
    $searcher.Filter = "(objectClass=pKIEnrollmentService)"
    $cas = $searcher.FindAll()

    if ($cas.Count -gt 0) {
        Log-Finding "  ✅ Found $($cas.Count) Certification Authority(ies):" "Green"
        foreach ($ca in $cas) {
            $caName = $ca.Properties.cn[0]
            Log-Finding "    - $caName" "Cyan"
        }
    } else {
        Log-Finding "  ℹ️  No AD CAs found" "Gray"
    }
} catch {
    Log-Finding "  ⚠️  Could not query AD: $($_.Exception.Message)" "Yellow"
}

Log-Finding ""
Log-Finding "=== PART B: Trusted Root CAs on This Machine ===" "Cyan"

Log-Finding ""
Log-Finding "[B.1] Local Machine Root CAs (Cert:\LocalMachine\Root)..." "Yellow"
try {
    $rootCAs = Get-ChildItem -Path Cert:\LocalMachine\Root\ -ErrorAction SilentlyContinue
    Log-Finding "  Total root certificates: $($rootCAs.Count)"
    
    # Show potential internal CAs
    $internalCAs = @()
    foreach ($ca in $rootCAs) {
        if ($ca.Subject -match "internal|corp|root|self|local|caizh") {
            $internalCAs += $ca
        }
    }
    
    if ($internalCAs.Count -gt 0) {
        Log-Finding "  💡 Found $($internalCAs.Count) potential internal/self-signed CA(s):" "Cyan"
        foreach ($ca in $internalCAs) {
            Log-Finding "    Subject: $($ca.Subject)"
            Log-Finding "    Issuer:  $($ca.Issuer)"
            Log-Finding "    Valid until: $($ca.NotAfter)"
            Log-Finding ""
        }
    } else {
        Log-Finding "  ℹ️  No obvious internal CAs found" "Gray"
    }
} catch {
    Log-Finding "  ⚠️  Error reading root store: $($_.Exception.Message)" "Yellow"
}

Log-Finding ""
Log-Finding "[B.2] All Certificate Stores Summary..." "Yellow"

$stores = @('LocalMachine\Root', 'LocalMachine\CA', 'LocalMachine\My', 'CurrentUser\Root', 'CurrentUser\CA')
foreach ($store in $stores) {
    $path = "Cert:\$store"
    try {
        $certs = Get-ChildItem -Path $path -ErrorAction SilentlyContinue
        $count = if ($certs -is [array]) { $certs.Count } else { if ($certs) { 1 } else { 0 } }
        Log-Finding "  [$store]: $count certificate(s)"
    } catch {
        Log-Finding "  [$store]: (error reading)"
    }
}

Log-Finding ""
Log-Finding "=== PART C: Testing HTTPS Connection to NetBox ===" "Cyan"

Log-Finding ""
Log-Finding "[C.1] PowerShell Invoke-WebRequest Test..." "Yellow"

$token = "nbt_SBTm9Eg6H3oz.OHmdynS8XL0crmpj3Fj7ZkE8dIGdTtEKRqAJPNZv"
$headers = @{"Authorization" = "Bearer $token"}

try {
    Log-Finding "  Testing: GET https://caizh.netbox.com/api/status/"
    $response = Invoke-WebRequest `
        -Uri "https://caizh.netbox.com/api/status/" `
        -Headers $headers `
        -UseBasicParsing `
        -ErrorAction Stop
    
    Log-Finding "  ✅ TLS VERIFICATION PASSED - HTTP $($response.StatusCode)" "Green"
    Log-Finding "  Content preview: $($response.Content.Substring(0, [Math]::Min(100, $response.Content.Length)))"
} catch [System.Net.Http.HttpRequestException] {
    Log-Finding "  ❌ HTTPS Connection Failed" "Red"
    Log-Finding "  Error: $($_.Exception.Message)" "Red"
    if ($_.Exception.Message -match "certificate|trust|verify|SSL") {
        Log-Finding "  → TLS Certificate Issue (not trusted by Windows)" "Red"
    }
} catch {
    Log-Finding "  ❌ Error: $($_.Exception.GetType().Name)" "Red"
    Log-Finding "  Message: $($_.Exception.Message)" "Red"
}

Log-Finding ""
Log-Finding "=== PART D: Python httpx TLS Verification ===" "Cyan"

Log-Finding ""
Log-Finding "[D.1] Checking Python TLS with socket/ssl..." "Yellow"

# Create a temporary Python script file to avoid PowerShell parsing issues
$pythonScriptPath = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.py'
$pythonCode = @"
import ssl, socket
hostname = 'caizh.netbox.com'
port = 443
try:
    ctx = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            print("[SUCCESS] TLS verification passed")
except ssl.SSLError as e:
    print(f"[FAIL] SSL Error: {e}")
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
"@

try {
    Set-Content -Path $pythonScriptPath -Value $pythonCode
    $result = .\.venv\Scripts\python.exe $pythonScriptPath 2>&1
    Log-Finding "  Python result: $result" "Cyan"
    Remove-Item -Path $pythonScriptPath -ErrorAction SilentlyContinue
} catch {
    Log-Finding "  ⚠️  Could not run Python test: $($_.Exception.Message)" "Yellow"
    Remove-Item -Path $pythonScriptPath -ErrorAction SilentlyContinue
}

Log-Finding ""
Log-Finding "=== PART E: System Information ===" "Cyan"

Log-Finding ""
Log-Finding "[E.1] Computer and Domain Information..." "Yellow"

try {
    $computerName = [System.Net.Dns]::GetHostName()
    Log-Finding "  Computer Name: $computerName"
    
    $domain = (Get-ADDomain -Current LocalComputer -ErrorAction SilentlyContinue).Name
    if ($domain) {
        Log-Finding "  Domain: $domain"
    } else {
        Log-Finding "  Domain: (not accessible)"
    }
    
    Log-Finding "  OS: Windows"
    
} catch {
    Log-Finding "  ⚠️  Could not get system info: $($_.Exception.Message)" "Yellow"
}

Log-Finding ""
Log-Finding "=== INSPECTION COMPLETE ===" "Green"
Log-Finding ""
Log-Finding "Report saved to: $reportFile" "Green"

Write-Host ""
Write-Host "=== Next Steps ===" -ForegroundColor Cyan
Write-Host "1. SSH to NetBox: ssh root@caizh.netbox.com" -ForegroundColor Yellow
Write-Host "2. Run Part B commands from: INSPECTION-PLAN-M30.x-TLS-CERTIFICATE.md" -ForegroundColor Yellow
Write-Host "3. Return all findings for analysis" -ForegroundColor Yellow
Write-Host ""
Write-Host "Report file: $reportFile" -ForegroundColor Green
