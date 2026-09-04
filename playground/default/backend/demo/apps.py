"""Throwaway host app — carries no models of its own on the default host (unlike the subclassed
host's `core`, which subclasses dynamic_user's three models). Its only job is to be the home for
`manage.py seed_users`.
"""

from django.apps import AppConfig


class DemoConfig(AppConfig):
    name = "demo"
    default_auto_field = "django.db.models.BigAutoField"
