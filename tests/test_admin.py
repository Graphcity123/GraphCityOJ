from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


@pytest.fixture
async def admin_client(client):
    await client.post('/api/reset/')
    resp = await client.post('/api/users/login', json={'username': 'admin', 'password': 'admintestpassword'})
    assert resp.status_code == 200
    return client


class TestSystemReset:

    async def test_reset_creates_admin(self, client):
        resp = await client.post('/api/reset/')
        assert resp.status_code == 200
        resp = await client.post('/api/users/login', json={'username': 'admin', 'password': 'admintestpassword'})
        assert resp.status_code == 200

    async def test_reset_languages(self, client):
        await client.post('/api/reset/')
        resp = await client.get('/api/languages/')
        assert resp.status_code == 200
        lang_ids = [lang['id'] for lang in resp.json()['data']]
        assert 'python' in lang_ids
        assert 'cpp' in lang_ids


class TestExportData:

    async def test_export_requires_admin(self, client):
        await client.post('/api/reset/')
        resp = await client.get('/api/export/')
        assert resp.status_code == 401

    async def test_export_structure(self, admin_client):
        resp = await admin_client.get('/api/export/')
        exported = resp.json()['data']
        assert 'users' in exported
        assert 'problems' in exported
        assert 'submissions' in exported

    async def test_export_submission_fields(self, admin_client):
        await admin_client.post('/api/languages/', json={'id': 'python', 'name': 'Python 3', 'extension': '.py', 'run_cmd': 'python3 {src}'})
        await admin_client.post('/api/problems/', json={'id': 'sum', 'title': 'A+B', 'testcases': [{'input': '1 2\n', 'output': '3'}], 'time_limit': 1.0, 'memory_limit': 128})
        await admin_client.post('/api/judge/', json={'problem_id': 'sum', 'language': 'python', 'code': 'print(1+2)'})
        resp = await admin_client.get('/api/export/')
        sub = resp.json()['data']['submissions'][0]
        assert 'submission_id' in sub
        assert 'created_at' in sub
        assert 'details' in sub
        assert 'counts' in sub

    async def test_export_password_hash(self, admin_client):
        resp = await admin_client.get('/api/export/')
        pw = resp.json()['data']['users'][0]['password']
        assert ':' in pw


class TestImportData:

    async def test_import_requires_admin(self, client):
        await client.post('/api/reset/')
        resp = await client.post('/api/import/', files={'file': ('data.json', json.dumps({'users': []}), 'application/json')})
        assert resp.status_code == 401

    async def test_import_rejects_non_json(self, admin_client):
        resp = await admin_client.post('/api/import/', files={'file': ('data.txt', b'hello', 'text/plain')})
        assert resp.status_code == 400

    async def test_import_users(self, admin_client):
        data = {'users': [{'user_id': 'usr_1', 'username': 'imported_user', 'role': 'user', 'password': 't:h', 'join_time': '2025-01-01', 'submit_count': 0, 'resolve_count': 0}]}
        resp = await admin_client.post('/api/import/', files={'file': ('data.json', json.dumps(data), 'application/json')})
        assert resp.status_code == 200
        resp = await admin_client.get('/api/users/list')
        assert 'imported_user' in [u['username'] for u in resp.json()['data']['users']]

    async def test_import_problems(self, admin_client):
        data = {'problems': [{'id': 'p1', 'title': 'Test', 'description': '', 'testcases': [], 'time_limit': 1.0, 'memory_limit': 128, 'public_cases': True}]}
        resp = await admin_client.post('/api/import/', files={'file': ('data.json', json.dumps(data), 'application/json')})
        assert resp.status_code == 200
        resp = await admin_client.get('/api/problems/p1')
        assert resp.json()['code'] == 200

    async def test_import_invalid_format(self, admin_client):
        resp = await admin_client.post('/api/import/', files={'file': ('data.json', json.dumps({'users': 'bad'}), 'application/json')})
        assert resp.status_code == 400

    async def test_import_missing_fields(self, admin_client):
        resp = await admin_client.post('/api/import/', files={'file': ('data.json', json.dumps({'users': [{'user_id': 'u1'}]}), 'application/json')})
        assert resp.status_code == 400

    async def test_import_conflict(self, admin_client):
        await admin_client.post('/api/users/register', json={'username': 'merge_test', 'password': 'old_password'})
        await admin_client.post('/api/users/login', json={'username': 'admin', 'password': 'admintestpassword'})
        resp = await admin_client.get('/api/users/list')
        uid = [u['user_id'] for u in resp.json()['data']['users'] if u['username'] == 'merge_test'][0]
        data = {'users': [{'user_id': uid, 'username': 'merge_test', 'role': 'teacher', 'password': 'n:h', 'join_time': '2025-06-01', 'submit_count': 99, 'resolve_count': 50}]}
        await admin_client.post('/api/import/', files={'file': ('data.json', json.dumps(data), 'application/json')})
        resp = await admin_client.get('/api/users/info/' + uid)
        assert resp.json()['data']['role'] == 'teacher'
        assert resp.json()['data']['submit_count'] == 99

