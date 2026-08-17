#!/bin/bash
# NetBox Server Inspection Commands (Ubuntu Linux)
# Run via SSH on the NetBox host
# INSPECTION ONLY - No changes made

echo "======================================================================="
echo "M30.x — NetBox TLS Certificate INSPECTION (NetBox Server)"
echo "======================================================================="
echo ""

echo "[B.1] Determine NetBox Deployment Type..."
echo ""

# Check Docker
if docker ps 2>/dev/null | grep -q netbox; then
    echo "RESULT: NetBox is running in Docker"
    echo ""
    docker ps | grep netbox
    echo ""
else
    echo "RESULT: NetBox is NOT running in Docker"
    echo ""
fi

# Check systemd
if systemctl list-units --type=service 2>/dev/null | grep -q netbox; then
    echo "RESULT: NetBox is running as systemd service"
    echo ""
    systemctl status netbox --no-pager 2>/dev/null || echo "(service info not available)"
    echo ""
else
    echo "RESULT: NetBox is NOT running as systemd service"
    echo ""
fi

# Check processes
echo "RESULT: Running processes related to NetBox/Python/web:"
ps aux | grep -E "python|netbox|gunicorn|uwsgi|nginx" | grep -v grep | head -20
echo ""

echo "[B.2] Inspect Nginx TLS Configuration..."
echo ""

echo "RESULT: Nginx version:"
nginx -v 2>&1
echo ""

echo "RESULT: Nginx configuration files:"
find /etc/nginx -name "*.conf" 2>/dev/null | head -20
echo ""

echo "RESULT: Nginx sites-enabled configuration:"
ls -la /etc/nginx/sites-enabled/ 2>/dev/null || echo "(directory not found or inaccessible)"
echo ""

echo "RESULT: TLS certificate and key configuration in nginx:"
if [ -d /etc/nginx/sites-enabled ]; then
    grep -h "ssl_certificate" /etc/nginx/sites-enabled/* 2>/dev/null | head -10
else
    echo "(sites-enabled not found)"
fi
echo ""

echo "[B.3] Inspect Current Certificate..."
echo ""

echo "RESULT: Certificate and key file details:"
ls -lah /etc/ssl/certs/netbox.crt 2>/dev/null || echo "(netbox.crt not found)"
ls -lah /etc/ssl/private/netbox.key 2>/dev/null || echo "(netbox.key not found)"
echo ""

echo "RESULT: Certificate full details (subject, issuer, dates):"
openssl x509 -in /etc/ssl/certs/netbox.crt -text -noout 2>/dev/null | grep -A20 "Subject:" || echo "(certificate read failed)"
echo ""

echo "RESULT: Certificate SAN (Subject Alternative Name) - THIS IS THE ISSUE:"
openssl x509 -in /etc/ssl/certs/netbox.crt -noout -text 2>/dev/null | grep -A3 "Subject Alternative Name" || echo "NO SAN FOUND - This is why Python/httpx cannot verify!"
echo ""

echo "RESULT: Certificate validity dates:"
openssl x509 -in /etc/ssl/certs/netbox.crt -noout -dates 2>/dev/null
echo ""

echo "RESULT: Certificate MD5 fingerprint:"
openssl x509 -in /etc/ssl/certs/netbox.crt -noout -fingerprint -md5 2>/dev/null
echo ""

echo "RESULT: Is certificate self-signed? (check if subject == issuer)"
openssl x509 -in /etc/ssl/certs/netbox.crt -noout -issuer -subject 2>/dev/null
echo ""

echo "[B.4] Look for Existing Internal CA Material..."
echo ""

echo "RESULT: CA-related files in /etc/ssl/:"
find /etc/ssl -name "*\.ca" -o -name "*internal*" -o -name "*root*" 2>/dev/null | grep -v "certs/ca-" || echo "(none found)"
echo ""

echo "RESULT: All certificate files in /etc/ssl/certs/:"
ls /etc/ssl/certs/*.crt 2>/dev/null | wc -l
echo " (certificate files found in total)"
echo ""

echo "RESULT: Check for internal/self-signed CAs in certificate store:"
for f in /etc/ssl/certs/*.pem /etc/ssl/certs/*.crt 2>/dev/null; do
    if openssl x509 -in "$f" -noout -text 2>/dev/null | grep -q "Subject.*internal\|Subject.*CAIZH\|Subject.*corp"; then
        echo "  Found: $f"
        openssl x509 -in "$f" -noout -subject 2>/dev/null | head -1
    fi
done 2>/dev/null | head -20
echo ""

echo "RESULT: Check /usr/local/share/ca-certificates/ (common custom CA location):"
ls -la /usr/local/share/ca-certificates/ 2>/dev/null || echo "(directory not found)"
echo ""

echo "RESULT: Check /etc/ca-certificates/update.d/ (CA management):"
ls -la /etc/ca-certificates/ 2>/dev/null | head -20 || echo "(directory not found)"
echo ""

echo "[B.5] Check System CA Trust Store..."
echo ""

echo "RESULT: Update CA certificates list available:"
update-ca-certificates --list 2>/dev/null | grep -i "internal\|caizh\|corp" | head -20 || echo "(no relevant CAs in update list)"
echo ""

echo "RESULT: Total trusted CA certificates on this system:"
ls -1 /etc/ssl/certs/*.pem 2>/dev/null | wc -l
echo ""

echo "[B.6] Check NetBox Deployment Configuration..."
echo ""

echo "RESULT: NetBox installation directory:"
find /opt -name "netbox*" -type d 2>/dev/null | head -10
echo ""

echo "RESULT: Docker Compose configuration (if applicable):"
find / -maxdepth 4 -name "docker-compose*" -type f 2>/dev/null | grep -i netbox || echo "(not found)"
echo ""

echo "RESULT: Systemd service configuration (if applicable):"
cat /etc/systemd/system/netbox* 2>/dev/null | head -30 || echo "(systemd service not found)"
echo ""

echo "[B.7] Summary..."
echo ""

echo "RESULT: Current certificate status:"
echo "  Subject CN: $(openssl x509 -in /etc/ssl/certs/netbox.crt -noout -subject 2>/dev/null | sed 's/subject=//')"
echo "  Issuer CN:  $(openssl x509 -in /etc/ssl/certs/netbox.crt -noout -issuer 2>/dev/null | sed 's/issuer=//')"
echo "  Has SAN:    $(openssl x509 -in /etc/ssl/certs/netbox.crt -noout -text 2>/dev/null | grep -c 'Subject Alternative Name')"
echo "  Self-signed: $(if [ \"$(openssl x509 -in /etc/ssl/certs/netbox.crt -noout -issuer -subject 2>/dev/null | cut -d'=' -f2 | sort -u | wc -l)\" = \"1\" ]; then echo 'YES'; else echo 'NO'; fi)"
echo ""

echo "======================================================================="
echo "INSPECTION COMPLETE"
echo "======================================================================="
echo ""
echo "Copy this output and share with the Network Operations Platform analysis."
