class ProviderError(Exception):
    """A third-party call failed. Safe to show `public_message` to staff."""

    public_message = "The provider could not complete the request"


class NotConfigured(ProviderError):  # noqa: N818 (reads naturally at the raise site)
    """The real adapter has no official documentation or credentials yet
    (docs/INTEGRATIONS.md). Raised instead of guessing at an API."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"{provider} is not configured: see docs/INTEGRATIONS.md")
        self.provider = provider
        self.public_message = f"{provider} is not set up yet"


class InvalidSignature(ProviderError):  # noqa: N818
    """A webhook's signature did not verify."""


class RefundNotSupported(ProviderError):  # noqa: N818
    """The gateway cannot refund through its API; an admin refunds by hand."""
