class DomainError(Exception):
    """
    Base class for errors raised by the domain layer.
    """


class InvalidTransitionError(DomainError, ValueError):
    """
    Raised when a repair run is asked to move to a state that is not allowed.

    It subclasses ValueError so that existing callers that catch ValueError
    keep working unchanged.
    """


class RunNotFoundError(DomainError):
    """
    Raised when a repair run does not exist.
    """


class InvalidWebhookPayloadError(DomainError):
    """
    Raised when an incoming webhook payload cannot be understood.

    The integration layer raises this instead of an HTTP error, so it
    stays independent of the web framework. The API layer decides which
    status code to return.
    """
