"""Verify Supabase user tokens and the shared employee allowlist."""

import os
import secrets

import httpx


async def authorized_user(token: str) -> dict | None:
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_PUBLISHABLE_KEY', '')
    if not url or not key or not token:
        return None

    headers = {'apikey': key, 'Authorization': f'Bearer {token}'}
    async with httpx.AsyncClient(timeout=8) as client:
        user_response = await client.get(f'{url}/auth/v1/user', headers=headers)
        if user_response.status_code != 200:
            return None
        user = user_response.json()
        email = str(user.get('email') or '').strip().lower()
        user_id = str(user.get('id') or '')
        if not email or not user_id:
            return None
        allow_response = await client.get(
            f'{url}/rest/v1/app_users',
            headers=headers,
            params={'select': 'email', 'email': f'eq.{email}', 'working_status': 'eq.permanent', 'limit': '1'},
        )
        if allow_response.status_code != 200 or not allow_response.json():
            return None
        return {'id': user_id, 'email': email}


def has_sync_secret(request) -> bool:
    secret = os.environ.get('SYNC_SECRET', '')
    if not secret:
        return False
    header = request.headers.get('x-sync-secret') or request.headers.get('authorization', '')
    provided = request.query_params.get('secret') or header.removeprefix('Bearer ').strip()
    return secrets.compare_digest(provided, secret)
