"""Project-specific exception hierarchy."""


class EmyError(Exception):
    """Base exception for expected application errors."""


class ConfigurationError(EmyError):
    """Raised when external configuration cannot be loaded."""


class RuleLoadError(EmyError):
    """Raised when an external rules document is invalid or inaccessible."""


class RuleValidationError(EmyError):
    """Raised when a rule, rule set, condition, or lifecycle change is unsafe."""


class RuleDependencyCycleError(RuleValidationError):
    """Raised when an executable rule set contains a dependency cycle."""


class NotFoundError(EmyError):
    """Raised when a requested domain record does not exist."""


class ConflictError(EmyError):
    """Raised when a domain uniqueness rule would be violated."""


class NormalizationError(EmyError):
    """Raised when a platform identity cannot be normalized safely."""


class ImportValidationError(EmyError):
    """Raised when an import file or row is invalid."""


class ConnectorNotConfiguredError(EmyError):
    """Raised when no connector implementation is registered for a platform."""


class ConnectorUnavailableError(ConnectorNotConfiguredError):
    """Raised with an explicit availability state for an unavailable connector."""

    def __init__(self, platform: str, availability: str) -> None:
        self.platform = platform
        self.availability = availability
        super().__init__(f"{platform} connector is {availability}")


class ConnectorTemporaryError(EmyError):
    """Retryable temporary connector or network failure."""


class ConnectorRateLimitError(ConnectorTemporaryError):
    """Retryable rate-limit response with an optional server delay."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(message)


class ConnectorPermissionError(EmyError):
    """Terminal connector permission failure."""


class InvalidAccountError(EmyError):
    """Terminal invalid or unavailable platform-account failure."""


class ContentNormalizationError(EmyError):
    """Raised when connector content cannot satisfy the canonical schema."""


class AnalysisError(EmyError):
    """Base exception for expected content-analysis failures."""


class AnalysisRuleError(AnalysisError):
    """Raised when analysis rules or taxonomy are inconsistent."""


class AnalysisEngineError(AnalysisError):
    """Raised when an analysis provider cannot complete its work."""


class GenerationError(EmyError):
    """Base exception for expected generation failures with a stable code."""

    code = "GENERATION_FAILED"


class GenerationNotReadyError(GenerationError):
    code = "GENERATION_NOT_READY"


class ProviderUnavailableError(GenerationError):
    code = "PROVIDER_UNAVAILABLE"


class ModelCapabilityError(GenerationError):
    code = "MODEL_CAPABILITY_MISSING"


class PromptConflictError(GenerationError):
    code = "PROMPT_CONFLICT"


class ReferenceSafetyError(GenerationError):
    code = "RIGHTS_BLOCKED"


class InvalidGeneratedAssetError(GenerationError):
    code = "INVALID_OUTPUT"


class MaxRetriesExceededError(GenerationError):
    code = "MAX_RETRIES_EXCEEDED"


class SalesValidationError(EmyError):
    """A business transaction violates a Product/Sales invariant."""

    code = "SALES_VALIDATION_FAILED"


class MessagingValidationError(EmyError):
    """A conversation or outbound action violates messaging policy."""

    code = "MESSAGING_VALIDATION_FAILED"


class MessagingProviderError(EmyError):
    """A channel/model provider failed without exposing private details."""

    code = "MESSAGING_PROVIDER_FAILED"
