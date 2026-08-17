import ssl
import socket

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
