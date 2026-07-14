"""GCOJ Frontend URL Configuration."""
from django.urls import include, path

urlpatterns = [
    path('', include('oj.urls')),
]
