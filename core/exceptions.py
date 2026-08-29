"""Custom exceptions for the Soy Grandez Engine orchestration system."""


class OrchestratorException(Exception):
    """Base exception for orchestrator-related errors."""
    pass


class ScraperException(OrchestratorException):
    """Exception raised when scraper operations fail."""
    pass


class OTPException(OrchestratorException):
    """Exception raised when OTP operations fail."""
    pass


class APIException(OrchestratorException):
    """Exception raised when API operations fail."""
    pass


class DatabaseException(OrchestratorException):
    """Exception raised when database operations fail."""
    pass


class CAPTCHAException(ScraperException):
    """Exception raised when CAPTCHA solving fails."""
    pass


class AuthenticationException(ScraperException):
    """Exception raised when authentication fails."""
    pass


class TimeoutException(OrchestratorException):
    """Exception raised when operations timeout."""
    pass


class RetryableException(OrchestratorException):
    """Base exception for errors that can be retried."""
    pass


class NonRetryableException(OrchestratorException):
    """Base exception for errors that should not be retried."""
    pass
