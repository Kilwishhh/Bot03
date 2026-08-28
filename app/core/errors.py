"""Domain exceptions used across services and APIs."""

from __future__ import annotations


class ErmisError(Exception):
    """Base for all domain errors. Carries an HTTP status hint."""
    http_status: int = 500

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message}


class NotFoundError(ErmisError):
    http_status = 404


class ForbiddenError(ErmisError):
    http_status = 403


class UnauthorizedError(ErmisError):
    http_status = 401


class ValidationError(ErmisError):
    http_status = 400


class ConflictError(ErmisError):
    http_status = 409


class LifecycleError(ValidationError):
    """Raised when a strategy lifecycle transition is invalid."""


class LiveDeploymentError(ForbiddenError):
    """Raised when LIVE deployment is rejected for safety reasons."""


class EmergencyActiveError(ConflictError):
    """Raised when an action is blocked by an active emergency pause."""
