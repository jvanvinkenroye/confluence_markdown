"""Custom exceptions for the confluence-markdown package."""


class ConfluenceError(Exception):
    """Base exception for all Confluence-related errors."""

    pass


class AuthenticationError(ConfluenceError):
    """Raised when authentication fails."""

    pass


class ConfigurationError(ConfluenceError):
    """Raised when configuration is invalid or missing."""

    pass


class PageNotFoundError(ConfluenceError):
    """Raised when a Confluence page cannot be found."""

    pass


class APIError(ConfluenceError):
    """Raised when the Confluence API returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ContentParseError(ConfluenceError):
    """Raised when page content cannot be parsed."""

    pass


class EditorError(ConfluenceError):
    """Raised when the external editor fails."""

    pass
