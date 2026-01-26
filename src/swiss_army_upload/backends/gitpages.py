import contextlib
import dataclasses
import logging
import os
import tarfile
import tempfile
import typing as T

import anyio
import httpx

from . import Backend, InvalidCredentials
from ..junk_drawer.sync import sync_to_async

LOG = logging.getLogger(__name__)


class GitPagesAuth(httpx.Auth): ...


@dataclasses.dataclass
class TFile:
    """
    A file that's about to get shoved into a tarfile
    """

    name: str
    source: os.PathLike | str
    # Skipping size, it'll be read in later
    mtime: int
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

    async def _get_status(self, domain: str):
        raise NotImplementedError

    async def _get_manifest(self, domain: str):
        raise NotImplementedError

    async def _download_site(self, domain: str):
        NotImplementedError

    async def check_credentials(self, url: httpx.URL) -> bool:
        raise NotImplementedError

    async def prompt_for_credentials(self, url: httpx.URL):
        raise NotImplementedError

    async def is_file(self, url: httpx.URL) -> bool:
        raise NotImplementedError

    async def get_to_file(self, url: httpx.URL, file: os.PathLike | str):
        assert url.scheme == "pages"
        raise NotImplementedError

    async def put_from_file(self, file: os.PathLike | str, url: httpx.URL):
        http = await self.scr.aget(httpx.AsyncClient)
        auth = GitPagesAuth()
        data = await bundle_into_tarfile(
            [
                await TFile.from_file(file, url.path),
            ]
        )

        resp = await http.request(
            # Yes, must be HTTP, due to site bootstrap concerns
            "PATCH",
            httpx.URL("http://", host=url.host),
            auth=auth,
            content=data,
            headers={
                "Content-Type": "application/x-tar+zstd",
                "Create-Parents": "yes",
                "Atomic": "no",
            },
            follow_redirects=True,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise InvalidCredentials(
                    f"Invalid credentials for {url.host} at Git Pages"
                ) from exc
