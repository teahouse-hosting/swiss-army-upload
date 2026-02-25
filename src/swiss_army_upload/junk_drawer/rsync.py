"""
rsync-like engine framework
"""

import abc
import collections
import dataclasses
import datetime
import enum
import posixpath
import typing as T

import anyio
import anyio.abc
import anyio.streams.file
import httpx

from .ahashlib import hash_stream


@dataclasses.dataclass
class RFileMeta:
    name: str
    size: int | None = None
    mtime: datetime.datetime | None = None
    hash_md5: bytes | None = None
    hash_sha1: bytes | None = None
    hash_sha256: bytes | None = None

    def populated(self) -> dict:
        return {
            key: val
            for key, val in vars(self).items()
            if key != "name"
            if val is not None
        }

    def populated_algos(self) -> list[str]:
        """
        Return the hash algorithms with populated digests
        """
        return [
            aname.removeprefix("hash_")
            for aname in dir(self)
            if aname.startswith("hash_")
            if getattr(self, aname) is not None
        ]

    def unpopulated_algos(self) -> list[str]:
        """
        Return the hash algorithms that are defined but have no digest
        """
        return [
            aname.removeprefix("hash_")
            for aname in dir(self)
            if aname.startswith("hash_")
            if getattr(self, aname) is None
        ]


async def _do_hash(file: anyio.AsyncFile[bytes], algo: str, meta: RFileMeta):
    # Don't context-manage the stream, it's the caller's job to close everything
    stream = anyio.streams.file.FileReadStream(T.cast(T.BinaryIO, file.wrapped))
    digest = await hash_stream(algo, stream)
    setattr(meta, f"hash_{algo}", digest)


async def _better_walk(
    root: anyio.Path, stream: anyio.abc.UnreliableObjectSendStream[anyio.Path]
):
    """
    Yield all the files within the root, recursively.
    """
    q = collections.deque([root])
    while q:
        pdir = q.popleft()
        async for file in pdir.iterdir():
            if file.info.is_file():
                await stream.send(file)
            elif file.info.is_dir():
                q.append(file)


class Op(enum.Enum):
    CREATE = enum.auto()
    UPDATE = enum.auto()
    DELETE = enum.auto()


@dataclasses.dataclass
class Operation:
    op: Op
    src: anyio.Path | httpx.URL | None
    dest: anyio.Path | httpx.URL


def _url_join(url: httpx.URL, stub: str) -> httpx.URL:
    return httpx.URL(url, path=posixpath.join(url.path, stub))


class Engine(abc.ABC):
    #: Suggested RFileMeta fields to request
    attrs_to_get: list[str]

    @abc.abstractmethod
    async def iter_remote(
        self, url: httpx.URL, stream: anyio.abc.UnreliableObjectSendStream[RFileMeta]
    ):
        """
        Produce the list of files on the remote.

        Only populate metadata fields that are free.
        """

    async def fill_remote_meta(
        self, url: httpx.URL, meta: RFileMeta, field_hints: list[str]
    ):
        """
        Perform additional requests to fill the rest of the metadata.

        How hard this should work is up to the implementer.

        Args:
            field_hints: What fields (RFileMeta) do we actually care about?
        """

    async def iter_local(
        self, path: anyio.Path, stream: anyio.abc.UnreliableObjectSendStream[RFileMeta]
    ):
        """
        Produce list of files in the local filesystem.
        """
        async with stream, anyio.create_task_group() as tg:
            send, recv = anyio.create_memory_object_stream[anyio.Path]()
            tg.start_soon(_better_walk, path, send)
            async with recv:
                async for file in recv:
                    stat = await file.stat()
                    await stream.send(
                        RFileMeta(
                            name=str(file.relative_to(path)),
                            size=stat.st_size,
                            mtime=datetime.datetime.fromtimestamp(
                                stat.st_mtime, tz=datetime.UTC
                            ),
                        )
                    )

    async def fill_local_meta(
        self, path: anyio.Path, meta: RFileMeta, field_hints: list[str]
    ):
        """
        Perform additional requests to fill the rest of the metadata.

        How hard this should work is up to the implementer.

        Args:
            field_hints: What fields (RFileMeta) do we actually care about?
        """
        # Ignore name, size, mtime: iter_local() unconditionally populates them
        hash_algos = {
            hint.removeprefix("hash_")
            for hint in field_hints
            if hint.startswith("hash_")
        } - set(meta.populated_algos())
        async with anyio.create_task_group() as tg:
            # FIXME: Read the file once and mux it between hashing tasks.
            for algo in hash_algos:
                tg.start_soon(_do_hash, await path.open("rb"), algo, meta)

    async def _build_meta_dict(self, func, root, results):
        send, recv = anyio.create_memory_object_stream[RFileMeta]()

        async with anyio.create_task_group() as tg:
            tg.start_soon(func, root, send)
            async with recv:
                async for meta in recv:
                    results[meta.name] = meta

    async def __call__(
        self,
        source: anyio.Path | httpx.URL,
        dest: anyio.Path | httpx.URL,
        ops: anyio.abc.UnreliableObjectSendStream[Operation],
    ):
        """
        Do all the metadata work, and produce a stream of operations.
        """
        async with ops:
            if isinstance(source, anyio.Path):
                local_root: anyio.Path = T.cast(anyio.Path, source)
                remote_root: httpx.URL = T.cast(httpx.URL, dest)
                local2remote = True
            else:
                local_root = T.cast(anyio.Path, dest)
                remote_root = T.cast(httpx.URL, source)
                local2remote = False

            # First, populate both lists
            async with anyio.create_task_group() as tg:
                remote_metas: dict[str, RFileMeta] = dict()
                local_metas: dict[str, RFileMeta] = dict()
                tg.start_soon(
                    self._build_meta_dict, self.iter_remote, remote_root, remote_metas
                )
                tg.start_soon(
                    self._build_meta_dict, self.iter_local, local_root, local_metas
                )

            remote_files = set(remote_metas.keys())
            local_files = set(remote_metas.keys())

            # Second, figure out the creates and deletes
            only_remote = remote_files - local_files
            only_local = local_files - remote_files

            for name in only_remote:
                meta = remote_metas[name]
                await ops.send(
                    Operation(
                        op=Op.DELETE if local2remote else Op.CREATE,
                        src=(
                            local_root / meta.name
                            if local2remote
                            else _url_join(remote_root, meta.name)
                        ),
                        dest=(
                            _url_join(remote_root, meta.name)
                            if local2remote
                            else local_root / meta.name
                        ),
                    )
                )

            for name in only_local:
                meta = local_metas[name]
                await ops.send(
                    Operation(
                        op=Op.CREATE if local2remote else Op.DELETE,
                        src=(
                            local_root / meta.name
                            if local2remote
                            else _url_join(remote_root, meta.name)
                        ),
                        dest=(
                            _url_join(remote_root, meta.name)
                            if local2remote
                            else local_root / meta.name
                        ),
                    )
                )

            # Third, do annoying metadata stuff
            async def _deep_comparison(name):
                rmeta = remote_metas[name]
                lmeta = local_metas[name]

                await self.fill_local_meta(
                    local_root / name,
                    lmeta,
                    [name for name, val in vars(rmeta).items() if val is not None],
                )

                rcheap = rmeta.populated()
                lcheap = lmeta.populated()

                if rcheap != lcheap:
                    # Mismatch in the easy stuff
                    await ops.send(
                        Operation(
                            op=Op.UPDATE,
                            src=(
                                local_root / meta.name
                                if local2remote
                                else _url_join(remote_root, meta.name)
                            ),
                            dest=(
                                _url_join(remote_root, meta.name)
                                if local2remote
                                else local_root / meta.name
                            ),
                        )
                    )
                    return

                # Ok, so we need to do the expensive stuff
                async with anyio.create_task_group() as tg:
                    tg.start_soon(
                        self.fill_remote_meta,
                        _url_join(remote_root, name),
                        rmeta,
                        self.attrs_to_get,
                    )
                    tg.start_soon(
                        self.fill_local_meta,
                        local_root / name,
                        lmeta,
                        self.attrs_to_get,
                    )

                rexp = rmeta.populated()
                lexp = lmeta.populated()

                if rexp != lexp:
                    # Mismatch on the hard stuff
                    await ops.send(
                        Operation(
                            op=Op.UPDATE,
                            src=(
                                local_root / meta.name
                                if local2remote
                                else _url_join(remote_root, meta.name)
                            ),
                            dest=(
                                _url_join(remote_root, meta.name)
                                if local2remote
                                else local_root / meta.name
                            ),
                        )
                    )
                    return

            in_both = remote_files & local_files
            async with anyio.create_task_group() as tg:
                for name in in_both:
                    tg.start_soon(_deep_comparison, name)
