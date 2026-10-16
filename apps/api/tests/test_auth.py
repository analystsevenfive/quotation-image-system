import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import create_app


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'AUTH_ENABLED': 'true'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(create_app(service=MagicMock()))

    def test_direct_api_request_without_token_is_rejected(self):
        response = self.client.get('/api/products/search?q=chair')
        self.assertEqual(response.status_code, 401)

    def test_health_remains_available(self):
        response = self.client.get('/api/health')
        self.assertNotEqual(response.status_code, 401)

    @patch('app.main.authorized_user')
    def test_invalid_token_is_rejected(self, verify):
        verify.return_value = None
        response = self.client.get('/api/products/search?q=chair', headers={'Authorization': 'Bearer invalid'})
        self.assertEqual(response.status_code, 401)
        verify.assert_awaited_once_with('invalid')

    @patch('app.main.authorized_user')
    def test_authorized_token_reaches_api(self, verify):
        verify.return_value = {'id': 'user-1', 'email': 'user@example.com'}
        response = self.client.get('/api/products/search?q=chair', headers={'Authorization': 'Bearer good'})
        self.assertNotEqual(response.status_code, 401)
        verify.assert_awaited_once_with('good')


if __name__ == '__main__':
    unittest.main()
