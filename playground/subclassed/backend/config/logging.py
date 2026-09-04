"""Minimal LOGGING dict builder — playground-only, not part of django-dynamic-user's own wiring.
Mirrors ../../default/backend/config/logging.py exactly; kept as a separate copy per host
(these two hosts otherwise share zero Python modules) rather than a shared playground-level
package, matching the "deliberate near-duplicates, not a shared package" convention this
playground's own README states for the frontend half too.
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
            "core": {
                "handlers": ["console"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
            "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        },
    }
