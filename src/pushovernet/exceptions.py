class PushoverError(Exception):
    pass


class PushoverConfigError(PushoverError):
    pass


class PushoverAPIError(PushoverError):
    def __init__(self, status: int, errors: list[str], request_id: str):
        self.status = status
        self.errors = errors
        self.request_id = request_id
        super().__init__(f"API error (status={status}): {'; '.join(errors)}")


class PushoverRateLimitError(PushoverAPIError):
    def __init__(self, status: int, errors: list[str], request_id: str, reset_at: int):
        self.reset_at = reset_at
        super().__init__(status, errors, request_id)


class PushoverHTTPError(PushoverError):
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}" if message else f"HTTP {status_code}")
