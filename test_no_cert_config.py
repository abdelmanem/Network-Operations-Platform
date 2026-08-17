"""Test that NetBox client works without certificate configuration (system default)."""
import asyncio
import os
from pathlib import Path

# Temporarily remove the cert config to test default behavior
os.environ['NETBOX_CA_CERT'] = ''

from backend.app.config.settings import get_settings
from backend.app.integrations.netbox.client import NetBoxClient

# Clear the cached settings to force reload
from backend.app.config.settings import Settings
Settings.model_rebuild()

async def test_without_cert():
    print("[TEST] Loading NetBox client WITHOUT certificate configuration")
    print()
    
    settings = get_settings()
    print(f"NetBox URL: {settings.netbox_base_url}")
    print(f"NetBox CA Cert: {settings.netbox_ca_cert!r}")
    print(f"NetBox Token: ***SET***")
    print()
    
    # Create client
    client = NetBoxClient.from_settings(settings)
    print(f"[SUCCESS] NetBox client created")
    print(f"  Base URL: {client.base_url}")
    print(f"  CA Cert: {client.ca_cert}")
    print(f"  Timeout: {client.timeout_seconds}s")
    print()
    
    # Would use system default trust store
    print("[INFO] Without CA cert specified, httpx will use system default trust store (verify=True)")
    print("       This is the secure default behavior.")
    
    await client.aclose()

if __name__ == '__main__':
    asyncio.run(test_without_cert())
