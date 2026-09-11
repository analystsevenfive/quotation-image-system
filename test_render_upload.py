"""
Cloud Deployment Verification Script
Tests PDF upload to both Vercel frontend proxy and direct Render backend API.
Usage:
    python test_render_upload.py
"""
import urllib.request
import urllib.error

with open('QT_test.pdf', 'rb') as f:
    pdf_bytes = f.read()

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = (
    f'--{boundary}\r\n'
    'Content-Disposition: form-data; name="file"; filename="QT_test.pdf"\r\n'
    'Content-Type: application/pdf\r\n\r\n'
).encode('utf-8') + pdf_bytes + f'\r\n--{boundary}--\r\n'.encode('utf-8')

for host in ['https://quotation-image-system.vercel.app', 'https://quotation-api-h4ta.onrender.com']:
    print(f"\n--- Testing upload to {host} ---")
    req = urllib.request.Request(
        f'{host}/api/quotations',
        data=body,
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Origin': 'https://quotation-image-system.vercel.app',
            'Sec-Fetch-Site': 'same-origin' if 'vercel' in host else 'cross-site'
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print('Status:', resp.status)
            print('Response snippet:', resp.read()[:200].decode())
    except urllib.error.HTTPError as e:
        print('HTTP Error:', e.code, e.read().decode())
    except Exception as e:
        print('Error:', type(e).__name__, e)
