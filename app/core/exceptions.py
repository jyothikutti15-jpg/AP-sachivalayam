from fastapi import HTTPException, status


class SchemeNotFoundError(HTTPException):
    def __init__(self, scheme_code: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme '{scheme_code}' not found",
        )


class EmployeeNotRegisteredError(HTTPException):
    def __init__(self, phone: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Employee with phone {phone[-4:]} not registered",
        )


class GSWSConnectionError(Exception):
    """GSWS portal is unreachable."""

    def __init__(self, message: str = "GSWS portal is unreachable"):
        self.message = message
        super().__init__(self.message)


class LLMServiceError(Exception):
    """Error calling LLM service (Claude or BharatGen)."""

    def __init__(self, model: str, message: str):
        self.model = model
        self.message = message
        super().__init__(f"LLM error ({model}): {message}")


class VoiceProcessingError(Exception):
    """Error processing voice input."""

    def __init__(self, message: str = "Failed to process voice input"):
        self.message = message
        super().__init__(self.message)
