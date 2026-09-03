"""Self-service, user-facing DRF views.

Phase 5 implements the views backing ``urls.py``'s routes (basePath ``/api/v1/users``) — see own
info, edit own profile/setting, browse others' public profiles — gated by ``IsProfileOwner``/
``IsPublicOrOwner`` from ``permissions.py``, built through ``serializers.build_serializer()``. No
endpoint here ever edits anyone else's data — there is no such route on this surface (this repo's
scope-boundary table).
"""
