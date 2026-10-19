import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure the root logger for the application.

    This is intentionally minimal: the project does not yet depend on a
    structured logging backend, but the application still needs to be able
    to report misconfiguration and rejected requests.
    """

    global _configured

    if _configured:
        return

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        stream=sys.stderr,
    )

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.
    """

    return logging.getLogger(name)
