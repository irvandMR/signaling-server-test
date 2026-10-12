from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.dto.base_response import ErrorResponse

class AppException(Exception):
    def __init__(self, status_code: int, message: str, errors=None):
        self.status_code = status_code
        self.message = message
        self.errors = errors

def setup_exception_handlers(app: FastAPI):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return ErrorResponse(is_success=False, code=exc.status_code, message=exc.message, errors=exc.errors).to_response()

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return ErrorResponse(is_success=False, code=exc.status_code, message=str(exc.detail)).to_response()

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return ErrorResponse(is_success=False, code=422, message="Validasi gagal", errors=exc.errors()).to_response()