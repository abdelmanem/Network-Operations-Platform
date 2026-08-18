class NetBoxIntegrationError(Exception):
    """Raised for NetBox integration errors while preserving safe API contracts."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: object | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)
