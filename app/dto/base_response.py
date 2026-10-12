from typing import Any
from typing import Optional
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar('T')

class BaseResponse(BaseModel):
    is_success : bool 
    code : int

    def to_response(self):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=self.code, content=self.model_dump())

class SuccessResponse(BaseResponse, Generic[T]):
    """
    Response model standar success
    """
    message : str
    data : Optional[T] = None

class ErrorResponse(BaseResponse):
    """
    Response model standar error
    """
    message : str
    errors : Optional[Any] = None
