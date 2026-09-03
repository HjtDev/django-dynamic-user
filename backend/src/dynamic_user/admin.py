"""Jazzmin ``ModelAdmin`` registrations for ``User``/``Profile``/``Setting``/
``AccountDeletionRequest``.

Phase 6 registers plain ``django.contrib.admin.ModelAdmin`` classes — Jazzmin is **not** a
dependency of this package; a host's own installed Jazzmin renders them, and this package never
writes to ``JAZZMIN_SETTINGS`` itself (``APP-DESIGN.md`` §5; the README instead suggests
``JAZZMIN_SETTINGS["icons"]`` entries a host may copy in). Paired with ``admin_views.py``'s
custom dashboard views the way ``urls.py`` pairs with ``views.py``.

Gated the same way as the rest of the admin surface: ``appkit``-style admin posture,
``IsDynamicUserAdmin``-equivalent access at the Django-admin layer (``is_staff`` by default,
``is_superuser`` when ``DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]`` is ``True``), with the
privilege-escalation guard never relaxed by that switch.
"""
