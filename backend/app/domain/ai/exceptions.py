from typing import Optional


class LLMProviderError(Exception):
    """Base exception for all LLM provider failures."""

    def __init__(
        self,
        message: str,
        provider_id: str = "unknown",
        model_id: Optional[str] = None,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
        raw_detail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider_id = provider_id
        self.model_id = model_id
        self.status_code = status_code
        self.retry_after = retry_after
        self.raw_detail = raw_detail

    def __str__(self) -> str:
        parts = [f"[{self.provider_id}] {self.message}"]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        if self.retry_after is not None:
            parts.append(f"(Retry-After: {self.retry_after}s)")
        return " ".join(parts)


class LLMProviderAuthError(LLMProviderError):
    """Raised when provider credentials are missing, invalid, or forbidden (HTTP 401 / 403)."""
    pass


class LLMProviderRateLimitError(LLMProviderError):
    """Raised when rate limits, token quotas, or concurrency limits are exceeded (HTTP 429)."""
    pass


class LLMProviderTimeoutError(LLMProviderError):
    """Raised when inference or connection times out."""
    pass


class LLMProviderUnavailableError(LLMProviderError):
    """Raised when upstream provider service is unreachable or returning server errors (HTTP 500, 502, 503, 504, or network drops)."""
    pass


class LLMProviderBadRequestError(LLMProviderError):
    """Raised when prompt or parameters are rejected (HTTP 400 / 404 / 422, context window overflow)."""
    pass
