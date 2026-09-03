"""``Profile``/``Setting`` subclasses only — this app's own ``User`` is never swapped; see this
module's package docstring (``apps.py``) for what this proves."""

from __future__ import annotations

from django.db import models

from dynamic_user.models import AbstractProfile, AbstractSetting


class Profile(AbstractProfile):
    tagline = models.CharField(max_length=200, blank=True)


class Setting(AbstractSetting):
    theme = models.CharField(max_length=20, default="light")
