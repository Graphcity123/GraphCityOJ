"""API client for OJ System backend.

All communication with the backend goes through this module.
Uses requests.Session for cookie-based authentication.
"""
from __future__ import annotations

import json
from typing import Any

import requests

API_BASE = "http://localhost:8000"


def get_session() -> requests.Session:
    """Get or create a requests.Session stored in st.session_state."""
    import streamlit as st
    if "api_session" not in st.session_state:
        st.session_state.api_session = requests.Session()
    return st.session_state.api_session


def _url(path: str) -> str:
    return API_BASE + path


def _api_call(method: str, path: str, **kwargs) -> requests.Response:
    """Make an API call with proper error handling for connection issues."""
    session = get_session()
    try:
        return session.request(method, _url(path), **kwargs)
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            "Cannot connect to backend. Is the server running on http://localhost:8000?"
        ) from e


def _handle_response(resp: requests.Response) -> dict[str, Any]:
    """Unwrap the ApiResponse envelope and raise on errors."""
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        resp.raise_for_status()
        return {}

    code = body.get("code", 500)
    if code != 200:
        msg = body.get("msg", body.get("detail", "Unknown error"))
        raise RuntimeError(msg)

    return body.get("data")


# ── Auth ──────────────────────────────────────────────────────


def register(username: str, password: str, email: str = "") -> dict[str, Any]:
    session = get_session()
    resp = _api_call("POST", "/api/users/", json={
        "username": username,
        "password": password,
    })
    if resp.status_code != 200:
        detail = resp.json().get("detail", "Registration failed")
        raise RuntimeError(detail)
    return _handle_response(resp)


def login(username: str, password: str) -> dict[str, Any]:
    session = get_session()
    resp = _api_call("POST", "/api/auth/login", json={
        "username": username,
        "password": password,
    })
    if resp.status_code != 200:
        detail = resp.json().get("detail", "Login failed")
        raise RuntimeError(detail)
    data = _handle_response(resp)
    return data


def logout() -> None:
    session = get_session()
    _api_call("POST", "/api/auth/logout")


# ── Problems ──────────────────────────────────────────────────


def list_problems(page: int = 1, page_size: int = 50) -> dict[str, Any]:
    session = get_session()
    resp = _api_call("GET", f"/api/problems/?page={page}&page_size={page_size}")
    return _handle_response(resp)


def get_problem(problem_id: str) -> dict[str, Any] | None:
    session = get_session()
    resp = _api_call("GET", f"/api/problems/{problem_id}")
    if resp.status_code == 404:
        return None
    return _handle_response(resp)


def create_problem(data: dict[str, Any]) -> dict[str, Any]:
    session = get_session()
    resp = _api_call("POST", "/api/problems/", json=data)
    if resp.status_code != 200:
        detail = resp.json().get("detail", "Create failed")
        raise RuntimeError(detail)
    return _handle_response(resp)


# ── Languages ─────────────────────────────────────────────────


def list_languages() -> list[dict[str, Any]]:
    session = get_session()
    resp = _api_call("GET", "/api/languages/")
    return _handle_response(resp) or []


# ── Judge ──────────────────────────────────────────────────────


def submit_judge(problem_id: str, language: str, code: str) -> dict[str, Any]:
    session = get_session()
    resp = _api_call("POST", "/api/submissions/", json={
        "problem_id": problem_id,
        "language": language,
        "code": code,
    })
    if resp.status_code != 200:
        detail = resp.json().get("detail", "Judge failed")
        raise RuntimeError(detail)
    return _handle_response(resp)


# ── Submissions ────────────────────────────────────────────────


def list_submissions(page: int = 1, page_size: int = 50, problem_id: str | None = None) -> dict[str, Any]:
    session = get_session()
    params = f"page={page}&page_size={page_size}"
    if problem_id:
        params += f"&problem_id={problem_id}"
    resp = _api_call("GET", f"/api/submissions/?{params}")
    return _handle_response(resp)


def get_submission(submission_id: str) -> dict[str, Any] | None:
    session = get_session()
    resp = _api_call("GET", f"/api/submissions/{submission_id}")
    if resp.status_code == 404:
        return None
    return _handle_response(resp)


# ── Admin ──────────────────────────────────────────────────────


def reset_system() -> dict[str, Any]:
    session = get_session()
    resp = _api_call("POST", "/api/reset/")
    return _handle_response(resp)


def export_data() -> dict[str, Any]:
    session = get_session()
    resp = _api_call("GET", "/api/export/")
    return _handle_response(resp)
