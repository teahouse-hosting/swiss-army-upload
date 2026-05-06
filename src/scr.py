# SPDX-FileCopyrightText: 2023 Hynek Schlawack <hs@ox.cx>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import contextlib
from functools import singledispatch

from svcs import exceptions
from svcs._core import (
    Container,
    RegisteredService,
    Registry,
    ServicePing,
)


__all__ = [
    "Container",
    "RegisteredService",
    "Registry",
    "ServicePing",
    "exceptions",
]


@singledispatch
def scr_from(obj) -> Container:
    raise TypeError(f"Don't know how to get Container from {obj!r}")


svcs_from = scr_from


@scr_from.register
def _(obj: Container) -> Container:
    return obj


async def aget(ctx: object, *svc_types: type) -> object:
    """
    Same as :meth:`svcs.Container.aget`, but uses the container from *ctx*.
    """
    return await scr_from(ctx).aget(*svc_types)


registry: Registry = Registry()
root: Container


@contextlib.asynccontextmanager
async def ainit():
    """
    Handles cleanup of the registry and root container, for async apps.
    """
    global root  # noqa: PLW0603
    # Do not close the registry; it'll erase all the init
    root = Container(registry)
    async with root:
        yield root


@contextlib.contextmanager
def init():
    """
    Handles cleanup of the registry and root container, for sync apps.
    """
    global root  # noqa: PLW0603
    # Do not close the registry; it'll erase all the init
    root = Container(registry)
    with root:
        yield root
