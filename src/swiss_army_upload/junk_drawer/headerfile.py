import re
import pathlib

import anyio
from anyio import AsyncFile
from anyio.streams.text import TextReceiveStream
from httpx import Headers


def _append_header(self: Headers, key: str, value: str):
    # Holy shit, why is this operation not on the class???
    set_key = key.encode(self._encoding or "utf-8")
    set_value = value.encode(self._encoding or "utf-8")
    lookup_key = set_key.lower()
    self._list.append((set_key, lookup_key, set_value))


_PLACEHOLDER_WILDCARD = re.compile(r"\*|(?<=/):[^/]+(?=/|$)")


class NetlifyHeaderFile:
    """
    Represents a relatively raw netlify header file.

    See: https://docs.netlify.com/manage/routing/headers/#syntax-for-the-headers-file
    """

    _data: dict[str | re.Pattern, Headers]

    def __init__(self):
        self._data = {}

    def _parser(self):
        """
        Coroutine that accepts one line at a time and populates the object.
        """
        current_heads = list()
        while True:
            line: str | None = yield
            if line is None:
                break
            if line.lstrip().startswith("#"):
                # Comment
                continue
            elif line.lstrip() != line:
                # Header line
                name, _, value = line.partition(":")
                _append_header(current_heads, name.strip(), value.strip())
            else:
                # Route line
                route = line.strip()
                if "*" in route or ":" in route:
                    route = re.compile(self._build_wildcard_regex(route))
                if route in self._data:
                    current_heads = self._data[route]
                else:
                    current_heads = self._data[route] = Headers()

    def _build_wildcard_regex(self, txt: str):
        def subs(m: re.Match):
            if m.group(0) == "*":
                # Wildcard, match anything
                return ".*"
            else:
                # Placeholder, match just that segment
                return "[^/]+"

        return _PLACEHOLDER_WILDCARD.sub(subs, txt)

    @classmethod
    async def load(cls, stream: TextReceiveStream):
        """
        Instantiate from the textual data read from a stream.
        """
        self = cls()

        parser = self._parser()  # Advance to the first yield
        next(parser)
        buff = ""
        async for chunk in stream:
            buff += chunk
            while "\n" in buff:
                line, _, buff = buff.partition("\n")
                print(f"{line=} {buff=}")
                parser.send(line)
        parser.send(buff)

        # Wait for the parser to finish
        for _ in parser:
            pass

        return self

    @classmethod
    async def loadf(cls, file: AsyncFile):
        """
        Instantiate from the textual data read from a stream.

        The file must be opened for reading in text mode with universal newlines.
        """
        self = cls()

        parser = self._parser()
        next(parser)  # Advance to the first yield
        while True:
            line: str = await file.readline()
            if not line:
                break
            else:
                line = line.rstrip("\n")
                parser.send(line)

        # Wait for the parser to finish
        for _ in parser:
            pass

        return self

    @classmethod
    def loads(cls, txt: str):
        """
        Read a text blob
        """
        self = cls()

        parser = self._parser()
        next(parser)  # Advance to the first yield
        for line in txt.split("\n"):
            parser.send(line)

        # Wait for the parser to finish
        for _ in parser:
            pass

        return self

    def _find_items(self, path: str):
        for key, heads in self._data.items():
            if key == path:
                yield heads
            elif isinstance(key, re.Pattern) and key.fullmatch(path):
                yield heads

    def resolve(self, path: anyio.Path | pathlib.PurePath) -> Headers:
        """
        Given a relative path, return the headers this file defines for it.
        """
        if path.is_absolute():
            raise ValueError(f"Path must be relative (got {path!r})")
        spath = "/" + "/".join(path.parts)
        rv = Headers()
        for head in self._find_items(spath):
            rv.update(head)
        return rv


class HeaderManager:
    """
    Manages multiple ``_headers``.
    """

    # directory -> NHF
    _files: dict[anyio.Path, NetlifyHeaderFile | None]

    def __init__(self):
        self._files = {}

    async def _find_files(self, path: anyio.Path):
        for pdir in path.parents:
            if pdir in self._files:
                nhf = self._files[pdir]
                if nhf is not None:
                    yield pdir, nhf
            else:
                head_file = pdir / "_headers"
                try:
                    fo = await head_file.open("rt")
                except FileNotFoundError:
                    self._files[pdir] = None
                else:
                    nhf = self._files[pdir] = await NetlifyHeaderFile.loadf(fo)
                    yield pdir, nhf

    async def resolve(self, path: anyio.Path | pathlib.PurePath):
        path = await anyio.Path(path).absolute()
        nhfs: list[tuple[anyio.Path, NetlifyHeaderFile]] = reversed(
            [nhf async for nhf in self._find_files(path)]
        )
        rv = Headers()
        for pdir, nhf in nhfs:
            rv.update(nhf.resolve(path.relative_to(pdir)))
        return rv
