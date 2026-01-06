"""
saucer/svcs definitions
"""

import contextlib
import dataclasses

import httpx
import scr

SCR_ATTR = "__scr_container"


# I'd like this to filter for CLI param classes, but that's circular
@scr.scr_from.register
def _(ctx: object):
    if not dataclasses.is_dataclass(ctx):
        raise NotImplementedError
    return getattr(ctx, SCR_ATTR)


@contextlib.asynccontextmanager
async def enter_container(*objects) -> scr.Container:
    async with scr.root.afork() as ctr:
        for obj in objects:
            setattr(obj, SCR_ATTR, ctr)
        yield ctr


async def build_client(svcs_container):
    return httpx.AsyncClient()


scr.registry.register_factory(httpx.AsyncClient, build_client, enter=True)
