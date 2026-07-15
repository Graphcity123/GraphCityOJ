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

def _paginate(request, total: int, page_size: int) -> dict:
    """Build pagination context for templates."""
    page = int(request.GET.get('page', '1'))
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page = min(page, total_pages)
    page_range = list(range(1, total_pages + 1))

    # Preserve query params (except page) for pagination links
    query_parts = []
    for key in request.GET:
        if key != 'page':
            for val in request.GET.getlist(key):
                query_parts.append(f'{key}={val}')
    query_params = ('&' + '&'.join(query_parts)) if query_parts else ''
    query_dict = {k: v for k, v in request.GET.items() if k != 'page'}

    return {
        'page': page,
        'total_pages': total_pages,
        'page_range': page_range,
        'query_params': query_params,
        'query_dict': query_dict,
    }


@login_required
def problem_list(request):
    """List problems with pagination."""
    page_size = 20
    page = int(request.GET.get('page', '1'))
    data = api.list_problems(request, page=page, page_size=page_size)
    if isinstance(data, list):
        problems = data
        total = len(data)
    else:
        problems = data.get('problems', [])
        total = data.get('total', 0)

    user = request.session.get('user', {})
    ctx = _paginate(request, total, page_size)
    ctx.update({'problems': problems or [], 'user': user, 'total': total})
    return render(request, 'oj/problems/list.html', ctx)


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


def submission_log(request, submission_id: str):
    """Judge result page — anyone can see score, owner/admin see details."""
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
    """List submissions — all logged-in users can see all."""
    user = request.session.get('user', {})

    page_size = int(request.GET.get('page_size', '50'))
    page = int(request.GET.get('page', '1'))
    filters = {'page': page, 'page_size': page_size}
    if request.GET.get('user_id'):
        filters['user_id'] = request.GET['user_id']
    if request.GET.get('problem_id'):
        filters['problem_id'] = request.GET['problem_id']

    data = api.list_submissions(request, **filters)
    total = data.get('total', 0)

    ctx = _paginate(request, total, page_size)
    ctx.update({
        'submissions': data.get('submissions', []),
        'total': total,
        'user': user,
    })
    return render(request, 'oj/submissions/list.html', ctx)


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
def problem_edit(request, folder_id: str):
    """Edit problem metadata (admin only)."""
    user = request.session.get('user', {})
    if user.get('role') != 'admin':
        messages.error(request, '仅限管理员。')
        return redirect('problem_detail', folder_id=folder_id)

    problem = api.get_problem(request, folder_id)
    if problem is None:
        messages.error(request, '题目未找到。')
        return redirect('problem_list')

    if request.method == 'POST':
        data = {
            "id": folder_id,
            "title": request.POST.get('title', problem.get('title', '')),
            "description": request.POST.get('description',
                                            problem.get('description', '')),
            "input_description": problem.get('input_description', ''),
            "output_description": problem.get('output_description', ''),
            "constraints": problem.get('constraints', ''),
            "hint": problem.get('hint', ''),
            "time_limit": float(request.POST.get('time_limit',
                                                 problem.get('time_limit', 1.0))),
            "memory_limit": int(request.POST.get('memory_limit',
                                                 problem.get('memory_limit', 256))),
            "difficulty": request.POST.get('difficulty',
                                          problem.get('difficulty', 'easy')),
            "samples": problem.get('samples', []),
            "testcases": problem.get('testcases', []),
            "tags": problem.get('tags', []),
            "source": problem.get('source', ''),
            "author": problem.get('author', ''),
        }
        result = api.update_problem(request, folder_id, data)
        if result:
            messages.success(request, '题目已更新。')
            return redirect('problem_detail', folder_id=folder_id)
        messages.error(request, '更新失败。')

    return render(request, 'oj/problems/edit.html', {
        'problem': problem,
        'folder_id': folder_id,
        'user': user,
    })


@login_required
def problem_testcases(request, folder_id: str):
    """Manage test cases (admin only)."""
    user = request.session.get('user', {})
    if user.get('role') != 'admin':
        messages.error(request, '仅限管理员。')
        return redirect('problem_detail', folder_id=folder_id)

    problem = api.get_problem(request, folder_id)
    if problem is None:
        messages.error(request, '题目未找到。')
        return redirect('problem_list')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'add_tc':
            inp = request.POST.get('tc_input', '')
            out = request.POST.get('tc_output', '')
            in_file = request.FILES.get('in_file')
            out_file = request.FILES.get('out_file')
            if (inp or in_file) and (out or out_file):
                api.add_testcase(request, folder_id,
                                 test_input=inp, test_output=out,
                                 in_file=in_file, out_file=out_file)
                messages.success(request, '测试点已添加。')
            else:
                messages.error(request, '请提供输入和输出。')
            return redirect('problem_testcases', folder_id=folder_id)
        elif action == 'del_tc':
            n = request.POST.get('tc_n', '')
            if n.isdigit():
                api.delete_testcase(request, folder_id, int(n))
                messages.success(request, f'测试点 {n} 已删除。')
            return redirect('problem_testcases', folder_id=folder_id)
        elif action == 'reupload':
            zip_file = request.FILES.get('tc_zip')
            if zip_file:
                api.reupload_testcases(request, folder_id, zip_file)
                messages.success(request, '测试点已重新上传。')
            return redirect('problem_testcases', folder_id=folder_id)

    return render(request, 'oj/problems/testcases.html', {
        'problem': problem,
        'folder_id': folder_id,
        'user': user,
    })


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
        request.session.pop('_api_cookies', None)
        api.reset_system(request)
        request.session.pop('_api_cookies', None)
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
