"""Custom Jazzmin admin-dashboard views — e.g. the account-deletion review queue's changelist-
style page.

Phase 6 implements the views this app's ``admin.py`` registrations link out to (or embed via
``ModelAdmin.get_urls()``), distinct from ``views_admin.py``'s DRF admin API: this module renders
Django-admin-integrated HTML/Jazzmin pages, ``views_admin.py`` serves JSON. Both exist because
Phase 6 is titled "Admin API *and* Jazzmin admin" — two distinct surfaces, each with its own
file, rather than one file covering both by accident.
"""
