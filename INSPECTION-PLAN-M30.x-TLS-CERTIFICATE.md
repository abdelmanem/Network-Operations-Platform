# M30.x — NetBox TLS Certificate Architecture Inspection Plan

**Date:** 2026-08-16  
**Environment:** Windows Server 2022 AD + Ubuntu NetBox 4.6.8  
**Scope:** INSPECTION ONLY — No changes, no certificate generation, no deployments

---

## Inspection Phase Overview

This document specifies the exact inspection commands to determine:
1. Whether AD CS (Enterprise Root CA) exists in your AD environment
2. Whether internal CA already exists and is trusted
3. NetBox deployment architecture (bare-metal/systemd vs Docker)
4. Current nginx TLS configuration and certificate status
5. Certificate trust situation on Network Operations Platform
6. Safest remediation path for this specific environment

---

## Part A: Windows Server 2022 / AD Environment Inspection

### A.1 Check for AD Certificate Services (AD CS)

**Command 1: Check AD CS Installation Status**

```powershell
# Run on Windows Server 2022 / CAIZH-DC or any domain-connected Windows machine
# (Network Operations Platform is domain-connected)

# Check if AD CS role is installed
Get-WindowsFeature -Name AD-Certificate | Select-Object Name, InstallState

# Expected output:
# Name           InstallState
# ----           ----------
# AD-Certificate       Installed    ← If AD CS is present
# or
# AD-Certificate     Available     ← If AD CS is not installed
```

**Command 2: Check for Active Certification Authority**

```powershell
# If AD CS is installed, check for running Enterprise Root CA

# Method 1: Check ADSI for certification authority objects
$rootDSE = [ADSI]"LDAP://RootDSE"
$configPath = $rootDSE.configurationNamingContext
$caPath = "LDAP://CN=Certification Authorities,CN=Public Key Services,CN=Services," + $configPath
$searcher = New-Object System.DirectoryServices.DirectorySearcher
$searcher.SearchRoot = [ADSI]$caPath
$searcher.Filter = "(objectClass=pKIEnrollmentService)"
$cas = $searcher.FindAll()

if ($cas.Count -gt 0) {
    Write-Host "Found $($cas.Count) Certification Authority(ies):"
    foreach ($ca in $cas) {
        $caName = $ca.Properties.cn[0]
        Write-Host "  - $caName"
        # Details of each CA
        foreach ($prop in $ca.Properties.Keys) {
            if ($prop -match "pkiExtendedKeyUsage|pkiMaxIssuingDepth") {
                Write-Host "    $prop: $($ca.Properties[$prop] -join ', ')"
            }
        }
    }
} else {
    Write-Host "No Certification Authority found in AD"
}

# Method 2: Simple check for AD CS service
Get-Service -Name CertSvc -ErrorAction SilentlyContinue | Select-Object Name, Status, DisplayName
```

**Command 3: Enumerate Windows Trusted Root CAs**

```powershell
# Check what root CAs are already trusted on this Windows machine

Write-Host "=== Trusted Root Certification Authorities ===" -ForegroundColor Green

Get-ChildItem -Path Cert:\LocalMachine\Root\ | ForEach-Object {
    Write-Host ""
    Write-Host "Subject: $($_.Subject)"
    Write-Host "Issuer: $($_.Issuer)"
    Write-Host "Thumbprint: $($_.Thumbprint)"
    Write-Host "Valid From: $($_.NotBefore) to $($_.NotAfter)"
    
    # Highlight internal/self-signed CAs
    if ($_.Subject -eq $_.Issuer) {
        Write-Host "  ⚠️  SELF-SIGNED or ROOT CA" -ForegroundColor Yellow
    }
    
    # Highlight any CA with "internal", "corp", "ca", etc.
    if ($_.Subject -match "internal|corp|ca|root" -or $_.Issuer -match "internal|corp|ca") {
        Write-Host "  💡 POSSIBLE INTERNAL CA" -ForegroundColor Cyan
    }
}

# Filter to show only internal/non-public CAs
Write-Host ""
Write-Host "=== Filtered: Internal/Non-Public CAs ===" -ForegroundColor Green
Get-ChildItem -Path Cert:\LocalMachine\Root\ | Where-Object {
    $_.Subject -match "internal|corp|root|self|local" -or 
    $_.Issuer -ne "CN=GlobalSign,O=GlobalSign,C=BE" -and 
    $_.Issuer -ne "CN=DigiCert Global Root CA,OU=www.digicert.com,O=DigiCert Inc,C=US"
} | ForEach-Object {
    Write-Host "Found: $($_.Subject)" -ForegroundColor Yellow
}
```

### A.2 Check Network Operations Platform Certificate Stores

```powershell
# Inspect all certificate stores on the Network Operations Platform host

Write-Host "=== All Certificate Stores on This Host ===" -ForegroundColor Green

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
    $certs = Get-ChildItem -Path $path -ErrorAction SilentlyContinue
    
    if ($certs.Count -gt 0) {
        Write-Host ""
        Write-Host "[$store] - $($certs.Count) certificate(s)" -ForegroundColor Cyan
        $certs | ForEach-Object {
            Write-Host "  Subject: $($_.Subject)"
            if ($_.Subject -ne $_.Issuer) {
                Write-Host "  Issuer:  $($_.Issuer)"
            } else {
                Write-Host "  Issuer:  (self-signed)"
            }
        }
    }
}
```

### A.3 Check if Windows Can Already Trust NetBox Certificate

```powershell
# Test HTTPS connection to NetBox to see what happens

Write-Host "=== Testing HTTPS Connection to NetBox ===" -ForegroundColor Green

$token = "nbt_SBTm9Eg6H3oz.OHmdynS8XL0crmpj3Fj7ZkE8dIGdTtEKRqAJPNZv"
$headers = @{"Authorization" = "Bearer $token"}

try {
    $response = Invoke-WebRequest `
        -Uri "https://caizh.netbox.com/api/status/" `
        -Headers $headers `
        -UseBasicParsing `
        -ErrorAction Stop
    
    Write-Host "✅ SUCCESS: TLS verification passed!"
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Content: $($response.Content)"
} catch [System.Net.Http.HttpRequestException] {
    Write-Host "❌ HTTPS Connection Failed"
    Write-Host "Error Type: $($_.Exception.GetType().Name)"
    Write-Host "Error: $($_.Exception.Message)"
    
    if ($_.Exception.Message -match "certificate|trust|verify") {
        Write-Host "  → TLS Certificate issue detected"
    }
}
```

---

## Part B: NetBox Server (Ubuntu) Inspection

**Run these commands via SSH on the NetBox server:**

```bash
# SSH to NetBox host
ssh root@192.168.137.5
# or
ssh ubuntu@192.168.137.5
# or
ssh caizh.netbox.com
```

### B.1 Determine NetBox Deployment Type

```bash
# Check if running as Docker container
if docker ps 2>/dev/null | grep -q netbox; then
    echo "[RESULT] NetBox is running in Docker"
    docker ps | grep netbox
    docker inspect $(docker ps -q -f "name=netbox") | grep -E "Image|State|Mounts" | head -20
else
    echo "[RESULT] NetBox is NOT running in Docker"
fi

echo ""

# Check if running as systemd service
if systemctl list-units --type=service 2>/dev/null | grep -q netbox; then
    echo "[RESULT] NetBox is running as systemd service"
    systemctl status netbox
else
    echo "[RESULT] NetBox is NOT running as systemd service"
fi

echo ""

# Check process directly
echo "[RESULT] NetBox processes:"
ps aux | grep -E "python.*netbox|gunicorn|uwsgi|docker" | grep -v grep
```

### B.2 Inspect Nginx TLS Configuration

```bash
# Find nginx configuration
echo "[RESULT] Nginx installation:"
which nginx
nginx -v

echo ""
echo "[RESULT] Nginx configuration locations:"
find /etc/nginx -name "*.conf" 2>/dev/null | head -20

echo ""
echo "[RESULT] Main nginx.conf:"
cat /etc/nginx/nginx.conf | grep -A10 "server {" | head -30

echo ""
echo "[RESULT] TLS configuration (sites-enabled):"
ls -la /etc/nginx/sites-enabled/

echo ""
echo "[RESULT] NetBox server block config:"
cat /etc/nginx/sites-enabled/* 2>/dev/null | grep -A20 "server {" | grep -E "ssl_certificate|listen|server_name" | head -20

echo ""
echo "[RESULT] Current certificate and key in use:"
grep -n "ssl_certificate" /etc/nginx/sites-enabled/* 2>/dev/null
```

### B.3 Inspect Current Certificate Details

```bash
echo "[RESULT] Certificate location:"
ls -la /etc/ssl/certs/netbox.crt /etc/ssl/private/netbox.key

echo ""
echo "[RESULT] Certificate details:"
openssl x509 -in /etc/ssl/certs/netbox.crt -text -noout

echo ""
echo "[RESULT] Certificate verification (self-signed check):"
openssl x509 -in /etc/ssl/certs/netbox.crt -noout -issuer -subject

echo ""
echo "[RESULT] Certificate SAN (Subject Alternative Name):"
openssl x509 -in /etc/ssl/certs/netbox.crt -noout -text | grep -A5 "Subject Alternative Name" || echo "❌ NO SAN FOUND"

echo ""
echo "[RESULT] Certificate file permissions:"
stat /etc/ssl/certs/netbox.crt
stat /etc/ssl/private/netbox.key

echo ""
echo "[RESULT] Certificate MD5 fingerprint:"
openssl x509 -in /etc/ssl/certs/netbox.crt -noout -fingerprint -md5

echo ""
echo "[RESULT] Certificate validity period:"
openssl x509 -in /etc/ssl/certs/netbox.crt -noout -dates
```

### B.4 Look for Existing Internal CA Material

```bash
echo "[RESULT] Searching for CA material on NetBox server:"

echo ""
echo "--- In /etc/ssl/certs/ ---"
ls -la /etc/ssl/certs/ | grep -E "\.crt|\.ca|root|internal|self" || echo "(no CA certs found)"

echo ""
echo "--- In /etc/ssl/private/ ---"
ls -la /etc/ssl/private/ | grep -E "\.key|\.pem" || echo "(no private keys found)"

echo ""
echo "--- In /etc/ca-certificates/ ---"
ls -la /etc/ca-certificates 2>/dev/null || echo "(directory not found)"

echo ""
echo "--- In /usr/local/share/ca-certificates/ ---"
ls -la /usr/local/share/ca-certificates/ 2>/dev/null || echo "(directory not found)"

echo ""
echo "--- Search for any '.ca' or '.crt' files in /etc/ ---"
find /etc -name "*\.ca" -o -name "*internal*ca*" -o -name "*root*ca*" 2>/dev/null | head -20

echo ""
echo "--- Check if there's an existing CA certificate bundle ---"
cat /etc/ssl/certs/ca-bundle.crt 2>/dev/null | head -5 || echo "(ca-bundle not found)"
cat /etc/ssl/certs/ca-certificates.crt 2>/dev/null | head -5 || echo "(ca-certificates.crt not found)"
```

### B.5 Check System CA Trust Store

```bash
echo "[RESULT] System CA certificate store:"
update-ca-certificates --list 2>/dev/null | grep -E "internal|corp|root|self" || echo "No internal CAs in system store"

echo ""
echo "[RESULT] Count of trusted CAs:"
ls -1 /etc/ssl/certs/*.pem 2>/dev/null | wc -l
```

### B.6 Check for Docker Compose or Deployment Config

```bash
echo "[RESULT] Docker-related files (if applicable):"
find /opt -name "docker-compose.yml" -o -name "docker-compose.yaml" 2>/dev/null

echo ""
echo "[RESULT] NetBox installation directory:"
find /opt -name "netbox*" -type d 2>/dev/null | head -10

echo ""
echo "[RESULT] Check for any CA configuration in NetBox config:"
grep -r "certificate\|tls\|ssl\|ca_bundle" /opt/netbox/ 2>/dev/null | grep -v ".git" | head -20
```

---

## Part C: Network Operations Platform Python/httpx Trust Analysis

### C.1 Python Certificate Verification Behavior

```powershell
# On Network Operations Platform Windows machine

# Check what certifi (the default Python CA bundle) contains
.venv\Scripts\python.exe -c "
import certifi
import ssl

print('[RESULT] Python certifi CA bundle location:')
print(f'  Path: {certifi.where()}')

print()
print('[RESULT] System SSL context verify mode:')
ctx = ssl.create_default_context()
print(f'  Verify mode: {ctx.verify_mode}')
print(f'  Check hostname: {ctx.check_hostname}')

print()
print('[RESULT] Checking if caizh.netbox.com certificate is trusted:')

import socket
import ssl

hostname = 'caizh.netbox.com'
port = 443

try:
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            print(f'  ✅ Certificate is TRUSTED')
            print(f'  Subject: {dict(x[0] for x in cert[\"subject\"])}')
            print(f'  Issuer: {dict(x[0] for x in cert[\"issuer\"])}')
            print(f'  SAN: {cert.get(\"subjectAltName\", \"NOT FOUND\")}')
except ssl.SSLError as e:
    print(f'  ❌ Certificate is NOT TRUSTED')
    print(f'  Error: {e}')
    print(f'  Error reason: {e.reason if hasattr(e, \"reason\") else \"Unknown\"}')
except Exception as e:
    print(f'  Error: {type(e).__name__}: {e}')
"
```

---

## Part D: Comprehensive Inspection Checklist

Create a summary document with these findings:

### ✓ Checklist Items

- [ ] **AD CS Status**
  - [ ] Enterprise Root CA exists in AD? (Yes/No)
  - [ ] CA Name: _________________
  - [ ] CA Type: Root / Subordinate / Other
  - [ ] Root certificate CN: _________________

- [ ] **Windows Trust Store**
  - [ ] Internal CA already present? (Yes/No)
  - [ ] CA Name: _________________
  - [ ] CA Certificate Thumbprint: _________________
  - [ ] CA Valid Until: _________________

- [ ] **NetBox Deployment**
  - [ ] Type: [ ] Bare-metal/systemd [ ] Docker [ ] Other: _________
  - [ ] Init system: systemd / docker-compose / other
  - [ ] Service name: _________________
  - [ ] Configuration file: _________________

- [ ] **Current Certificate**
  - [ ] Location: /etc/ssl/certs/netbox.crt
  - [ ] Key location: /etc/ssl/private/netbox.key
  - [ ] Self-signed? Yes / No
  - [ ] Has SAN? Yes / **No** ← Current issue
  - [ ] SAN value: _________________
  - [ ] Valid from: _________________
  - [ ] Valid until: _________________
  - [ ] CN: _________________
  - [ ] Issuer CN: _________________

- [ ] **Nginx Configuration**
  - [ ] Nginx installed? Yes / No
  - [ ] TLS config file: _________________
  - [ ] SSL certificate directive: _________________
  - [ ] SSL key directive: _________________

- [ ] **Existing Internal CA**
  - [ ] CA certificate exists on NetBox? (Yes/No)
  - [ ] CA location: _________________
  - [ ] CA CN: _________________
  - [ ] CA usage: _________________

- [ ] **Network Operations Platform Trust**
  - [ ] Can httpx reach caizh.netbox.com? Yes / No
  - [ ] TLS verification passes? Yes / **No**
  - [ ] Error type: _________________
  - [ ] Certifi CA bundle location: _________________

---

## Part E: Expected Results

After running all inspection commands, you should have:

1. **Certificate architecture decision tree:**
   ```
   IF AD CS exists and Enterprise Root CA is present
     → Use Option C: Request cert from AD CS Enterprise Root CA
   ELSE IF internal CA already exists on NetBox
     → Use Option B: Reuse existing internal CA to sign new cert
   ELSE
     → Use Option A: Create new dedicated internal self-signed CA
   ```

2. **Exact deployment path identified:**
   - Is it systemd? → Restart: systemctl restart nginx
   - Is it Docker? → Restart: docker-compose restart OR docker restart
   - Is it managed? → Verify change procedure

3. **Certificate replacement procedure:**
   - Exact file paths for current cert/key
   - Exact nginx config file to verify
   - Ownership/permissions to preserve
   - Restart command for this environment

4. **Trust chain on Network Operations Platform:**
   - Must import CA into: Windows Trusted Root CA store OR custom Python CA bundle
   - Exact import procedure for Windows
   - Exact configuration for Python/httpx

---

## Next Steps

1. **Run all Part A commands** (PowerShell on Windows) and capture output
2. **Run all Part B commands** (SSH to NetBox) and capture output
3. **Run Part C command** (Python on Windows) and capture output
4. **Fill in Part D checklist** with results
5. **Return all findings** in one response

Once inspection is complete and approved, I will provide:
- Exact certificate generation commands (if new CA needed)
- Exact deployment commands
- Exact trust store import commands
- Exact Network Operations Platform configuration changes
- Verification/rollback procedures

---

**⏸️ AWAITING INSPECTION RESULTS**

Do not proceed until all inspection output has been collected and reviewed.
