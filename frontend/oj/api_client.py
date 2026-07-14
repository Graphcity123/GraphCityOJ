"""HTTP client for FastAPI backend.

Uses requests.Session for cookie-based authentication.
Stores session in Django's session framework so cookies
persist across requests for the same browser session.
"""
from __future__ import annotations

import json
from typing import Any

import requests
from django.conf import settings
from django.http import HttpRequest


def _get_session(request: HttpRequest) -> requests.Session:
    """Get or create a requests.Session for the current Django session."""
    session = requests.Session()
    # Restore cookies from Django session if any
    cookies = request.session.get('_api_cookies', {})
    for name, value in cookies.items():
        session.cookies.set(name, value)
    return session


def _save_cookies(request: HttpRequest, session: requests.Session) -> None:
    """Persist cookies from the API session into Django's session."""
    request.session['_api_cookies'] = dict(session.cookies)
    request.session.modified = True


def _api_call(request: HttpRequest, method: str, path: str,
              **kwargs: Any) -> requests.Response:
    """Make an API call, persisting cookies between requests."""
    session = _get_session(request)
    url = settings.API_BASE_URL + path
    try:
        resp = session.request(method, url, **kwargs)
    except requests.exceptions.ConnectionError:
        from django.contrib import messages
        messages.error(request,
                       'Cannot connect to backend. Is the OJ server running?')
        resp = requests.Response()
        resp.status_code = 503
        return resp

    # Always persist cookies, even on error responses
    _save_cookies(request, session)
    return resp


def api_get(request: HttpRequest, path: str,
            **kwargs: Any) -> dict[str, Any] | None:
    resp = _api_call(request, 'GET', path, **kwargs)
    return _unwrap(request, resp)


def api_post(request: HttpRequest, path: str,
             **kwargs: Any) -> dict[str, Any] | None:
    resp = _api_call(request, 'POST', path, **kwargs)
    return _unwrap(request, resp)


def api_put(request: HttpRequest, path: str,
            **kwargs: Any) -> dict[str, Any] | None:
    resp = _api_call(request, 'PUT', path, **kwargs)
    return _unwrap(request, resp)


def api_delete(request: HttpRequest, path: str,
               **kwargs: Any) -> dict[str, Any] | None:
    resp = _api_call(request, 'DELETE', path, **kwargs)
    return _unwrap(request, resp)


def _unwrap(request: HttpRequest,
            resp: requests.Response) -> dict[str, Any] | None:
    status = resp.status_code
    if status == 503:
        return None

    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        body = {}

    code = body.get('code', status)
    if code != 200:
        msg = body.get('msg', body.get('detail', 'Unknown error'))
        from django.contrib import messages
        messages.error(request, msg)
        if code == 401:
            messages.warning(request, '会话已过期，请重新登录。')
        return None

    return body.get('data')


# ── Convenience wrappers ──────────────────────────────────────

def login(request: HttpRequest, username: str,
          password: str) -> dict[str, Any] | None:
    """Login and return user data."""
    return api_post(request, '/api/auth/login',
                    json={'username': username, 'password': password})


def logout(request: HttpRequest) -> None:
    """Logout from backend."""
    api_post(request, '/api/auth/logout')
    request.session.pop('_api_cookies', None)
    request.session.pop('user', None)
    request.session.modified = True


def register(request: HttpRequest, username: str,
             password: str) -> dict[str, Any] | None:
    """Register a new user."""
    return api_post(request, '/api/users/',
                    json={'username': username, 'password': password})


def list_problems(request: HttpRequest) -> list[dict[str, Any]]:
    """List all problems."""
    return api_get(request, '/api/problems/') or []


def get_problem(request: HttpRequest, problem_id: str) -> dict[str, Any] | None:
    """Get problem detail."""
    return api_get(request, f'/api/problems/{problem_id}')


def create_problem(request: HttpRequest,
                   data: dict[str, Any]) -> dict[str, Any] | None:
    """Create a problem."""
    return api_post(request, '/api/problems/', json=data)


def list_languages(request: HttpRequest) -> dict[str, Any]:
    """List supported languages."""
    return api_get(request, '/api/languages/') or {}


def submit_judge(request: HttpRequest, problem_id: str, language: str,
                 code: str) -> dict[str, Any] | None:
    """Submit code for judging."""
    return api_post(request, '/api/submissions/',
                    json={'problem_id': problem_id,
                          'language': language, 'code': code})


def list_submissions(request: HttpRequest, **filters: Any) -> dict[str, Any]:
    """List submissions with optional filters."""
    params = '&'.join(f'{k}={v}' for k, v in filters.items() if v)
    path = f'/api/submissions/?{params}' if params else '/api/submissions/'
    return api_get(request, path) or {}


def get_submission(request: HttpRequest,
                   submission_id: str) -> dict[str, Any] | None:
    """Get submission detail."""
    return api_get(request, f'/api/submissions/{submission_id}')


def get_submission_log(request: HttpRequest,
                       submission_id: str) -> dict[str, Any] | None:
    """Get detailed judge log."""
    return api_get(request, f'/api/submissions/{submission_id}/log')


def rejudge(request: HttpRequest, submission_id: str) -> dict[str, Any] | None:
    """Rejudge a submission (admin only)."""
    return api_put(request, f'/api/submissions/{submission_id}/rejudge')


def reset_system(request: HttpRequest) -> dict[str, Any] | None:
    """Reset the system (admin only)."""
    return api_post(request, '/api/reset/')


def export_data(request: HttpRequest) -> dict[str, Any] | None:
    """Export all data (admin only)."""
    return api_get(request, '/api/export/')


def import_data(request: HttpRequest,
                file_content: bytes) -> dict[str, Any] | None:
    """Import data from JSON (admin only)."""
    return api_post(request, '/api/import/',
                    files={'file': ('data.json', file_content,
                                    'application/json')})


def get_users(request: HttpRequest,
              page: int = 1, page_size: int = 100) -> dict[str, Any]:
    """List users (admin only)."""
    return api_get(request,
                   f'/api/users/?page={page}&page_size={page_size}') or {}


def get_user(request: HttpRequest, user_id: str) -> dict[str, Any] | None:
    """Get user info."""
    return api_get(request, f'/api/users/{user_id}')


def change_role(request: HttpRequest, user_id: str,
                role: str) -> dict[str, Any] | None:
    """Change user role (admin only)."""
    return api_put(request, f'/api/users/{user_id}/role',
                   json={'role': role})
