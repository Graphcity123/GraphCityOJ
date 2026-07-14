from __future__ import annotations

import json

import pytest


@pytest.fixture
def admin_client(client):
    """Login as admin and return authenticated client. Admin exists from app lifespan."""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admintestpassword"})
    assert resp.status_code == 200
    # Reset to get clean state
    client.post("/api/reset/")
    # Re-login after reset clears session
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admintestpassword"})
    assert resp.status_code == 200
    return client


class TestSystemReset:

    def test_reset_creates_admin(self, client):
        """Admin can reset and re-login after."""
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admintestpassword"})
        assert resp.status_code == 200
        resp = client.post("/api/reset/")
        assert resp.status_code == 200
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admintestpassword"})
        assert resp.status_code == 200

    def test_reset_languages(self, client):
        """After reset, languages are cleared; can be re-registered."""
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admintestpassword"})
        assert resp.status_code == 200
        client.post("/api/reset/")
        # After reset, no languages exist
        resp = client.get("/api/languages/")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == []
        # Re-register after reset
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admintestpassword"})
        assert resp.status_code == 200
        client.post("/api/languages/", json={
            "name": "python", "file_ext": ".py", "run_cmd": "python3 {src}",
        })
        resp = client.get("/api/languages/")
        assert "python" in resp.json()["data"]["name"]


class TestExportData:

    def test_export_requires_admin(self, client):
        """Unauthenticated export returns 401."""
        resp = client.get("/api/export/")
        assert resp.status_code == 401

    def test_export_structure(self, admin_client):
        resp = admin_client.get("/api/export/")
        exported = resp.json()["data"]
        assert "users" in exported
        assert "problems" in exported
        assert "submissions" in exported

    def test_export_submission_fields(self, admin_client):
        admin_client.post("/api/languages/", json={
            "name": "python", "file_ext": ".py", "run_cmd": "python3 {src}",
        })
        admin_client.post("/api/problems/", json={
            "id": "sum", "title": "A+B",
            "description": "Add two numbers",
            "input_description": "Two numbers",
            "output_description": "Sum",
            "constraints": "None",
            "samples": [],
            "testcases": [{"input": "1 2\n", "output": "3"}],
            "time_limit": 1.0, "memory_limit": 128,
        })
        admin_client.post("/api/submissions/", json={
            "problem_id": "sum", "language": "python", "code": "print(1+2)",
        })
        resp = admin_client.get("/api/export/")
        sub = resp.json()["data"]["submissions"][0]
        assert "submission_id" in sub
        assert "details" in sub
        assert "counts" in sub

    def test_export_password_hash(self, admin_client):
        resp = admin_client.get("/api/export/")
        pw = resp.json()["data"]["users"][0]["password"]
        assert ":" in pw


class TestImportData:

    def test_import_requires_admin(self, client):
        """Unauthenticated import returns 401."""
        resp = client.post("/api/import/", files={
            "file": ("data.json", json.dumps({"users": []}), "application/json"),
        })
        assert resp.status_code == 401

    def test_import_rejects_non_json(self, admin_client):
        resp = admin_client.post("/api/import/", files={
            "file": ("data.txt", b"hello", "text/plain"),
        })
        assert resp.status_code == 400

    def test_import_users(self, admin_client):
        data = {"users": [{
            "user_id": "usr_1", "username": "imported_user", "role": "user",
            "password": "t:h", "join_time": "2025-01-01",
            "submit_count": 0, "resolve_count": 0,
        }]}
        resp = admin_client.post("/api/import/", files={
            "file": ("data.json", json.dumps(data), "application/json"),
        })
        assert resp.status_code == 200
        resp = admin_client.get("/api/users/?page=1&page_size=100")
        usernames = [u["username"] for u in resp.json()["data"]["users"]]
        assert "imported_user" in usernames

    def test_import_problems(self, admin_client):
        data = {"problems": [{
            "id": "p1", "title": "Test", "description": "",
            "input_description": "", "output_description": "",
            "constraints": "", "samples": [],
            "testcases": [], "time_limit": 1.0, "memory_limit": 128,
            "public_cases": True,
        }]}
        resp = admin_client.post("/api/import/", files={
            "file": ("data.json", json.dumps(data), "application/json"),
        })
        assert resp.status_code == 200
        resp = admin_client.get("/api/problems/p1")
        assert resp.json()["code"] == 200

    def test_import_invalid_format(self, admin_client):
        resp = admin_client.post("/api/import/", files={
            "file": ("data.json", json.dumps({"users": "bad"}), "application/json"),
        })
        assert resp.status_code == 400

    def test_import_missing_fields(self, admin_client):
        resp = admin_client.post("/api/import/", files={
            "file": ("data.json", json.dumps({"users": [{"user_id": "u1"}]}), "application/json"),
        })
        assert resp.status_code == 400

    def test_import_conflict(self, admin_client):
        admin_client.post("/api/users/", json={
            "username": "merge_test", "password": "old_password",
        })
        admin_client.post("/api/auth/login", json={
            "username": "admin", "password": "admintestpassword",
        })
        resp = admin_client.get("/api/users/?page=1&page_size=100")
        uid = [u["user_id"] for u in resp.json()["data"]["users"]
               if u["username"] == "merge_test"][0]
        data = {"users": [{
            "user_id": uid, "username": "merge_test", "role": "teacher",
            "password": "n:h", "join_time": "2025-06-01",
            "submit_count": 99, "resolve_count": 50,
        }]}
        admin_client.post("/api/import/", files={
            "file": ("data.json", json.dumps(data), "application/json"),
        })
        resp = admin_client.get(f"/api/users/{uid}")
        assert resp.json()["data"]["role"] == "teacher"
        assert resp.json()["data"]["submit_count"] == 99
