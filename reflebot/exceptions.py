from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from .core.utils.exceptions import CoreException

async def core_exception_handler(request: Request, exc: CoreException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )

def apply_exceptions_handlers(app: FastAPI) -> FastAPI:
    """
    Применяем глобальные обработчики исключений.
    """
    app.exception_handler(CoreException)(core_exception_handler)
    
    return app