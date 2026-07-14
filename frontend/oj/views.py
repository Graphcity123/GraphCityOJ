"""GCOJ Frontend Views.

All views are function-based (following graphcity_blog pattern).
They call the FastAPI backend via oj.api_client and render Django templates.
"""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render

from oj import api_client as api
from oj.decorators import admin_required, login_required


# ── Auth ──────────────────────────────────────────────────────

def login_view(request):
    """Login page."""
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user_data = api.login(request, username, password)
        if user_data:
            request.session['user'] = user_data
            messages.success(request, f'Welcome, {user_data["username"]}!')
            return redirect('problem_list')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'oj/auth/login.html')


def register_view(request):
    """Register page."""
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        if len(username) < 3 or len(password) < 6:
            messages.error(request,
                           'Username must be 3+ chars, password 6+ chars.')
        else:
            result = api.register(request, username, password)
            if result is not None:
                messages.success(request, 'Registered! Please log in.')
                return redirect('login')
    return render(request, 'oj/auth/register.html')


def logout_view(request):
    """Logout."""
    api.logout(request)
    request.session.flush()
    messages.success(request, 'Logged out.')
    return redirect('login')


# ── Problems ──────────────────────────────────────────────────

@login_required
def problem_list(request):
    """List all problems."""
    problems = api.list_problems(request)
    user = request.session.get('user', {})
    return render(request, 'oj/problems/list.html', {
        'problems': problems or [],
        'user': user,
    })


@login_required
def problem_detail(request, folder_id: str):
    """Problem detail + submission form."""
    problem = api.get_problem(request, folder_id)
    languages = api.list_languages(request)
    user = request.session.get('user', {})
    if problem is None:
        messages.error(request, 'Problem not found.')
        return redirect('problem_list')
    return render(request, 'oj/problems/detail.html', {
        'problem': problem,
        'languages': languages.get('name', []),
        'folder_id': folder_id,
        'user': user,
    })


# ── Submissions ───────────────────────────────────────────────

@login_required
def submission_create(request, folder_id: str):
    """Submit code for judging."""
    if request.method != 'POST':
        return redirect('problem_detail', folder_id=folder_id)

    code = request.POST.get('code', '')
    language = request.POST.get('language', 'python')

    if not code.strip():
        messages.error(request, 'Code cannot be empty.')
        return redirect('problem_detail', folder_id=folder_id)

    result = api.submit_judge(request, folder_id, language, code)
    if result is None:
        return redirect('problem_detail', folder_id=folder_id)

    sub_id = result.get('submission_id', '')
    messages.success(request, f'Submitted! ID: {sub_id}')
    return redirect('submission_result', submission_id=sub_id)


@login_required
def submission_result(request, submission_id: str):
    """Show submission result with polling."""
    user = request.session.get('user', {})
    log_data = api.get_submission_log(request, submission_id)
    return render(request, 'oj/submissions/result.html', {
        'submission_id': submission_id,
        'log_data': log_data,
        'user': user,
    })


@login_required
def submission_log(request, submission_id: str):
    """Detailed judge log."""
    user = request.session.get('user', {})
    log_data = api.get_submission_log(request, submission_id)
    return render(request, 'oj/submissions/log.html', {
        'submission_id': submission_id,
        'log_data': log_data,
        'user': user,
    })


@login_required
def submission_list(request):
    """List submissions with filters."""
    user = request.session.get('user', {})
    is_admin = user.get('role') == 'admin'

    filters = {'page': request.GET.get('page', '1'),
               'page_size': request.GET.get('page_size', '50')}
    if not is_admin:
        filters['user_id'] = user.get('user_id', '')
    else:
        if request.GET.get('user_id'):
            filters['user_id'] = request.GET['user_id']
        if request.GET.get('problem_id'):
            filters['problem_id'] = request.GET['problem_id']

    data = api.list_submissions(request, **filters)
    return render(request, 'oj/submissions/list.html', {
        'submissions': data.get('submissions', []),
        'total': data.get('total', 0),
        'is_admin': is_admin,
        'user': user,
    })


@login_required
def submission_rejudge(request, submission_id: str):
    """Rejudge a submission (admin only)."""
    user = request.session.get('user', {})
    if user.get('role') != 'admin':
        messages.error(request, 'Admin only.')
        return redirect('submission_list')

    api.rejudge(request, submission_id)
    messages.success(request, f'Rejudge started for {submission_id}.')
    return redirect('submission_result', submission_id=submission_id)


# ── Admin ─────────────────────────────────────────────────────



@admin_required
def admin_reset(request):
    """Reset the system."""
    if not _check_admin(request):
        return redirect('problem_list')
    if request.method == 'POST':
        api.reset_system(request)
        user_data = api.login(request, 'admin', 'admintestpassword')
        if user_data:
            request.session['user'] = user_data
        messages.success(request, 'System reset. Logged in as admin.')
        return redirect('problem_list')
    return render(request, 'oj/admin/dashboard.html',
                  {'user': request.session.get('user', {})})


@admin_required
def admin_export(request):
    """Export all data as JSON download."""
    if not _check_admin(request):
        return redirect('problem_list')
    data = api.export_data(request)
    if data is None:
        return redirect('problem_list')
    import json as _json
    response = render(request, 'oj/admin/export.html',
                      {'data_json': _json.dumps(data, indent=2,
                                                ensure_ascii=False)})
    return response


@admin_required
def admin_import(request):
    """Import data from JSON upload."""
    if not _check_admin(request):
        return redirect('problem_list')
    if request.method == 'POST':
        uploaded = request.FILES.get('data_file')
        if uploaded:
            api.import_data(request, uploaded.read())
            messages.success(request, 'Import completed.')
            return redirect('problem_list')
        messages.error(request, 'No file uploaded.')
    return render(request, 'oj/admin/import.html',
                  {'user': request.session.get('user', {})})


@admin_required
def admin_users(request):
    """User management."""
    if not _check_admin(request):
        return redirect('problem_list')
    data = api.get_users(request)
    return render(request, 'oj/admin/users.html', {
        'users': data.get('users', []),
        'total': data.get('total', 0),
        'user': request.session.get('user', {}),
    })
