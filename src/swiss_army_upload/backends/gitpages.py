import contextlib
import dataclasses
import json
import logging
import os
import sys
import tarfile
import tempfile
import time
import typing as T

import anyio
import httpdate
import httpx
import platformdirs
import rich.console
from rich.prompt import Prompt
import scr

from . import Backend, InvalidCredentials
from ..junk_drawer.keyring import AsyncKeyring
from ..junk_drawer.sync import sync_to_async

LOG = logging.getLogger(__name__)


class GitPagesAuth(httpx.Auth):
    def __init__(self, saucer: scr.Container):
        self.scr = saucer

    async def async_auth_flow(self, request: httpx.Request):
        keyring: AsyncKeyring = await self.scr.aget(AsyncKeyring)  # type: ignore
        cred = await keyring.get_credential(request.url.host, None)
        if cred is not None:
            request.headers["Authorization"] = f"Pages {cred.password}"
        yield request


def _get_auth(svcs_container):
    return GitPagesAuth(svcs_container)


scr.registry.register_factory(GitPagesAuth, _get_auth, enter=False)


@dataclasses.dataclass
class TFile:
    """
    A file that's about to get shoved into a tarfile
    """

    name: str
    source: os.PathLike | str
    # Skipping size, it'll be read in later
    mtime: float
    # Skipping type, linkname, devmajor, devminor, not applicable
    # Skipping mode, uid, gid, uname, gname, don't need them here

    @classmethod
    async def from_file(cls, path: os.PathLike | str, dest: str) -> T.Self:
        return cls(
            name=dest, source=path, mtime=(await anyio.Path(path).stat()).st_mtime
        )

    def to_tarinfo(self) -> tarfile.TarInfo:
        ti = tarfile.TarInfo(self.name)
        ti.mtime = self.mtime
        ti.mode = 0o644
        ti.size = os.stat(self.source).st_size
        return ti

    def open(self):
        return open(self.source, "rb")


# Note that we have to be pretty precise about what entries appear in the tar file,
# see https://codeberg.org/git-pages/git-pages/src/branch/main/README.md for details


@sync_to_async
def bundle_into_tarfile(files: T.Iterable[TFile]) -> bytes:
    """
    Builds a synthetic tar with the given entries.

    No implicit entries are added.

    Return is zstd compressed tar data.
    """
    with tempfile.TemporaryFile("wb+") as fbytes:
        with tarfile.open(fileobj=fbytes, mode="x:zst") as ftar:
            for inode in files:
                ti = inode.to_tarinfo()
                with inode.open() as fsrc:
                    ftar.addfile(ti, fsrc)
        fbytes.seek(0)
        return fbytes.read()


class GitPagesBackend(anyio.AsyncContextManagerMixin, Backend):
    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self):
        yield self

    @contextlib.asynccontextmanager
    async def _cache_dir(self, domain) -> T.AsyncIterable[anyio.Path]:
        pdirs = await self.scr.aget(platformdirs.PlatformDirs)
        cachedir = anyio.Path(pdirs.user_cache_dir)
        sitedir = cachedir / "gitpages" / domain
        await sitedir.mkdir(parents=True, exist_ok=True)
        yield sitedir

    async def _request(self, method, url, **opts):
        http, auth = await self.scr.aget(httpx.AsyncClient, GitPagesAuth)
        resp = await http.request(
            method,
            # Yes, must be HTTP, due to site bootstrap concerns
            httpx.URL(url, scheme="http"),
            auth=auth,
            follow_redirects=True,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise InvalidCredentials(
                    f"Invalid credentials for {url.host} at Git Pages"
                ) from exc
            else:
                exc.add_note(f"Body: {resp.text}")
                raise
        else:
            return resp

    @contextlib.asynccontextmanager
    async def _stream(self, method, url, **opts):
        http, auth = await self.scr.aget(httpx.AsyncClient, GitPagesAuth)
        async with http.stream(
            method,
            # Yes, must be HTTP, due to site bootstrap concerns
            httpx.URL(url, scheme="http"),
            auth=auth,
            follow_redirects=True,
        ) as resp:
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    raise InvalidCredentials(
                        f"Invalid credentials for {url.host} at Git Pages"
                    ) from exc
                else:
                    exc.add_note(f"Body: {await resp.aread()}")
                    raise
            else:
                yield resp

    # FIXME: Cache this on what policy?
    async def _get_status(self, domain: str) -> int:
        """
        Query for the current manifest timestamp.

        Return:
            int: The current manifest, as a unix timestamp
        """
        resp = await self._request(
            "GET",
            httpx.URL(host=domain, path="/.git-pages/health"),
        )

        return httpdate.httpdate_to_unixtime(resp.headers["Last-Modified"])

    async def _get_manifest(self, domain: str):
        last_updated = await self._get_status(domain)
        async with self._cache_dir(domain) as sitecache:
            manicache = sitecache / "manifest.json"
            try:
                cstat = await manicache.stat()
                cache_updated = cstat.st_mtime
            except FileNotFoundError:
                cache_updated = float("-inf")

            if last_updated <= cache_updated:
                LOG.debug(
                    "Loading manifest from cache (last_updated:%r <= cache_updated:%r)",
                    last_updated,
                    cache_updated,
                )
                return json.loads(await manicache.read_text())
            else:
                LOG.debug(
                    "Download manifest from server (last_updated:%r > cache_updated:%r)",
                    last_updated,
                    cache_updated,
                )
                resp = await self._request(
                    "GET",
                    httpx.URL(host=domain, path="/.git-pages/manifest.json"),
                )
                lm = httpdate.httpdate_to_unixtime(resp.headers["Last-Modified"])
                await manicache.write_text(resp.text)
                await sync_to_async(os.utime)(manicache, (time.time(), lm))
                return json.loads(resp.text)

    async def _download_site(self, domain: str):
        last_updated = await self._get_status(domain)
        async with self._cache_dir(domain) as sitecache:
            archcache = sitecache / "archive.tar"
            try:
                cstat = await archcache.stat()
                cache_updated = cstat.st_mtime
            except FileNotFoundError:
                cache_updated = float("-inf")

            if last_updated <= cache_updated:
                LOG.debug(
                    "Loading archive from cache (last_updated:%r <= cache_updated:%r)",
                    last_updated,
                    cache_updated,
                )
                raise NotImplementedError
            else:
                LOG.debug(
                    "Download archive from server (last_updated:%r > cache_updated:%r)",
                    last_updated,
                    cache_updated,
                )
                # TODO: Show progress to user
                # TODO: Investigate compression
                async with self._stream(
                    "GET",
                    httpx.URL(host=domain, path="/.git-pages/archive.tar"),
                    stream=True,
                ) as resp:
                    lm = httpdate.httpdate_to_unixtime(resp.headers["Last-Modified"])
                    async with archcache.open("wb") as fcache:
                        async for chunk in resp.aiter_bytes():
                            await fcache.write(chunk)
                    raise NotImplementedError
                    lm, resp

    async def check_credentials(self, url: httpx.URL) -> bool:
        assert url.scheme == "pages"
        if not url.host:
            LOG.critical("Git Pages does not support global credentials, only per-site")
            sys.exit(1)

        try:
            await self._get_manifest(url.host)
        except InvalidCredentials:
            return False
        else:
            return True

    async def prompt_for_credentials(self, url: httpx.URL):
        console = await self.scr.aget(rich.console.Console)
        keyring: AsyncKeyring = await self.scr.aget(AsyncKeyring)  # type: ignore

        assert url.scheme == "pages"
        if not url.host:
            LOG.critical("Git Pages does not support global credentials, only per-site")
            sys.exit(1)

        credentials_ok = False
        while not credentials_ok:
            # These do block the event loop, but maybe that's ok?
            password = Prompt.ask("Git Pages Token", password=True, console=console)

            # FIXME: Try credentials before saving them
            await keyring.set_password(url.host, "Pages", password)

            credentials_ok = await self.check_credentials(url)
            if not credentials_ok:
                console.print("Unable to confirm credentials; try again")

    async def is_file(self, url: httpx.URL) -> bool:
        raise NotImplementedError

    async def get_to_file(self, url: httpx.URL, file: os.PathLike | str):
        assert url.scheme == "pages"
        raise NotImplementedError

    async def put_from_file(self, file: os.PathLike | str, url: httpx.URL):
        assert url.scheme == "pages"
        http, auth = await self.scr.aget(httpx.AsyncClient, GitPagesAuth)
        data = await bundle_into_tarfile(
            [
                await TFile.from_file(file, url.path),
            ]
        )

        await self._request(
            "PATCH",
            httpx.URL(host=url.host, path="/.git-pages/health"),
            headers={
                "Content-Type": "application/x-tar+zstd",
                "Create-Parents": "yes",
                "Atomic": "no",
            },
            content=data,
        )
