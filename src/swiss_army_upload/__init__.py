from dataclasses import dataclass
from pathlib import Path
import typing as T

import anyio

import dykes


@dataclass
class ConfigCmd:
    """
    Configure Swiss Army Upload
    """

    ...


@dataclass
class GetCmd:
    """
    Download one or more files
    """

    src: T.Annotated[str, "URL to read from"]
    dest: T.Annotated[Path, "Path to write to"]


@dataclass
class PutCmd:
    """
    Upload one or more files
    """

    src: T.Annotated[Path, "Path to read from"]
    dest: T.Annotated[str, "URL to write to"]


@dataclass
class SAUArgs:
    """
    Upload to a variety of web hosts
    """

    config: dykes.Subparser[ConfigCmd] = None
    get: dykes.Subparser[GetCmd] = None
    put: dykes.Subparser[PutCmd] = None


async def main():
    args = dykes.parse_args(SAUArgs)
    print(args)


def entrypoint():
    anyio.run(main, backend="trio")
