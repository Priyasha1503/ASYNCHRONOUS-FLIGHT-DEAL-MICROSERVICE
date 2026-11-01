"""Provider error taxonomy. `retryable` drives the retry policy: transient failures may be retried
with backoff; permanent ones (bad request, auth, unsupported route) never are."""


class ProviderError(Exception):
    code = "error"
    retryable = False

    def __init__(self, provider: str, message: str = "") -> None:
        super().__init__(f"{provider}: {message or self.code}")
        self.provider = provider


class ProviderTimeout(ProviderError):
    code = "timeout"
    retryable = True


class ProviderUnavailable(ProviderError):
    """Network error or 5xx."""

    code = "unavailable"
    retryable = True


class ProviderRateLimited(ProviderError):
    code = "rate_limited"
    retryable = True

    def __init__(
        self, provider: str, message: str = "", retry_after_s: float | None = None
    ) -> None:
        super().__init__(provider, message)
        self.retry_after_s = retry_after_s


class ProviderInvalidResponse(ProviderError):
    """The provider answered, but not with something we can trust (schema/validation failure)."""

    code = "invalid_response"


class ProviderAuthError(ProviderError):
    code = "auth"


class ProviderUnsupportedQuery(ProviderError):
    """This provider can't serve the query (route, cabin, passenger mix …). Not a failure."""

    code = "unsupported"
