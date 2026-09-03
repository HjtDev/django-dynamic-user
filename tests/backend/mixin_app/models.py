"""``Widget`` composes every mixin in ``dynamic_user.mixins`` so this app's test suite can
exercise each one against a real, migrated model. ``SoftDeleteMixin``'s own docstring requires
the composing model to supply its own ``objects``/``all_objects`` managers — done below.
"""

from __future__ import annotations

from django.db import models

from dynamic_user.mixins import (
    AvatarMixin,
    HistoryMixin,
    LastSeenMixin,
    MetadataMixin,
    SoftDeleteMixin,
    TimestampMixin,
    VerificationMixin,
)


class WidgetManager(models.Manager["Widget"]):
    def get_queryset(self) -> models.QuerySet[Widget]:
        return super().get_queryset().filter(is_deleted=False)


class Widget(
    AvatarMixin,
    TimestampMixin,
    HistoryMixin,
    SoftDeleteMixin,
    VerificationMixin,
    LastSeenMixin,
    MetadataMixin,
):
    name = models.CharField(max_length=100)

    objects = WidgetManager()
    all_objects: models.Manager[Widget] = models.Manager()
