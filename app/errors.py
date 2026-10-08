from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """ルーターから投げるアプリ固有のエラー。{"error": {"code", "message"}} 形式で返す。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # loc の先頭("body" / "query" など)は省き、"title: ..." のような形にまとめる
    messages = []
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"][1:])
        messages.append(f"{field}: {err['msg']}" if field else err["msg"])
    return error_response(422, "VALIDATION_ERROR", "; ".join(messages))


async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    # 存在しないパスや許可されていないメソッドなど、FastAPI 自体が返すエラーも同じ形式にする
    codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
    return error_response(
        exc.status_code, codes.get(exc.status_code, "HTTP_ERROR"), str(exc.detail)
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
