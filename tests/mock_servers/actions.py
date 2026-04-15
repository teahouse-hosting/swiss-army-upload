"""
Mock server for actions-like OIDC
"""

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, JSONResponse
from starlette.routing import Route


async def key_xchange(request):
    # audience = request.query_params.get("audience")
    if "Authorization" not in request.headers:
        return PlainTextResponse("Need Authorization", 400)
    auth_kind, _, token = request.headers["Authorization"].partition(" ")
    if auth_kind.lower() != "bearer":
        return PlainTextResponse("Unknown Authorization", 400)

    if token == "owo":
        return JSONResponse({"value": "i-am-a-valid-key"}, 200)
    elif token == "uwu":
        return PlainTextResponse("Invalid auth", 403)
    else:
        return PlainTextResponse("Invalid auth", 403)


oidc = Starlette(
    debug=True,
    routes=[Route("/exchange-a-key", key_xchange, methods=["GET"])],
)
