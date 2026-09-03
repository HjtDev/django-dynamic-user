"""Model-layer coverage for the default (unswapped) settings module."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

from dynamic_user.models import AccountDeletionRequest
from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = pytest.mark.django_db


def test_create_user_sets_expected_defaults() -> None:
    user = get_user_model().objects.create_user(
        username="carol", email="carol@example.com", password="pw"
    )
    assert user.username == "carol"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.check_password("pw")


def test_create_user_requires_username() -> None:
    with pytest.raises(ValueError, match="username"):
        get_user_model().objects.create_user(username="", email="x@example.com", password="pw")


def test_create_superuser_sets_staff_and_superuser() -> None:
    user = get_user_model().objects.create_superuser(
        username="root", email="root@example.com", password="pw"
    )
    assert user.is_staff is True
    assert user.is_superuser is True


def test_create_superuser_rejects_explicit_is_staff_false() -> None:
    with pytest.raises(ValueError, match="is_staff"):
        get_user_model().objects.create_superuser(
            username="root2", email="root2@example.com", password="pw", is_staff=False
        )


def test_username_and_email_are_unique(user: object) -> None:
    with pytest.raises(IntegrityError):
        get_user_model().objects.create_user(
            username=user.username, email="different@example.com", password="pw"
        )


def test_profile_and_setting_resolve_to_default_models() -> None:
    assert get_profile_model()._meta.label_lower == "dynamic_user.profile"
    assert get_setting_model()._meta.label_lower == "dynamic_user.setting"


def test_profile_defaults(user: object) -> None:
    profile = get_profile_model().objects.create(user=user)
    assert profile.bio == ""
    assert profile.is_public is True


def test_setting_defaults(user: object) -> None:
    setting = get_setting_model().objects.create(user=user)
    assert setting.language == "en"
    assert setting.timezone == "UTC"
    assert setting.notifications_enabled is True


def test_profile_is_one_to_one(user: object) -> None:
    get_profile_model().objects.create(user=user)
    with pytest.raises(IntegrityError):
        get_profile_model().objects.create(user=user)


def test_account_deletion_request_defaults(user: object) -> None:
    request = AccountDeletionRequest.objects.create(user=user)
    assert request.status == AccountDeletionRequest.Status.PENDING
    assert request.reviewed_at is None
    assert request.reviewed_by is None


def test_account_deletion_request_reviewed_by_set_null_on_reviewer_delete(
    user: object, other_user: object
) -> None:
    request = AccountDeletionRequest.objects.create(user=user, reviewed_by=other_user)
    other_user.delete()
    request.refresh_from_db()
    assert request.reviewed_by is None
    # The request itself survives — only `user`'s deletion cascades, per its own FK.
    assert AccountDeletionRequest.objects.filter(pk=request.pk).exists()


def test_account_deletion_request_cascades_on_user_delete(user: object) -> None:
    request = AccountDeletionRequest.objects.create(user=user)
    user.delete()
    assert not AccountDeletionRequest.objects.filter(pk=request.pk).exists()


def test_no_concrete_model_imports_outside_resolution_and_settings_module() -> None:
    """The boundary rail (this repo's CLAUDE.md rule 1 / guide §0 item 1), asserted rather than
    only grepped by hand: dynamic_user.services/admin never import a concrete Profile/Setting."""
    import ast
    import pathlib

    package_dir = pathlib.Path(__import__("dynamic_user").__file__).parent
    offenders = []
    for path in package_dir.glob("*.py"):
        if path.name in {"models.py"}:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "models" in node.module:
                names = {alias.name for alias in node.names}
                concrete = names & {"User", "Profile", "Setting"}
                if concrete and "dynamic_user" in (node.module or ""):
                    offenders.append((path.name, concrete))
    assert offenders == []
