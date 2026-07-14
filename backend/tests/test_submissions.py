from __future__ import annotations

import pytest


@pytest.fixture
def admin_client(client):
    """Login as admin and return authenticated client."""
    resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admintestpassword",
    })
    assert resp.status_code == 200
    return client


@pytest.fixture
def user_client(client):
    """Register a normal user, login, return authenticated client."""
    client.post("/api/users/", json={
        "username": "student1",
        "password": "test123456",
    })
    resp = client.post("/api/auth/login", json={
        "username": "student1",
        "password": "test123456",
    })
    assert resp.status_code == 200
    return client


def _create_problem(client, problem_id: str = "sum") -> dict:
    resp = client.post("/api/problems/", json={
        "id": problem_id,
        "title": "A+B Problem",
        "description": "Sum two integers",
        "input_description": "a b",
        "output_description": "a+b",
        "testcases": [
            {"input": "1 2\n", "output": "3"},
            {"input": "-1 1\n", "output": "0"},
        ],
        "time_limit": 2.0,
        "memory_limit": 256,
        "samples": [],
        "constraints": "",
    })
    assert resp.status_code == 200, f"Create problem failed: {resp.json()}"
    return resp.json()


def _create_submission(client, code: str = "print(1+2)") -> dict:
    resp = client.post("/api/submissions/", json={
        "problem_id": "sum",
        "language": "python",
        "code": code,
    })
    assert resp.status_code == 200, f"Create submission failed: {resp.json()}"
    return resp.json()


# ============================================================
# Task 1: 评测列表查询
# ============================================================

class TestListSubmissions:
    """评测列表查询接口测试"""

    def test_list_submissions_requires_login(self, client):
        """未登录用户无法查看评测列表"""
        resp = client.get("/api/submissions/?user_id=admin")
        assert resp.status_code == 401

    def test_list_submissions_requires_filter(self, client):
        """普通用户不带 user_id 或 problem_id 时返回 400"""
        # Login as regular user
        client.post("/api/users/", json={
            "username": "normal_user", "password": "test123456",
        })
        client.post("/api/auth/login", json={
            "username": "normal_user", "password": "test123456",
        })
        resp = client.get("/api/submissions/")
        assert resp.status_code == 400

    def test_list_submissions_empty(self, admin_client):
        """刚重置后，评测列表为空"""
        resp = admin_client.get("/api/submissions/?user_id=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 0
        assert data["data"]["submissions"] == []

    def test_list_submissions_with_data(self, admin_client):
        """有评测记录时正常返回"""
        _create_problem(admin_client)
        _create_submission(admin_client)

        resp = admin_client.get("/api/submissions/?user_id=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 1
        assert len(data["data"]["submissions"]) == 1
        item = data["data"]["submissions"][0]
        assert item["submission_id"] == "sub_1"
        assert "status" in item

    def test_list_submissions_pagination(self, admin_client):
        """分页参数正确生效"""
        _create_problem(admin_client)
        for _ in range(3):
            admin_client.post("/api/submissions/", json={
                "problem_id": "sum", "language": "python", "code": "print(1+2)",
            })

        # Page 1 with size 2
        resp = admin_client.get("/api/submissions/?page=1&page_size=2&user_id=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 3
        assert len(data["data"]["submissions"]) == 2

        # Page 2 with size 2
        resp = admin_client.get("/api/submissions/?page=2&page_size=2&user_id=admin")
        data = resp.json()
        assert len(data["data"]["submissions"]) == 1

    def test_list_submissions_no_pagination(self, admin_client):
        """不带分页参数时返回全部"""
        _create_problem(admin_client)
        for _ in range(3):
            admin_client.post("/api/submissions/", json={
                "problem_id": "sum", "language": "python", "code": "print(1+2)",
            })

        resp = admin_client.get("/api/submissions/?user_id=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 3
        assert len(data["data"]["submissions"]) == 3

    def test_list_submissions_filter_by_problem(self, admin_client):
        """按题目筛选"""
        _create_problem(admin_client, "sum")
        _create_problem(admin_client, "diff")
        admin_client.post("/api/submissions/", json={
            "problem_id": "sum", "language": "python", "code": "print(1+2)",
        })
        admin_client.post("/api/submissions/", json={
            "problem_id": "diff", "language": "python", "code": "print(1-2)",
        })

        resp = admin_client.get("/api/submissions/?problem_id=sum")
        data = resp.json()
        assert data["data"]["total"] == 1

    def test_list_submissions_admin_sees_all(self, admin_client, client):
        """管理员不带 user_id 可以看到所有人的提交"""
        _create_problem(admin_client)
        _create_submission(admin_client, "print(1+2)")

        # Register and login as another user to create a submission
        client.post("/api/users/", json={
            "username": "student2", "password": "test123456",
        })
        client.post("/api/auth/login", json={
            "username": "student2", "password": "test123456",
        })
        _create_submission(client, "print(3+4)")

        # Log back in as admin
        admin_client.post("/api/auth/login", json={
            "username": "admin", "password": "admintestpassword",
        })

        # Admin sees all (no user_id filter)
        resp = admin_client.get("/api/submissions/?problem_id=sum")
        data = resp.json()
        assert data["data"]["total"] == 2

    def test_list_submissions_user_sees_only_own(self, admin_client, client):
        """普通用户不带 user_id 只能看到自己的提交"""
        _create_problem(admin_client)
        _create_submission(admin_client, "print(1+2)")

        # Another user only sees their own
        client.post("/api/users/", json={
            "username": "student3", "password": "test123456",
        })
        client.post("/api/auth/login", json={
            "username": "student3", "password": "test123456",
        })
        _create_submission(client, "print(3+4)")

        resp = client.get("/api/submissions/?problem_id=sum")
        data = resp.json()
        assert data["data"]["total"] == 1


# ============================================================
# Task 2: 单个评测详情
# ============================================================

class TestGetSubmissionDetail:
    """单个评测详情接口测试"""

    def test_detail_requires_login(self, client):
        """未登录无法查看详情"""
        resp = client.get("/api/submissions/sub_1")
        assert resp.status_code == 401

    def test_detail_not_found(self, admin_client):
        """不存在的提交返回404"""
        resp = admin_client.get("/api/submissions/nonexistent")
        assert resp.status_code == 404

    def test_detail_own_submission(self, admin_client):
        """查看自己的提交 - 返回 score 和 counts"""
        _create_problem(admin_client)
        _create_submission(admin_client, "print(1+2)")

        resp = admin_client.get("/api/submissions/sub_1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert "score" in data["data"]
        assert "counts" in data["data"]

    def test_detail_admin_can_view_any(self, admin_client):
        """管理员可以查看任何人的提交"""
        _create_problem(admin_client)
        # Register a user and create a submission as that user
        admin_client.post("/api/users/", json={
            "username": "student4", "password": "test123456",
        })
        resp = admin_client.post("/api/auth/login", json={
            "username": "student4", "password": "test123456",
        })
        assert resp.status_code == 200
        _create_submission(admin_client, "print(1+2)")

        # Login back as admin
        admin_client.post("/api/auth/login", json={
            "username": "admin", "password": "admintestpassword",
        })

        # Admin can view student's submission
        resp = admin_client.get("/api/submissions/sub_1")
        assert resp.status_code == 200

    def test_detail_other_user_cannot_view(self, admin_client, client):
        """非管理员无法查看别人的提交"""
        _create_problem(admin_client)
        _create_submission(admin_client, "print(1+2)")

        # Another user tries to view
        client.post("/api/users/", json={
            "username": "student5", "password": "test123456",
        })
        client.post("/api/auth/login", json={
            "username": "student5", "password": "test123456",
        })
        resp = client.get("/api/submissions/sub_1")
        assert resp.status_code == 403


# ============================================================
# Task 3: 重新评测
# ============================================================

class TestRejudge:
    """重新评测接口测试"""

    def test_rejudge_requires_admin(self, admin_client, client):
        """非管理员无法重新评测"""
        _create_problem(admin_client)
        _create_submission(admin_client, "print(1+2)")

        # Regular user tries to rejudge
        client.post("/api/users/", json={
            "username": "student6", "password": "test123456",
        })
        client.post("/api/auth/login", json={
            "username": "student6", "password": "test123456",
        })
        resp = client.put("/api/submissions/sub_1/rejudge")
        assert resp.status_code == 403

    def test_rejudge_not_found(self, admin_client):
        """不存在的提交返回404"""
        resp = admin_client.put("/api/submissions/nonexistent/rejudge")
        assert resp.status_code == 404

    def test_rejudge_success(self, admin_client):
        """重新评测触发成功"""
        _create_problem(admin_client)
        _create_submission(admin_client, "print(1+2)")

        resp = admin_client.put("/api/submissions/sub_1/rejudge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["msg"] == "rejudge started"
        assert data["data"]["submission_id"] == "sub_1"
        assert data["data"]["status"] == "pending"

    def test_rejudge_updates_submission(self, admin_client):
        """重新评测后提交数据被更新"""
        _create_problem(admin_client)
        _create_submission(admin_client, "print(1+2)")

        # Rejudge
        resp = admin_client.put("/api/submissions/sub_1/rejudge")
        assert resp.status_code == 200
        rejudge_data = resp.json()
        assert rejudge_data["data"]["submission_id"] == "sub_1"
        assert rejudge_data["data"]["status"] == "pending"

        # Submission still exists after rejudge
        resp = admin_client.get("/api/submissions/sub_1")
        assert resp.status_code == 200
        updated = resp.json()
        assert "score" in updated["data"]
