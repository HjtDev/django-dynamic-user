"""A host-style subclass of all three of ``dynamic_user``'s abstract bases, each with one extra
field — the fully-swapped leg (``tests/backend/settings_swapped.py``: ``AUTH_USER_MODEL``,
``DYNAMIC_USER_PROFILE_MODEL``, ``DYNAMIC_USER_SETTING_MODEL`` all point here).

None of these three declare ``Meta.swappable`` themselves — that attribute belongs to
``dynamic_user``'s own default implementation (``dynamic_user.models.User``/``Profile``/
``Setting``), marking "this is the model a setting can swap away from". A host's replacement model
is simply whatever the setting names; it needs no ``swappable`` attribute of its own, exactly like
any other project's custom ``AUTH_USER_MODEL``.
"""

from __future__ import annotations

from django.db import models

from dynamic_user.managers import UserManager
from dynamic_user.models import AbstractDynamicUser, AbstractProfile, AbstractSetting


class User(AbstractDynamicUser):
    department = models.CharField(max_length=100, blank=True)

    objects = UserManager()


class Profile(AbstractProfile):
    tagline = models.CharField(max_length=200, blank=True)


class Setting(AbstractSetting):
    theme = models.CharField(max_length=20, default="light")
