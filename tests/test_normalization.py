import pytest

from backend.core.enums import Platform
from backend.core.exceptions import NormalizationError
from backend.services.normalization import AccountNormalizer


@pytest.mark.parametrize(
    ("value", "expected_platform", "expected_username", "expected_url"),
    (
        (
            "@UserName",
            Platform.INSTAGRAM,
            "username",
            "https://www.instagram.com/username",
        ),
        (
            "username",
            Platform.INSTAGRAM,
            "username",
            "https://www.instagram.com/username",
        ),
        (
            "https://instagram.com/UserName/",
            Platform.INSTAGRAM,
            "username",
            "https://www.instagram.com/username",
        ),
        (
            "www.instagram.com/UserName",
            Platform.INSTAGRAM,
            "username",
            "https://www.instagram.com/username",
        ),
    ),
)
def test_instagram_identity_normalization(
    value,
    expected_platform,
    expected_username,
    expected_url,
) -> None:
    normalized = AccountNormalizer().normalize_account(
        platform=Platform.INSTAGRAM if not value.startswith(("http", "www")) else None,
        username=value,
    )

    assert normalized.platform is expected_platform
    assert normalized.username == expected_username
    assert normalized.profile_url == expected_url


def test_platform_url_mismatch_is_rejected() -> None:
    with pytest.raises(NormalizationError):
        AccountNormalizer().normalize_account(
            platform=Platform.TIKTOK,
            profile_url="https://instagram.com/example",
        )
