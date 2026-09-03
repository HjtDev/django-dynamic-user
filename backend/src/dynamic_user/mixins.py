"""Composable abstract-model mixin library.

Phase 2 implements one composable abstract model per mixin, each documenting exactly which
fields it adds and any requirement it places on the composing model (``docs/CONTRACT.md`` §1):

* ``AvatarMixin`` — an avatar ``ImageField``, behind the ``avatar`` extra at runtime.
* ``TimestampMixin`` — ``created_at``/``updated_at``. No ``Meta`` requirement on the composing
  model.
* ``HistoryMixin`` (+ concrete ``ChangeLogEntry``) — a generic-relation change log, the one
  place this package uses ``django.contrib.contenttypes`` (a ships-with-Django exception, not an
  app-package boundary concern per this repo's ``CLAUDE.md`` rule 4).
* ``SoftDeleteMixin`` — a soft-delete flag and manager swap.
* ``VerificationMixin`` — a verified/unverified flag and timestamp.
* ``LastSeenMixin`` — ``last_seen_at``, updated no more often than
  ``DYNAMIC_USER["LAST_SEEN_UPDATE_SECONDS"]`` by a host-wired hook (not a view this package
  ships).
* ``MetadataMixin`` — a ``JSONField`` escape hatch for host-specific, unstructured data that
  doesn't warrant a real column. Never read or written by this package's own views/serializers
  by default — a host opts a field allowlist into it explicitly.
"""
