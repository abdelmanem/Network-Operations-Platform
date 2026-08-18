import os
from pathlib import Path

import httpx
from backend.app.config.settings import get_settings

settings = get_settings()
cert_path = (
    Path(settings.netbox_ca_cert).expanduser() if settings.netbox_ca_cert else None
)
print("[TEST 1] Testing HTTPS connection with certificate trust")
if cert_path is not None:
    print(f"Certificate path: {cert_path.resolve()}")
else:
    print("Certificate path: system default trust store")
print()

token = settings.netbox_token
headers = {"Authorization": f"Bearer {token}"}

if not token:
    raise RuntimeError(
        "NETBOX_TOKEN is not configured; "
        "configure the project .env before running this script."
    )

try:
    response = httpx.get(
        f"{settings.netbox_base_url}/api/status/",
        headers=headers,
        verify=str(cert_path.resolve()) if cert_path else True,
        timeout=httpx.Timeout(settings.netbox_timeout_seconds),
    )
    print(f"[SUCCESS] HTTP {response.status_code}")
    print("Response received successfully.")
except (OSError, ValueError, TypeError, httpx.HTTPError) as exc:
    error_msg = str(exc)
    print(f"[FAILED] {type(exc).__name__}")
    print(f"Error: {error_msg}")

    if "Hostname mismatch" in error_msg or "verify" in error_msg.lower():
        print()
        print("[DIAGNOSIS] Hostname verification issue detected.")
        print("The certificate may not have the correct SAN or CN.")

    if "certificate verify failed" in error_msg:
        print("[DIAGNOSIS] Certificate validation failed.")
        print("The certificate may not be properly formatted or valid.")

os.environ.setdefault("NETBOX_TOKEN", token)
