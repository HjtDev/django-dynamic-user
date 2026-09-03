"""Region-specific validator hooks — the ``PHONE_VALIDATORS``/``NAME_VALIDATORS`` settings made
real.

Phase 2 implements ``run_validators(setting_key: str, value: Any) -> None``: resolves the dotted
callable paths configured under ``DYNAMIC_USER[setting_key]`` lazily and caches them on first
use, calling each in turn and raising ``django.core.exceptions.ValidationError`` on the first
failure. Empty (the default for both keys) means no extra validation beyond Django's own field
checks — this module ships no opinionated phone/name format of its own; the hook is the feature,
not a validator (this repo's scope-boundary table).
"""
