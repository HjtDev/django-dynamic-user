"""This app's public callable interface — the ONLY place a Profile/Setting update or an
account-deletion state transition happens.

Phase 3 implements ``ProfileService.update``, ``SettingService.update`` (each sending
``profile_updated``/nothing on a no-op write — see ``signals.py``), and ``DeletionService``'s
four transitions — ``request``/``review``/``finalize``/``cancel`` — plus the
``DeletionRequestAlreadyExists``/``InvalidDeletionState`` exceptions, exactly as
``docs/CONTRACT.md`` §4 specifies.

Every model reference in this module is resolved through ``resolution.py`` at call time, never a
concrete import — the same rule this repo's ``CLAUDE.md`` states for every other module.
"""
