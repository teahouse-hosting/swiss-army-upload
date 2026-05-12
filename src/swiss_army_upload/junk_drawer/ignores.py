"""
Exclusion engine for synchronization
"""
# Jamie expects there's a lot of room for optimization here, since it has to
# evaluate every name seen

import dataclasses
import fnmatch
import pathlib
from pathlib import PurePath
import re
from types import EllipsisType
import typing as T

import anyio
import httpx
import scr

from swiss_army_upload import CliArgs, ExcludeSpecial


#: True means "keep", False means "ignore", ... means "ask someone else"
type Result = bool | EllipsisType


@dataclasses.dataclass
class ConstRule:
    name: str


@dataclasses.dataclass
class GlobRule:
    pattern: str


DEFAULT_IGNORES = {".git", ".gitignore"}


class DefaultRule:
    """
    Optimized handling of the default ignore list
    """


Rule = ConstRule | GlobRule | DefaultRule


def is_glob(text: str) -> bool:
    if "*" in text or "?" in text:
        return True
    else:
        return False


# FIXME: Case handling
# FIXME: fnmatch might compile the wrong thing for matching URLs on Windows
class IgnoreEngine:
    rules: list[Rule]

    # Compiled versions
    _consts: set[str]
    _pats: list[re.Pattern]

    @classmethod
    async def from_args(
        cls, exclusions: list[str | anyio.Path | ExcludeSpecial]
    ) -> T.Self:
        """
        Construct engine from CLI exclusions
        """
        rules: list[Rule] = []
        for excl in exclusions:
            match excl:
                case str():
                    if is_glob(excl):
                        rules.append(GlobRule(excl))
                    else:
                        rules.append(ConstRule(excl))
                case anyio.Path():
                    raise NotImplementedError("Read a gitignore file")
                case ExcludeSpecial.Default:
                    rules.append(DefaultRule())
                case ExcludeSpecial.Nothing:
                    rules = []

        self = cls()
        self.rules = rules
        self._compile()
        return self

    def _compile(self):
        self._consts = set()
        self._pats = list()
        for rule in self.rules:
            match rule:
                case GlobRule(pattern=pat):
                    self._pats.append(re.compile(fnmatch.translate(pat)))
                case ConstRule(name=name):
                    self._consts.add(name)
                case DefaultRule():
                    self._consts |= DEFAULT_IGNORES

    def __call__(self, filename: anyio.Path | httpx.URL) -> bool:
        """
        Check the rules against the given path. False if excluded, True if included.
        """
        path: PurePath
        if isinstance(filename, httpx.URL):
            path = pathlib.PurePosixPath(filename.path)
        else:
            # Jamie thinks that anyio.Path fully implements PurePath, it's just
            # the Path stuff that's incompatible
            path = T.cast(PurePath, filename)

        if path.name in self._consts:
            return False
        elif any(p.match(str(path)) for p in self._pats):
            return False
        else:
            return True


async def _factory(svcs_container):
    args = await svcs_container.aget(CliArgs)
    return await IgnoreEngine.from_args(args.exclusions)


scr.registry.register_factory(IgnoreEngine, _factory)
