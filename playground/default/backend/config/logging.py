"""Minimal LOGGING dict builder — playground-only, not part of django-dynamic-user's own wiring.
Exists so dynamic_user's own logger calls (services.py, checks.py) are actually visible in
`docker compose logs backend-default`, and so appkit.request_id.RequestIDFilter is wired
somewhere (appkit.W005 fires otherwise).
"""

from __future__ import annotations

from typing import Any


def build_logging_config(*, debug: bool) -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "appkit.request_id.RequestIDFilter"},
        },
        "formatters": {
            "simple": {"format": "%(levelname)s [%(request_id)s] %(name)s: %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "filters": ["request_id"],
            },
        },
        "root": {"handlers": ["console"], "level": "INFO"},
        "loggers": {
            "dynamic_user": {
                "handlers": ["console"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        },
    }
