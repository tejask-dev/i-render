"""The one error shape every RoomProof response uses: {code, message, retryable}."""


class ApiError(Exception):
    def __init__(self, status_code, code, message, retryable=False):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable

    def body(self):
        return {"code": self.code, "message": self.message, "retryable": self.retryable}
