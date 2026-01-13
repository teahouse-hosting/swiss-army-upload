from contextlib import asynccontextmanager
import http.cookiejar
import logging
import os
import typing

import anyio


LOG = logging.getLogger(__name__)


class SecureSavedJar(http.cookiejar.CookieJar, anyio.AsyncContextManagerMixin):
    """
    Securely serializes cookies to disk, maintaining a long-term jar.

    This is multi-process safe.
    """

    # FIXME: Actually serialize

    def __init__(
        self,
        filename: os.PathLike | str,
        policy: http.cookiejar.CookiePolicy | None = None,
    ):
        super().__init__(policy)

    @asynccontextmanager
    async def __asynccontextmanager__(self) -> typing.AsyncGenerator[typing.Self]:
        yield self
