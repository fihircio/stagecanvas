import unittest
import sys
import os
from pathlib import Path

# Add orchestration-server to path so 'app' can be found
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token, FAKE_USERS_DB

class TestRBAC(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_login_success(self):
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": "admin", "password": "admin123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())

    def test_login_failure(self):
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": "admin", "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, 401)

    def test_protected_route_no_token(self):
        # /api/v1/operators/pause is secured with 'operator' role
        response = self.client.post(
            "/api/v1/operators/pause",
            json={"payload": {}, "node_ids": [], "request_id": "req-1"}
        )
        self.assertEqual(response.status_code, 401)

    def test_operator_access_to_pause(self):
        # Login as operator
        login_res = self.client.post(
            "/api/v1/auth/token",
            data={"username": "operator", "password": "op123"}
        )
        token = login_res.json()["access_token"]
        
        response = self.client.post(
            "/api/v1/operators/pause",
            json={"payload": {}, "node_ids": [], "request_id": "req-2"},
            headers={"Authorization": f"Bearer {token}"}
        )
        # 200 or 409 depending on idempotency/registry state, but NOT 401/403
        self.assertIn(response.status_code, [200, 409])

    def test_viewer_denied_pause(self):
        # Login as viewer
        login_res = self.client.post(
            "/api/v1/auth/token",
            data={"username": "view", "password": "view123"}
        )
        token = login_res.json()["access_token"]
        
        response = self.client.post(
            "/api/v1/operators/pause",
            json={"payload": {}, "node_ids": [], "request_id": "req-3"},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 403)

    def test_designer_access_to_timeline(self):
        # Login as designer
        login_res = self.client.post(
            "/api/v1/auth/token",
            data={"username": "designer", "password": "design123"}
        )
        token = login_res.json()["access_token"]
        
        response = self.client.post(
            "/api/v1/timeline/shows/test-show",
            json={"duration_ms": 10000},
            headers={"Authorization": f"Bearer {token}"}
        )
        # Note: endpoint is PUT in main.py, let's check
        res_put = self.client.put(
            "/api/v1/timeline/shows/test-show",
            json={"duration_ms": 10000},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res_put.status_code, 200)

    def test_operator_denied_timeline_edit(self):
        # Login as operator
        login_res = self.client.post(
            "/api/v1/auth/token",
            data={"username": "operator", "password": "op123"}
        )
        token = login_res.json()["access_token"]
        
        response = self.client.put(
            "/api/v1/timeline/shows/test-show",
            json={"duration_ms": 10000},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 403)

if __name__ == "__main__":
    unittest.main()
