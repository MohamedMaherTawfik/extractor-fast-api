"""Stable errors exposed by the Social Inventory API."""


class SocialInventoryError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


def feature_disabled() -> SocialInventoryError:
    return SocialInventoryError("SOCIAL_FEATURE_DISABLED", "Social Inventory is disabled.", status_code=503)
