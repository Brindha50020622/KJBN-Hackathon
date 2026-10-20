class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class DuplicateFileError(AppError):
    status_code = 409
    code = "DUPLICATE_FILE"


class FileTooLargeError(AppError):
    status_code = 413
    code = "FILE_TOO_LARGE"


class InvalidRequestError(AppError):
    status_code = 422
    code = "INVALID_REQUEST"


def error_body(code: str, message: str, request_id: str, details=None) -> dict:
    body = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        body["details"] = details
    return {"error": body}
