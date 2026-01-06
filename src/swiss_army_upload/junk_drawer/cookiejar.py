from contextlib import asynccontextmanager
import http.cookiejar
import os
import typing

import anyio


class SecureSavedJar(http.cookiejar.CookieJar, anyio.AsyncContextManagerMixin):
    """
    Securely serializes cookies to disk, maintaining a long-term jar.

    This is multi-process safe.
    """

    # FIXME: Actually serialize

    def __init__(
        self,
        filename: os.PathLike | str,
        policy: http.cookierjar.CookiePolicy | None = None,
    ):
        super().__init__(policy)

    @asynccontextmanager
    async def __asynccontextmanager__(self) -> typing.AsyncGenerator[typing.Self]:
        yield self
