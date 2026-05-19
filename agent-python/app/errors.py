class AppError(Exception):
    pass


class ExternalServiceNotConfigured(AppError):
    pass


class ExternalServiceError(AppError):
    pass
