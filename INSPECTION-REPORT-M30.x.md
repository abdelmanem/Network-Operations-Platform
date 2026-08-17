# M30.x — NetBox TLS Certificate Architecture Inspection Report

**Date:** 2026-08-16  
**Status:** IN PROGRESS - Awaiting NetBox server inspection

---

## Part 1: Windows Network Operations Platform Inspection (COMPLETE)

### A.1 Active Directory Certificate Services

**Finding:** `Get-WindowsFeature` not available on this machine.
- This is a workstation, not a Domain Controller or Server with RSAT installed
- AD CS may still exist in the domain (on DC) but cannot be queried from this machine
- **Status**: Cannot determine AD CS availability from workstation

**Next Check:** Query AD domain directly or ask administrator if AD CS exists in CAIZH.radissonhotels.com domain

### A.2 Existing Enterprise CAs in Windows Trust Store

**Major Finding:** ✅ **INTERNAL ENTERPRISE CAS ALREADY EXIST AND ARE TRUSTED!**

Discovered 72 root certificates including several internal enterprise CAs:

```
1. CN=CAIZH-LT-ADIT.CAIZH.radissonhotels.com (multiple instances)
   - Valid until: 02/20/3025, 02/15/3025, 02/07/3025, etc.
   - This appears to be an Enterprise Root CA from CAIZH organization

2. CN=CAIZH-LT-ADIT.caih.rezidor.com (multiple instances)
   - Valid until: 08/08/3024, 01/13/3025, 11/03/3023, etc.
   - Sister CA for Rezidor (parent company)

3. CN=CAIZH-LT-ADIT (standalone)
   - Valid until: 01/18/3025
   - Generic root CA reference
```

**Implication:** These CAs are already in the Windows Trusted Root CA store and are valid until ~3025 (25+ years). 

### A.3 Current NetBox Certificate Issue

**Test Result:**
```
PowerShell Invoke-WebRequest to https://caizh.netbox.com/api/status/
  → [FAIL] TLS Certificate Issue - Windows cannot verify

Python ssl module test
  → [FAIL] SSL Error: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate
```

**Root Cause:** The NetBox certificate is self-signed and not signed by the enterprise CA (CAIZH-LT-ADIT)

### A.4 Recommendation for Windows

**Option A (PREFERRED):** Request/generate NetBox certificate from the existing enterprise CA
- CA Name: `CAIZH-LT-ADIT.CAIZH.radissonhotels.com` (already trusted on Windows)
- Requirement: Must add SAN extension: `DNS:caizh.netbox.com`
- Windows will automatically trust it (CA already in store)
- No additional import needed on Windows

**Option B (FALLBACK):** Import the self-signed certificate into Windows Trusted Root CA store
- Less secure than Option A
- Requires manual import on every machine
- Not recommended for production

---

## Part 2: NetBox Server Inspection (PENDING)

**Still Needed:** SSH to NetBox host and run inspection commands

### Commands to Run

SSH into NetBox and execute the inspection script:

```bash
# Copy the script to NetBox or run commands inline:
ssh root@caizh.netbox.com

# Then run each section from: ssh_inspect_netbox.sh
```

**Key questions to be answered by NetBox inspection:**

1. Is NetBox running in Docker, systemd, or other?
2. What nginx version and configuration is in use?
3. Current certificate location and permissions
4. Is there already a CA certificate infrastructure on NetBox?
5. What is the exact path to the certificate and key?
6. Is there an existing CA that could be used for signing?

---

## Preliminary Recommendations (Based on Windows Findings)

### Certificate Architecture Decision

Given that **CAIZH-LT-ADIT enterprise CA already exists and is trusted on Windows**, the safest approach is:

```
Preferred Solution:
  1. Identify the CAIZH-LT-ADIT CA infrastructure location
  2. Request new certificate from CAIZH-LT-ADIT for caizh.netbox.com
  3. Include SAN: DNS:caizh.netbox.com
  4. Deploy on NetBox
  5. Windows will automatically trust it (CA already imported)
  6. Python/httpx will automatically trust it (CA in standard store)
  7. No application code changes needed
  8. No additional imports needed
```

### Timeline

Once NetBox inspection is complete:
- If enterprise CA available: **~30 minutes** (request cert + deploy)
- If no enterprise CA: **~45 minutes** (create internal CA + deploy)

---

## Next Steps

1. **SSH to NetBox** and execute the inspection commands
2. **Provide output** from: `ssh_inspect_netbox.sh`
3. **Confirm** whether enterprise CA is accessible from NetBox
4. **I will then provide** exact implementation plan

---

## Files Created

- [INSPECTION-PLAN-M30.x-TLS-CERTIFICATE.md](INSPECTION-PLAN-M30.x-TLS-CERTIFICATE.md) - Full inspection methodology
- [M30.x-NETBOX-TLS-CERTIFICATE-ANALYSIS.md](M30.x-NETBOX-TLS-CERTIFICATE-ANALYSIS.md) - Detailed analysis and options
- [ssh_inspect_netbox.sh](ssh_inspect_netbox.sh) - NetBox server inspection script
- [inspect_windows_final.ps1](inspect_windows_final.ps1) - Windows inspection script (completed)
- [test_netbox_tls.py](test_netbox_tls.py) - Python TLS test

---

## Status

✅ **Windows Inspection: COMPLETE**
- Enterprise CA CAIZH-LT-ADIT discovered and trusted
- Current NetBox cert: Self-signed, no SAN, not trusted

⏳ **NetBox Server Inspection: PENDING**
- Awaiting SSH output from NetBox inspection script

⏹️ **No infrastructure changes made yet** - Inspection only

---

**AWAITING NETBOX SERVER INSPECTION OUTPUT**
