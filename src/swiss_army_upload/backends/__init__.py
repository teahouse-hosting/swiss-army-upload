import abc
import importlib.metadata
import typing

import httpx


class Backend(abc.ABC):
    hinted_base: httpx.URL

    def __init__(self, hint: httpx.URL):
        self.hinted_base = hint

    @abc.abstractmethod
    async def __aenter__(self) -> typing.Self: ...

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_value, traceback): ...


class UnknownURLError(ValueError):
    pass


def get_backend(url: httpx.URL) -> Backend:
    try:
        (ep,) = importlib.metadata.entry_points(
            name=url.scheme, group="swiss_army_upload.backend"
        )
    except ValueError as exc:
        raise UnknownURLError(
            f"Don't know how to handle a {url.scheme!r} URL", url
        ) from exc
    backcls: type[Backend] = ep.load()
    return backcls(url)
