"""
Mock server for counter.teahouse.cafe
"""

import contextlib
import typing as T

from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route


SESSION_COOKIE = "pytest_user_status"


@contextlib.asynccontextmanager
async def get_body(request) -> T.AsyncIterator[dict]:
    if request.headers.get("Content-Type") == "application/json":
        yield await request.json()
    else:
        async with request.form() as form:
            yield form


def get_auth(request) -> dict | None:
    if SESSION_COOKIE in request.cookies:
        return {"email": request.cookies["SESSION_COOKIE"]}
    else:
        return None


async def login(request):
    async with get_body(request) as input:
        if input.get("email", "").endswith("@valid.test"):
            resp = JSONResponse("okay!")
            resp.set_cookie(SESSION_COOKIE, input["email"])
            return resp
        else:
            resp = JSONResponse("no", status_code=400)
            resp.delete_cookie(SESSION_COOKIE)
            return resp


async def user_info(request):
    if get_auth(request):
        return await whoami(request)
    else:
        return RedirectResponse(url="/user/login/")


async def whoami(request):
    user = get_auth(request)
    if user is None:
        return JSONResponse(
            {"type": "anonymous", "is_authenticated": False, "name": ""}
        )
    else:
        return JSONResponse(
            {"type": "regular", "is_authenticated": True, "name": user["email"]}
        )
    # JSONResponse({"type":"oidc","is_authenticated":True,"name":...})


async def get_s3_config(request):
    user = get_auth(request)
    if user is None:
        return JSONResponse("no", status_code=403)
    else:
        async with get_body(request) as input:
            if "domain" not in input:
                return JSONResponse("domain plz", status_code=400)

            return JSONResponse(
                {
                    "AWS_ACCESS_KEY_ID": "TODO",
                    "AWS_ENDPOINT_URL_S3": "http://objects.test",
                    "AWS_REGION": "auto",
                    "AWS_SECRET_ACCESS_KEY": "TODO",
                    # 'AWS_SESSION_TOKEN': ...,
                    "BUCKET_NAME": input["domain"],
                }
            )


app = Starlette(
    debug=True,
    routes=[
        Route("/auth/login/", login, methods=["POST"]),
        Route("/auth/whoami/", whoami, methods=["GET"]),
        Route("/upload/get-s3-config", get_s3_config, methods=["POST"]),
        Route("/user/", user_info, methods=["GET"]),
    ],
)
