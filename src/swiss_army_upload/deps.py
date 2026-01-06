"""
saucer/svcs definitions
"""

import contextlib
import dataclasses

import httpx
import platformdirs
import scr

from .junk_drawer.cookiejar import SecureSavedJar

SCR_ATTR = "__scr_container"


# I'd like this to filter for CLI param classes, but that's circular
@scr.scr_from.register
def _(ctx: object):
    if not dataclasses.is_dataclass(ctx):
        raise NotImplementedError
    return getattr(ctx, SCR_ATTR)


def get_appdirs() -> platformdirs.PlatformDirs:
    return platformdirs.PlatformDirs(
        appname="swiss-army-upload",
        appauthor="teahouse",
        # TODO: Roaming?
        # TODO: Versioned?
        ensure_exists=True,
        # Wish ensure_exists was asyncable, but directory creation should be
        # cached and backgrounded by all OSes
        opinion=True,
    )


scr.registry.register_factory(platformdirs.PlatformDirs, get_appdirs, enter=True)


@contextlib.asynccontextmanager
async def build_client(svcs_container):
    platdirs = await svcs_container.aget(platformdirs.PlatformDirs)
    async with (
        SecureSavedJar(platdirs.user_cache_dir + "/cookies.blob") as jar,
        httpx.AsyncClient(http2=True, cookies=jar) as client,
    ):
        yield client


scr.registry.register_factory(httpx.AsyncClient, build_client, enter=True)


@contextlib.asynccontextmanager
async def enter_container(*objects) -> scr.Container:
    async with scr.root.afork() as ctr:
        for obj in objects:
            setattr(obj, SCR_ATTR, ctr)
        yield ctr
