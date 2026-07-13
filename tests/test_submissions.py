from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.storage import reset_storage
from app.utils.rate_limiter import judge_rate_limiter


@pytest.fixture(autouse=True)
def reset_before():
    reset_storage()
    judge_rate_limiter.reset()


@pytest.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    """Login as admin and return authenticated client."""
    await client.post("/api/reset/")
    resp = await client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admintestpassword",
    })
    assert resp.status_code == 200
    return client


@pytest.fixture
async def user_client(client: AsyncClient) -> AsyncClient:
    """Register a normal user, login, return authenticated client."""
    await client.post("/api/reset/")
    await client.post("/api/users/", json={
        "username": "student1",
        "password": "test123456",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "student1",
        "password": "test123456",
    })
    assert resp.status_code == 200
    return client


async def _create_problem(client: AsyncClient, problem_id: str = "sum") -> dict:
    resp = await client.post("/api/problems/", json={
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


async def _create_submission(client: AsyncClient, code: str = "print(1+2)") -> dict:
    resp = await client.post("/api/submissions/", json={
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

    async def test_list_submissions_requires_login(self, client: AsyncClient):
        """未登录用户无法查看评测列表"""
        resp = await client.get("/api/submissions/?user_id=admin")
        assert resp.status_code == 401

    async def test_list_submissions_requires_filter(self, admin_client: AsyncClient):
        """不带 user_id 或 problem_id 时返回 400"""
        resp = await admin_client.get("/api/submissions/")
        assert resp.status_code == 400

    async def test_list_submissions_empty(self, admin_client: AsyncClient):
        """刚重置后，评测列表为空"""
        resp = await admin_client.get("/api/submissions/?user_id=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 0
        assert data["data"]["submissions"] == []

    async def test_list_submissions_with_data(self, admin_client: AsyncClient):
        """有评测记录时正常返回"""
        await _create_problem(admin_client)
        await _create_submission(admin_client)

        resp = await admin_client.get("/api/submissions/?user_id=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 1
        assert len(data["data"]["submissions"]) == 1
        item = data["data"]["submissions"][0]
        assert item["submission_id"] == "sub_1"
        assert "status" in item

    async def test_list_submissions_pagination(self, admin_client: AsyncClient):
        """分页参数正确生效"""
        await _create_problem(admin_client)
        for _ in range(3):
            await admin_client.post("/api/submissions/", json={
                "problem_id": "sum", "language": "python", "code": "print(1+2)",
            })

        # Page 1 with size 2
        resp = await admin_client.get("/api/submissions/?page=1&page_size=2&user_id=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 3
        assert len(data["data"]["submissions"]) == 2

        # Page 2 with size 2
        resp = await admin_client.get("/api/submissions/?page=2&page_size=2&user_id=admin")
        data = resp.json()
        assert len(data["data"]["submissions"]) == 1

    async def test_list_submissions_no_pagination(self, admin_client: AsyncClient):
        """不带分页参数时返回全部"""
        await _create_problem(admin_client)
        for _ in range(3):
            await admin_client.post("/api/submissions/", json={
                "problem_id": "sum", "language": "python", "code": "print(1+2)",
            })

        resp = await admin_client.get("/api/submissions/?user_id=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 3
        assert len(data["data"]["submissions"]) == 3

    async def test_list_submissions_filter_by_problem(self, admin_client: AsyncClient):
        """按题目筛选"""
        await _create_problem(admin_client, "sum")
        await _create_problem(admin_client, "diff")
        await admin_client.post("/api/submissions/", json={
            "problem_id": "sum", "language": "python", "code": "print(1+2)",
        })
        await admin_client.post("/api/submissions/", json={
            "problem_id": "diff", "language": "python", "code": "print(1-2)",
        })

        resp = await admin_client.get("/api/submissions/?problem_id=sum")
        data = resp.json()
        assert data["data"]["total"] == 1

    async def test_list_submissions_admin_sees_all(self, admin_client: AsyncClient, client: AsyncClient):
        """管理员不带 user_id 可以看到所有人的提交"""
        await _create_problem(admin_client)
        await _create_submission(admin_client, "print(1+2)")

        # Register and login as another user to create a submission
        await client.post("/api/users/", json={
            "username": "student2", "password": "test123456",
        })
        await client.post("/api/auth/login", json={
            "username": "student2", "password": "test123456",
        })
        await _create_submission(client, "print(3+4)")

        # Log back in as admin (client and admin_client share session)
        await admin_client.post("/api/auth/login", json={
            "username": "admin", "password": "admintestpassword",
        })

        # Admin sees all (no user_id filter)
        resp = await admin_client.get("/api/submissions/?problem_id=sum")
        data = resp.json()
        assert data["data"]["total"] == 2

    async def test_list_submissions_user_sees_only_own(self, admin_client: AsyncClient, client: AsyncClient):
        """普通用户不带 user_id 只能看到自己的提交"""
        await _create_problem(admin_client)
        await _create_submission(admin_client, "print(1+2)")

        # Another user only sees their own
        await client.post("/api/users/", json={
            "username": "student3", "password": "test123456",
        })
        await client.post("/api/auth/login", json={
            "username": "student3", "password": "test123456",
        })
        await _create_submission(client, "print(3+4)")

        resp = await client.get("/api/submissions/?problem_id=sum")
        data = resp.json()
        assert data["data"]["total"] == 1


# ============================================================
# Task 2: 单个评测详情
# ============================================================

class TestGetSubmissionDetail:
    """单个评测详情接口测试"""

    async def test_detail_requires_login(self, client: AsyncClient):
        """未登录无法查看详情"""
        resp = await client.get("/api/submissions/sub_1")
        assert resp.status_code == 401

    async def test_detail_not_found(self, admin_client: AsyncClient):
        """不存在的提交返回404"""
        resp = await admin_client.get("/api/submissions/nonexistent")
        assert resp.status_code == 404

    async def test_detail_own_submission(self, admin_client: AsyncClient):
        """查看自己的提交 - 返回 score 和 counts"""
        await _create_problem(admin_client)
        await _create_submission(admin_client, "print(1+2)")

        resp = await admin_client.get("/api/submissions/sub_1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert "score" in data["data"]
        assert "counts" in data["data"]

    async def test_detail_admin_can_view_any(self, admin_client: AsyncClient):
        """管理员可以查看任何人的提交"""
        await _create_problem(admin_client)
        # Register a user and create a submission as that user
        await admin_client.post("/api/users/", json={
            "username": "student4", "password": "test123456",
        })
        resp = await admin_client.post("/api/auth/login", json={
            "username": "student4", "password": "test123456",
        })
        assert resp.status_code == 200
        await _create_submission(admin_client, "print(1+2)")

        # Login back as admin
        await admin_client.post("/api/auth/login", json={
            "username": "admin", "password": "admintestpassword",
        })

        # Admin can view student's submission
        resp = await admin_client.get("/api/submissions/sub_1")
        assert resp.status_code == 200

    async def test_detail_other_user_cannot_view(self, admin_client: AsyncClient, client: AsyncClient):
        """非管理员无法查看别人的提交"""
        await _create_problem(admin_client)
        await _create_submission(admin_client, "print(1+2)")

        # Another user tries to view
        await client.post("/api/users/", json={
            "username": "student5", "password": "test123456",
        })
        await client.post("/api/auth/login", json={
            "username": "student5", "password": "test123456",
        })
        resp = await client.get("/api/submissions/sub_1")
        assert resp.status_code == 403


# ============================================================
# Task 3: 重新评测
# ============================================================

class TestRejudge:
    """重新评测接口测试"""

    async def test_rejudge_requires_admin(self, admin_client: AsyncClient, client: AsyncClient):
        """非管理员无法重新评测"""
        await _create_problem(admin_client)
        await _create_submission(admin_client, "print(1+2)")

        # Regular user tries to rejudge
        await client.post("/api/users/", json={
            "username": "student6", "password": "test123456",
        })
        await client.post("/api/auth/login", json={
            "username": "student6", "password": "test123456",
        })
        resp = await client.put("/api/submissions/sub_1/rejudge")
        assert resp.status_code == 403

    async def test_rejudge_not_found(self, admin_client: AsyncClient):
        """不存在的提交返回404"""
        resp = await admin_client.put("/api/submissions/nonexistent/rejudge")
        assert resp.status_code == 404

    async def test_rejudge_success(self, admin_client: AsyncClient):
        """重新评测触发成功"""
        await _create_problem(admin_client)
        await _create_submission(admin_client, "print(1+2)")

        resp = await admin_client.put("/api/submissions/sub_1/rejudge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["msg"] == "rejudge started"
        assert data["data"]["submission_id"] == "sub_1"
        assert data["data"]["status"] == "pending"

    async def test_rejudge_updates_submission(self, admin_client: AsyncClient):
        """重新评测后提交数据被更新"""
        await _create_problem(admin_client)
        await _create_submission(admin_client, "print(1+2)")

        # Rejudge
        resp = await admin_client.put("/api/submissions/sub_1/rejudge")
        assert resp.status_code == 200
        rejudge_data = resp.json()
        assert rejudge_data["data"]["submission_id"] == "sub_1"
        assert rejudge_data["data"]["status"] == "pending"

        # Submission still exists after rejudge
        resp = await admin_client.get("/api/submissions/sub_1")
        assert resp.status_code == 200
        updated = resp.json()
        assert "score" in updated["data"]
