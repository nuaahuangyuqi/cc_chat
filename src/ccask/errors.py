class CCAskError(Exception):
    """An actionable error that may safely be shown to a client."""

    def __init__(self, message: str, code: str = "request_failed", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class ConnectionError(CCAskError):
    """The local CC Ask service or CC Switch proxy is unavailable."""
