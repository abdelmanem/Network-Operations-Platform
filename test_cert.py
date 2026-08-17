import httpx
from pathlib import Path

cert_path = Path('certs/netbox.crt')
print(f'[TEST 1] Testing HTTPS connection with certificate trust')
print(f'Certificate path: {cert_path.absolute()}')
print()

token = "nbt_SBTm9Eg6H3oz.OHmdynS8XL0crmpj3Fj7ZkE8dIGdTtEKRqAJPNZv"
headers = {'Authorization': f'Bearer {token}'}

try:
    response = httpx.get(
        'https://caizh.netbox.com/api/status/',
        headers=headers,
        verify=str(cert_path.absolute()),
        timeout=httpx.Timeout(10)
    )
    print(f'[SUCCESS] HTTP {response.status_code}')
    print(f'Response: {response.json()}')
    
except Exception as e:
    error_msg = str(e)
    print(f'[FAILED] {type(e).__name__}')
    print(f'Error: {error_msg}')
    
    if 'Hostname mismatch' in error_msg or 'verify' in error_msg.lower():
        print()
        print('[DIAGNOSIS] Hostname verification issue detected.')
        print('The certificate may not have the correct SAN or CN.')
    
    if 'certificate verify failed' in error_msg:
        print('[DIAGNOSIS] Certificate validation failed.')
        print('The certificate may not be properly formatted or valid.')
