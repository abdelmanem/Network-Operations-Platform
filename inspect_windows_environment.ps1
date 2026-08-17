# Comprehensive Inspection Script for Windows (Network Operations Platform)
# Run this on the Windows Server 2022 machine hosting Network Operations Platform
# This script performs inspection only - makes NO changes

Write-Host "======================================================================" -ForegroundColor Green
Write-Host "M30.x — NetBox TLS Certificate Architecture INSPECTION" -ForegroundColor Green
Write-Host "Network Operations Platform Windows Server 2022" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  INSPECTION ONLY - NO CHANGES WILL BE MADE" -ForegroundColor Yellow
Write-Host ""

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportFile = "inspection_report_$timestamp.txt"

Start-Transcript -Path $reportFile -Append

Write-Host ""
Write-Host "=== PART A: Active Directory Certificate Services ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "[A.1] Checking AD CS Installation Status..." -ForegroundColor Yellow
try {
    $adcs = Get-WindowsFeature -Name AD-Certificate -ErrorAction Stop
    Write-Host "AD Certificate Services Status:"
    Write-Host "  Name: $($adcs.Name)"
    Write-Host "  Install State: $($adcs.InstallState)"
    
    if ($adcs.InstallState -eq "Installed") {
        Write-Host "  ✅ AD CS IS INSTALLED" -ForegroundColor Green
    } else {
        Write-Host "  ℹ️  AD CS is not installed" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ⚠️  Could not determine AD CS status: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[A.2] Checking for Certification Authority Objects in AD..." -ForegroundColor Yellow
try {
    $rootDSE = [ADSI]"LDAP://RootDSE"
    $configPath = $rootDSE.configurationNamingContext
    $caPath = "LDAP://CN=Certification Authorities,CN=Public Key Services,CN=Services," + $configPath
    $searcher = New-Object System.DirectoryServices.DirectorySearcher
    $searcher.SearchRoot = [ADSI]$caPath
    $searcher.Filter = "(objectClass=pKIEnrollmentService)"
    $cas = $searcher.FindAll()

    if ($cas.Count -gt 0) {
        Write-Host "  ✅ Found $($cas.Count) Certification Authority(ies):" -ForegroundColor Green
        foreach ($ca in $cas) {
            $caName = $ca.Properties.cn[0]
            Write-Host "    - $caName"
        }
    } else {
        Write-Host "  ℹ️  No Certification Authorities found in AD" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ⚠️  Could not query AD for CAs: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[A.3] Checking Trusted Root CAs on This Machine..." -ForegroundColor Yellow
try {
    $rootCAs = Get-ChildItem -Path Cert:\LocalMachine\Root\ -ErrorAction SilentlyContinue
    Write-Host "  Found $($rootCAs.Count) trusted root certificates"
    
    # Show potential internal CAs
    $internalCAs = $rootCAs | Where-Object {
        $_.Subject -match "internal|corp|root|self|local|caizh" -or 
        ($_.Subject -eq $_.Issuer)
    }
    
    if ($internalCAs.Count -gt 0) {
        Write-Host "  💡 Potential internal/self-signed CAs found:" -ForegroundColor Cyan
        foreach ($ca in $internalCAs) {
            Write-Host "    Subject: $($ca.Subject)"
            Write-Host "    Issuer:  $($ca.Issuer)"
            Write-Host "    Thumbprint: $($ca.Thumbprint)"
            Write-Host "    Valid Until: $($ca.NotAfter)"
            Write-Host ""
        }
    } else {
        Write-Host "  ℹ️  No obvious internal CAs found in root store" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ⚠️  Error reading trusted root CAs: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== PART B: Network Operations Platform Certificate Stores ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "[B.1] Checking All Certificate Stores..." -ForegroundColor Yellow

$stores = @(
    'LocalMachine\Root'
    'LocalMachine\CA'
    'LocalMachine\My'
    'CurrentUser\Root'
    'CurrentUser\CA'
    'CurrentUser\My'
)

foreach ($store in $stores) {
    $path = "Cert:\$store"
    try {
        $certs = Get-ChildItem -Path $path -ErrorAction SilentlyContinue
        
        if ($certs.Count -gt 0) {
            Write-Host "  [$store]: $($certs.Count) certificate(s)" -ForegroundColor Yellow
            
            # Only show CA and internal certs
            $relevantCerts = $certs | Where-Object {
                ($_.Subject -eq $_.Issuer) -or 
                ($_.Subject -match "internal|corp|root|ca|caizh")
            }
            
            if ($relevantCerts) {
                foreach ($cert in $relevantCerts) {
                    Write-Host "    - Subject: $($cert.Subject)"
                    Write-Host "      Thumbprint: $($cert.Thumbprint)"
                }
            }
        }
    } catch {
        Write-Host "  Error accessing $store : $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== PART C: Testing HTTPS Connection to NetBox ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "[C.1] Testing PowerShell HTTPS Verification..." -ForegroundColor Yellow

$token = "nbt_SBTm9Eg6H3oz.OHmdynS8XL0crmpj3Fj7ZkE8dIGdTtEKRqAJPNZv"
$headers = @{"Authorization" = "Bearer $token"}

try {
    Write-Host "  Attempting: GET https://caizh.netbox.com/api/status/" -ForegroundColor Gray
    $response = Invoke-WebRequest `
        -Uri "https://caizh.netbox.com/api/status/" `
        -Headers $headers `
        -UseBasicParsing `
        -ErrorAction Stop
    
    Write-Host "  ✅ TLS VERIFICATION PASSED" -ForegroundColor Green
    Write-Host "  Status: $($response.StatusCode)"
    Write-Host "  Response: $($response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 1)"
} catch [System.Net.Http.HttpRequestException] {
    Write-Host "  ❌ HTTPS Connection Failed" -ForegroundColor Red
    Write-Host "  Error Type: $($_.Exception.GetType().Name)"
    Write-Host "  Message: $($_.Exception.Message)"
    
    if ($_.Exception.Message -match "certificate|trust|verify|SSL") {
        Write-Host "  → TLS Certificate Issue: Windows cannot verify the certificate" -ForegroundColor Red
    }
} catch {
    Write-Host "  ❌ Connection Error: $($_.Exception.GetType().Name)" -ForegroundColor Red
    Write-Host "  Message: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== PART D: Python/httpx TLS Verification ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "[D.1] Checking Python Certificate Verification..." -ForegroundColor Yellow

$pythonScript = @"
import certifi
import ssl
import socket

print('[D.1.1] Python certifi CA bundle:')
print(f'  Location: {certifi.where()}')

print()
print('[D.1.2] Testing TLS connection with Python ssl module:')

hostname = 'caizh.netbox.com'
port = 443

try:
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            print(f'  ✅ TLS VERIFICATION PASSED')
            
            # Extract subject
            subject_dict = dict(x[0] for x in cert.get('subject', []))
            print(f'  Subject CN: {subject_dict.get(\"commonName\", \"N/A\")}')
            
            # Extract issuer
            issuer_dict = dict(x[0] for x in cert.get('issuer', []))
            print(f'  Issuer CN: {issuer_dict.get(\"commonName\", \"N/A\")}')
            
            # Check SAN
            san = cert.get('subjectAltName', [])
            print(f'  SAN: {san}')
            
except ssl.SSLError as e:
    print(f'  ❌ TLS VERIFICATION FAILED')
    print(f'  Error: {e}')
    print(f'  Reason: {e.reason if hasattr(e, "reason") else "Certificate not trusted"}')
    
except Exception as e:
    print(f'  ❌ Error: {type(e).__name__}: {e}')
"@

try {
    $pythonOutput = .\.venv\Scripts\python.exe -c $pythonScript
    Write-Host $pythonOutput
} catch {
    Write-Host "  ⚠️  Could not run Python test: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== PART E: System Information ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "[E.1] OS and Domain Information..." -ForegroundColor Yellow

$osInfo = Get-ComputerInfo
Write-Host "  OS: $($osInfo.OsName) $($osInfo.OsVersion)"
Write-Host "  Computer Name: $($osInfo.CsComputerNamePhysicalDnsHostname)"
Write-Host "  Domain: $($osInfo.CsDomain)"
Write-Host "  Domain Role: $($osInfo.CsDomainRole)"

Write-Host ""
Write-Host "=== INSPECTION COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "Results saved to: $reportFile" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run the following commands on NetBox host (via SSH):" -ForegroundColor Gray
Write-Host "     ssh root@caizh.netbox.com" -ForegroundColor Gray
Write-Host "     (Then run commands from INSPECTION-PLAN-M30.x-TLS-CERTIFICATE.md Part B)" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Gather all output and review findings" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Return full inspection report for analysis" -ForegroundColor Gray
Write-Host ""

Stop-Transcript

Write-Host "Full transcript: $reportFile" -ForegroundColor Green
