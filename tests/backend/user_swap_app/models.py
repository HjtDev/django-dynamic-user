"""A host-style ``User`` subclass only — see this module's package docstring (``apps.py``) for
what this proves."""

from __future__ import annotations

from django.db import models

from dynamic_user.managers import UserManager
from dynamic_user.models import AbstractDynamicUser


class User(AbstractDynamicUser):
    department = models.CharField(max_length=100, blank=True)

    objects = UserManager()
