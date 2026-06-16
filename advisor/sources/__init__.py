class SourceError(Exception):
    """Base for all source-client errors. Subclasses carry a `kind` string
    so the agent can branch on error category without parsing messages."""

    kind: str = "unknown"


class SourceNetworkError(SourceError):
    kind = "network"


class SourceHttpError(SourceError):
    kind = "http"

    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:200]}")
        self.status = status


class SourceParseError(SourceError):
    kind = "parse"
