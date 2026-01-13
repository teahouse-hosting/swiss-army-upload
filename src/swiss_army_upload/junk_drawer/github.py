import os
import typing

import httpx


def github_oidc(
    audience: str = "",
) -> typing.Generator[httpx.Request, httpx.Response, str | None]:
    """
    A mixin for doing GitHub Actions OIDC in httpx auth.

    Inside your auth class, do:

        token = yield from github_oidc()

    and if $GITHUB_TOKEN is set, it'll do the thing.

    You must set `requires_response_body` on your httpx.Auth.

    Return:
        (str): The OIDC token issued by GitHub
        (None): This is not a GitHub environment

    Raises:
        httpx.HTTPStatusError: An unexpected error
    """
    # https://docs.github.com/en/actions/reference/security/oidc#methods-for-requesting-the-oidc-token

    if "ACTIONS_ID_TOKEN_REQUEST_TOKEN" in os.environ:
        resp = yield httpx.Request(
            "GET",
            os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"],
            params={"audience": audience},
            headers={
                "Authorization": "bearer "
                + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"],
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        return body["value"]

    return None
