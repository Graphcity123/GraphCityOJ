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
            messages.success(request, f'欢迎，{user_data["username"]}！')
            return redirect('problem_list')
        messages.error(request, '用户名或密码错误。')
    return render(request, 'oj/auth/login.html')


def register_view(request):
    """Register page."""
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        if len(username) < 3 or len(password) < 6:
            messages.error(request,
                           '用户名需3-40字符，密码需6位以上。')
        else:
            result = api.register(request, username, password)
            if result is not None:
                messages.success(request, '注册成功！请登录。')
                return redirect('login')
    return render(request, 'oj/auth/register.html')


def logout_view(request):
    """Logout."""
    api.logout(request)
    request.session.flush()
    messages.success(request, '已登出。')
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
        messages.error(request, '题目未找到。')
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

    language = request.POST.get('language', 'cpp')
    uploaded = request.FILES.get('code_file')
    if uploaded:
        code = uploaded.read().decode('utf-8', errors='replace')
    else:
        code = request.POST.get('code', '')

    if not code.strip():
        messages.error(request, '代码不能为空。')
        return redirect('problem_detail', folder_id=folder_id)

    result = api.submit_judge(request, folder_id, language, code)
    if result is None:
        return redirect('problem_detail', folder_id=folder_id)

    sub_id = result.get('submission_id', '')
    messages.success(request, f'已提交！编号：{sub_id}')
    return redirect('submission_log', submission_id=sub_id)


@login_required
def submission_log(request, submission_id: str):
    """Judge result page (owner sees all, others see only score)."""
    user = request.session.get('user', {})
    log_data = api.get_submission_log(request, submission_id)
    sub = api.get_submission(request, submission_id) or {}
    is_owner = sub.get('user_id') == user.get('user_id')
    is_admin = user.get('role') == 'admin'
    can_view_full = is_owner or is_admin
    return render(request, 'oj/submissions/log.html', {
        'submission_id': submission_id,
        'log_data': log_data,
        'problem_id': sub.get('problem_id', ''),
        'code': sub.get('code', '') if can_view_full else '',
        'language': sub.get('language', 'python'),
        'can_view_full': can_view_full,
        'user': user,
    })


@login_required
def submission_list(request):
    """List submissions with optional filters."""
    user = request.session.get('user', {})
    is_admin = user.get('role') == 'admin'

    filters = {'page': request.GET.get('page', '1'),
               'page_size': request.GET.get('page_size', '50')}
    if request.GET.get('user_id'):
        filters['user_id'] = request.GET['user_id']
    if request.GET.get('problem_id'):
        filters['problem_id'] = request.GET['problem_id']
    if not is_admin and not filters.get('user_id') and not filters.get('problem_id'):
        filters['user_id'] = user.get('user_id', '')

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
        messages.error(request, '仅限管理员。')
        return redirect('submission_list')

    api.rejudge(request, submission_id)
    messages.success(request, f'重新评测已启动： {submission_id}.')
    return redirect('submission_log', submission_id=submission_id)


# ── Problem Upload ─────────────────────────────────────────────

@login_required
def problem_upload(request):
    """Upload a new problem via .md + .zip files (admin only)."""
    user = request.session.get('user', {})
    if user.get('role') != 'admin':
        messages.error(request, '仅限管理员上传题目。')
        return redirect('problem_list')

    if request.method == 'POST':
        md_file = request.FILES.get('problem_md')
        zip_file = request.FILES.get('testcases_zip')

        if not md_file or not zip_file:
            messages.error(request, '请上传 problem.md 和 testcases.zip 两个文件。')
        elif not md_file.name.endswith('.md'):
            messages.error(request, '题面文件必须是 .md 格式。')
        elif not zip_file.name.endswith('.zip'):
            messages.error(request, '测试数据必须是 .zip 格式。')
        else:
            result = api.upload_problem(request, md_file, zip_file)
            if result:
                pid = result.get('id', '')
                messages.success(request, f'题目创建成功！ID：{pid}')
                return redirect('problem_detail', folder_id=pid)
            messages.error(request, '上传失败，请检查文件格式是否正确。')

    return render(request, 'oj/problems/upload.html',
                  {'user': user})


@login_required
def problem_delete(request, folder_id: str):
    """Delete a problem (admin only)."""
    user = request.session.get('user', {})
    if user.get('role') != 'admin':
        messages.error(request, '仅限管理员删除题目。')
        return redirect('problem_list')

    if request.method == 'POST':
        api.delete_problem(request, folder_id)
        messages.success(request, f'题目 {folder_id} 已删除。')
        return redirect('problem_list')
    return redirect('problem_detail', folder_id=folder_id)


# ── Admin ─────────────────────────────────────────────────────



@admin_required
def admin_reset(request):
    """Reset the system."""
    if request.method == 'POST':
        api.reset_system(request)
        user_data = api.login(request, 'admin', 'admintestpassword')
        if user_data:
            request.session['user'] = user_data
        messages.success(request, '系统已重置。已以管理员身份登录。')
        return redirect('problem_list')
    return render(request, 'oj/admin/dashboard.html',
                  {'user': request.session.get('user', {})})


@admin_required
def admin_export(request):
    """Export all data as JSON download."""
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
    if request.method == 'POST':
        uploaded = request.FILES.get('data_file')
        if uploaded:
            api.import_data(request, uploaded.read())
            messages.success(request, '导入完成。')
            return redirect('problem_list')
        messages.error(request, '未上传文件。')
    return render(request, 'oj/admin/import.html',
                  {'user': request.session.get('user', {})})


@admin_required
def admin_users(request):
    """User management."""
    data = api.get_users(request)
    return render(request, 'oj/admin/users.html', {
        'users': data.get('users', []),
        'total': data.get('total', 0),
        'user': request.session.get('user', {}),
    })
