"""Unit tests for the Flask Backend API and route access controls."""
import json
import unittest
from app.api.app import create_app
from app.repository.connection import DatabaseConnectionManager

class TestBackendAPI(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.headers_admin = {"Authorization": "Bearer super-admin-token-12345"}
        self.headers_hod = {"Authorization": "Bearer hod-token-12345"}

    def test_login_endpoint(self):
        # 1. Successful Super Admin login
        res = self.client.post("/api/auth/login", json={"username": "admin", "password": "adminpassword"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["token"], "super-admin-token-12345")
        self.assertEqual(data["role"], "SUPER_ADMIN")

        # 2. Failed login
        res_fail = self.client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(res_fail.status_code, 401)

    def test_auth_route_protection(self):
        # Accessing faculties list without auth token should return 401
        res = self.client.get("/api/faculties")
        self.assertEqual(res.status_code, 401)

        # Accessing write operations with HOD token should return 403 (requires SUPER_ADMIN)
        res_write = self.client.post("/api/faculties", json={"faculty_id": "F99", "faculty_name": "Dr. X"}, headers=self.headers_hod)
        self.assertEqual(res_write.status_code, 403)

    def test_crud_endpoints(self):
        # 1. Create a Faculty via API
        payload = {
            "faculty_id": "F99",
            "faculty_name": "Test Faculty",
            "max_hours_week": 30,
            "email": "test@test.com",
            "status": "ACTIVE"
        }
        res_create = self.client.post("/api/faculties", json=payload, headers=self.headers_admin)
        self.assertEqual(res_create.status_code, 201) # Created
        
        # 2. Get Faculty
        res_get = self.client.get("/api/faculties/F99", headers=self.headers_hod)
        self.assertEqual(res_get.status_code, 200)
        data = res_get.get_json()
        self.assertEqual(data["faculty_name"], "Test Faculty")

        # 3. Update Faculty name
        res_update = self.client.put("/api/faculties/F99", json={"faculty_name": "Updated Name"}, headers=self.headers_admin)
        self.assertEqual(res_update.status_code, 200)

        # Confirm update
        res_get_updated = self.client.get("/api/faculties/F99", headers=self.headers_hod)
        self.assertEqual(res_get_updated.get_json()["faculty_name"], "Updated Name")

        # 4. Delete Faculty
        res_delete = self.client.delete("/api/faculties/F99", headers=self.headers_admin)
        self.assertEqual(res_delete.status_code, 200)

    def test_dashboard_stats(self):
        res = self.client.get("/api/dashboard/stats", headers=self.headers_hod)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("faculty_count", data)
        self.assertIn("room_count", data)

    def test_validator_and_repair_endpoints(self):
        # Validate a small mock schedule payload
        mock_schedule = [
            {
                "run_id": 1, "section_id": "S1", "day_id": 1, "period_no": 1,
                "course_id": "CS101", "faculty_id": "F01", "room_no": "R101",
                "year": 2026, "semester": 1
            }
        ]
        
        # Validate route
        res_val = self.client.post("/api/scheduler/validate", json={"schedule": mock_schedule}, headers=self.headers_hod)
        self.assertEqual(res_val.status_code, 200)
        data_val = res_val.get_json()
        self.assertIn("is_valid", data_val)
        self.assertIn("errors", data_val)

        # Repair route
        res_rep = self.client.post("/api/scheduler/repair", json={"schedule": mock_schedule}, headers=self.headers_hod)
        self.assertEqual(res_rep.status_code, 200)
        data_rep = res_rep.get_json()
        self.assertIn("stats", data_rep)
        self.assertIn("repaired_schedule", data_rep)


if __name__ == "__main__":
    unittest.main()
