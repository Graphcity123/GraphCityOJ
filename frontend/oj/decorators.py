"""View decorators for auth checks."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def login_required(view_func):
    """Redirect to login if not authenticated."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user'):
            messages.warning(request, 'Please log in first.')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Redirect to problem list if not admin."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.session.get('user', {})
        if user.get('role') != 'admin':
            messages.error(request, 'Admin access required.')
            return redirect('problem_list')
        return view_func(request, *args, **kwargs)
    return wrapper
