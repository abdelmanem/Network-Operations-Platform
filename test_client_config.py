"""Test that NetBox client loads with certificate configuration."""
import asyncio
from backend.app.config.settings import get_settings
from backend.app.integrations.netbox.client import NetBoxClient

async def test_netbox_client():
    print("[TEST] Loading NetBox client with certificate configuration")
    print()
    
    settings = get_settings()
    print(f"NetBox URL: {settings.netbox_base_url}")
    print(f"NetBox CA Cert: {settings.netbox_ca_cert}")
    print(f"NetBox Token: ***SET***")
    print()
    
    # Create client
    client = NetBoxClient.from_settings(settings)
    print(f"[SUCCESS] NetBox client created")
    print(f"  Base URL: {client.base_url}")
    print(f"  CA Cert: {client.ca_cert}")
    print(f"  Timeout: {client.timeout_seconds}s")
    print()
    
    # Test API call
    print("[TEST] Testing /api/status/ endpoint")
    try:
        response = await client.health()
        print(f"[SUCCESS] HTTP 200")
        print(f"  Version: {response.version}")
        print(f"  Hostname: {response.hostname}")
    except Exception as e:
        print(f"[FAILED] {type(e).__name__}: {e}")
    finally:
        await client.aclose()

if __name__ == '__main__':
    asyncio.run(test_netbox_client())
