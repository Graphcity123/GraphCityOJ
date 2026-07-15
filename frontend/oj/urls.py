"""OJ App URL Configuration."""
from django.urls import path
from oj import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Problems
    path('', views.problem_list, name='problem_list'),
    path('problem/upload/', views.problem_upload, name='problem_upload'),
    path('problem/<str:folder_id>/', views.problem_detail,
         name='problem_detail'),
    path('problem/<str:folder_id>/submit/', views.submission_create,
         name='submit'),
    path('problem/<str:folder_id>/delete/', views.problem_delete,
         name='problem_delete'),
    path('problem/<str:folder_id>/edit/', views.problem_edit,
         name='problem_edit'),
    path('problem/<str:folder_id>/testcases/', views.problem_testcases,
         name='problem_testcases'),

    # Submissions
    path('submissions/', views.submission_list, name='submission_list'),
    path('submission/<str:submission_id>/', views.submission_log,
         name='submission_result'),
    path('submission/<str:submission_id>/log/', views.submission_log,
         name='submission_log'),
    path('submission/<str:submission_id>/rejudge/', views.submission_rejudge,
         name='submission_rejudge'),

    # Users
    path('user/<str:user_id>/', views.user_profile, name='user_profile'),

    # Admin
    path('admin/reset/', views.admin_reset, name='admin_reset'),
    path('admin/export/', views.admin_export, name='admin_export'),
    path('admin/import/', views.admin_import, name='admin_import'),
    path('admin/users/', views.admin_users, name='admin_users'),
]
