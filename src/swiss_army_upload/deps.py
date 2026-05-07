"""
saucer/svcs definitions
"""

import argparse
import contextlib
import dataclasses
import http.cookiejar
import logging
import typing as T

import httpx
import platformdirs
import rich.console
import scr

from .junk_drawer.cookiejar import SecureSavedJar
from .junk_drawer import keyring


LOG = logging.getLogger(__name__)

SCR_ATTR = "__scr_container"


@scr.scr_from.register
def _(ctx: object):
    if not dataclasses.is_dataclass(ctx):
        raise NotImplementedError
    return getattr(ctx, SCR_ATTR)


@scr.scr_from.register
def _(ctx: argparse.Namespace):
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
async def get_jar(svcs_container):
    platdirs = await svcs_container.aget(platformdirs.PlatformDirs)
    async with SecureSavedJar(platdirs.user_cache_dir + "/cookies.blob") as jar:
        yield jar


scr.registry.register_factory(http.cookiejar.CookieJar, get_jar, enter=True)


@contextlib.asynccontextmanager
async def build_client(svcs_container):
    jar = await svcs_container.aget(http.cookiejar.CookieJar)
    async with (
        httpx.AsyncClient(
            http2=True,
            cookies=jar,
            headers={"User-Agent": "swiss-army-upload/0.0.0"},
            follow_redirects=False,  # This causes complications in implementing auth code
        ) as client,
    ):
        yield client


scr.registry.register_factory(httpx.AsyncClient, build_client, enter=True)


async def get_keyring() -> keyring.AsyncKeyring:
    classes = await keyring.get_viable_backends()
    keyrings = [((kr := cls()), await kr.priority()) for cls in classes]
    keyrings.sort(key=lambda t: -t[1])
    if len(keyrings) == 0:
        raise RuntimeError("Unable to find viable credentials keyring")
    elif len(keyrings) == 1:
        ring, _ = keyrings[0]
        LOG.info("Using keyring %s", ring.name)
        return ring
    else:
        # More than one ring
        # TODO: chain them together
        ring, _ = keyrings[0]
        LOG.info(
            "Using keyring %s (also %s)",
            ring,
            ", ".join(str(r) for r, _ in keyrings[1:]),
        )
        return ring


scr.registry.register_factory(keyring.AsyncKeyring, get_keyring, enter=False)


scr.registry.register_factory(rich.console.Console, rich.console.Console, enter=False)


@contextlib.asynccontextmanager
async def enter_container(*objects) -> T.AsyncIterator[scr.Container]:
    async with scr.root as ctr:
        for obj in objects:
            setattr(obj, SCR_ATTR, ctr)
        yield ctr
