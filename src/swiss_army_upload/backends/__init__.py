import abc
import importlib.metadata
import os
import typing

import httpx
import scr
from scr import scr_from


class InvalidCredentials(Exception):
    """
    Raised when the credentials were rejected
    """


class UnknownSite(Exception):
    """
    Raised when the backend doesn't know the domain
    """


class NoCredentialsFound(Exception):
    """
    Unable to find the appropriate credentials
    """


class Backend(abc.ABC):
    hinted_base: httpx.URL
    scr: scr.Container

    def __init__(self, ctx: object, hint: httpx.URL):
        self.hinted_base = hint
        self.scr = scr_from(ctx)

    @abc.abstractmethod
    async def __aenter__(self) -> typing.Self: ...

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_value, traceback): ...

    @abc.abstractmethod
    async def check_credentials(self, url: httpx.URL) -> bool: ...

    @abc.abstractmethod
    async def prompt_for_credentials(self, url: httpx.URL): ...

    @abc.abstractmethod
    async def is_file(self, url: httpx.URL) -> bool: ...

    @abc.abstractmethod
    async def get_to_file(self, url: httpx.URL, file: os.PathLike | str): ...


class UnknownURLError(ValueError):
    pass


def get_backend(ctx: object, url: httpx.URL) -> Backend:
    try:
        (ep,) = importlib.metadata.entry_points(
            name=url.scheme, group="swiss_army_upload.backend"
        )
    except ValueError as exc:
        raise UnknownURLError(
            f"Don't know how to handle a {url.scheme!r} URL", url
        ) from exc
    backcls: type[Backend] = ep.load()
    return backcls(ctx, url)
