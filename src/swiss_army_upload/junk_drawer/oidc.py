import abc
import os
import typing

import httpx


class OidcTool(abc.ABC):
    """
    Abstract class for doing an OIDC acquisition flow within an httpx auth.

    In a synchronous context, you can just::

        token = yield from oidc_tool

    In an async context, you need:

        async for req in oidc_tool:
            resp = yield req
            await oidc_tool.asend(resp)
        if oidc_tool:
            token = oidc_tool.token
    """

    #: The resulting token. Only exists if bool(self)
    token: str

    audience: str | None

    _going: bool = False
    _buffer: httpx.Response | None = None

    def __init__(self, audience: str | None = None):
        self.audience = audience

    @staticmethod
    @abc.abstractmethod
    def is_available() -> bool:
        """
        Are we in an environment where this is available?
        """

    def __bool__(self):
        return hasattr(self, "token")

    @abc.abstractmethod
    def __iter__(
        self,
    ) -> typing.Generator[httpx.Request, httpx.Response, str | None]: ...

    async def __aiter__(self) -> typing.AsyncIterator[httpx.Request]:
        if self._going:
            raise RuntimeError("Not reentrant")
        self._going = True
        try:
            gen = iter(self)
            yield next(gen)
            while True:
                if self._buffer is None:
                    raise RuntimeError("Need to send between iterations")
                else:
                    resp, self._buffer = self._buffer, None
                    yield gen.send(resp)
        except StopIteration as exc:
            # Hopefully this is redundant
            self.token = exc.value
            return
        finally:
            self._going = False

    async def asend(self, resp: httpx.Response):
        if self._buffer is not None:
            raise RuntimeError("Need to iterate between sends")
        await resp.aread()
        self._buffer = resp


class GitHubOIDC(OidcTool):
    """
    GitHub and Forgejo Actions OIDC
    """

    @staticmethod
    def is_available():
        # Sorry for the format, ruff just wants to do this
        return os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN") and os.environ.get(
            "ACTIONS_ID_TOKEN_REQUEST_URL"
        )

    def __iter__(self):
        # https://docs.github.com/en/actions/reference/security/oidc#methods-for-requesting-the-oidc-token
        resp = yield httpx.Request(
            "GET",
            os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"],
            params={"audience": self.audience or ""},
            headers={
                "Authorization": "bearer "
                + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"],
                "Accept": "application/json",
            },
        )
        # FIXME: Call resp.read() in synchronous contexts
        resp.raise_for_status()
        return resp.text


PROVIDERS = [GitHubOIDC]


def oidc_tool(audience: str | None = None) -> OidcTool | None:
    for prov in PROVIDERS:
        if prov.is_available():
            return prov(audience)
    else:
        return None
