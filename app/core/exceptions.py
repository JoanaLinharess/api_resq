class AppError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    pass


class ConflictError(AppError):
    pass


class InvalidIdError(AppError):
    pass


class DatabaseError(AppError):
    pass
