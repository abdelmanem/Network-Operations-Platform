#!/usr/bin/env python3
"""
NetBox Live Validation - Inspection Only
Do not modify application code or disable TLS verification in production paths.
"""
import httpx
from backend.app.config.settings import get_settings

def main():
    settings = get_settings()
    print('=' * 70)
    print('NETBOX LIVE VALIDATION - INSPECTION ONLY')
    print('=' * 70)
    print(f'Target URL: {settings.netbox_base_url}')
    print(f'Configured Token: ***SET***')
    print(f'Expected Version: {settings.netbox_expected_version}')
    print()

    # Test 1: TLS Connection (no auth)
    print('[1] Testing TLS Connection (no auth)...')
    try:
        response = httpx.get(
            f'{settings.netbox_base_url}/api/status/',
            timeout=httpx.Timeout(settings.netbox_timeout_seconds)
        )
        print(f'    HTTP {response.status_code} (no auth sent)')
    except Exception as e:
        if 'CERTIFICATE_VERIFY_FAILED' in str(e) or 'self-signed' in str(e):
            print(f'    TLS ERROR: Certificate verification failed')
            print(f'    Cause: Self-signed certificate detected')
        else:
            print(f'    Error: {type(e).__name__}')

    print()

    # Test 2: With authentication and TLS verification enabled
    print('[2] Testing with Authentication (TLS verification ON)...')
    token = settings.netbox_token
    headers = {'Authorization': f'Bearer {token}'}

    try:
        with httpx.Client(
            base_url=settings.netbox_base_url,
            headers=headers,
            timeout=httpx.Timeout(settings.netbox_timeout_seconds),
            verify=True
        ) as client:
            response = client.get('/api/status/')
            print(f'    GET /api/status/')
            print(f'    Status: {response.status_code}')
            if response.status_code == 200:
                print(f'    Result: AUTHENTICATION SUCCESSFUL')
                try:
                    data = response.json()
                    version = data.get('netbox-version', 'unknown')
                    print(f'    NetBox Version: {version}')
                except:
                    print(f'    (response body not JSON)')
            else:
                body_preview = response.text[:200] if response.text else '(empty)'
                print(f'    Result: AUTH FAILED')
                print(f'    Body: {body_preview}')
    except Exception as e:
        if 'CERTIFICATE_VERIFY_FAILED' in str(e) or 'self-signed' in str(e):
            print(f'    TLS VERIFICATION FAILED')
            print(f'    Certificate issue detected - cannot proceed without resolution')
        else:
            print(f'    Error: {type(e).__name__}: {str(e)[:120]}')

    print()
    print('[3] Attempting GET /api/dcim/devices/ (with auth, TLS ON)...')
    try:
        with httpx.Client(
            base_url=settings.netbox_base_url,
            headers=headers,
            timeout=httpx.Timeout(settings.netbox_timeout_seconds),
            verify=True
        ) as client:
            response = client.get('/api/dcim/devices/')
            print(f'    GET /api/dcim/devices/')
            print(f'    Status: {response.status_code}')
            if response.status_code == 200:
                print(f'    Result: SUCCESS')
                try:
                    data = response.json()
                    count = data.get('count', 0)
                    print(f'    Device Count: {count}')
                except:
                    print(f'    (cannot parse response)')
            else:
                body_preview = response.text[:200] if response.text else '(empty)'
                print(f'    Result: FAILED')
                print(f'    Body: {body_preview}')
    except Exception as e:
        if 'CERTIFICATE_VERIFY_FAILED' in str(e) or 'self-signed' in str(e):
            print(f'    TLS VERIFICATION FAILED')
        else:
            print(f'    Error: {type(e).__name__}')

    print()
    print('=' * 70)
    print('VALIDATION COMPLETE')
    print('=' * 70)

if __name__ == '__main__':
    main()
