from dataclasses import dataclass
from pathlib import Path
import sys
import typing as T

import anyio
import httpx

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

    src: T.Annotated[httpx.URL, "URL to read from"]
    dest: T.Annotated[Path, "Path to write to"]


@dataclass
class PutCmd:
    """
    Upload one or more files
    """

    src: T.Annotated[Path, "Path to read from"]
    dest: T.Annotated[httpx.URL, "URL to write to"]


@dataclass
class SAUArgs:
    """
    Upload to a variety of web hosts
    """

    config: dykes.Subparser[ConfigCmd] = None
    get: dykes.Subparser[GetCmd] = None
    put: dykes.Subparser[PutCmd] = None


async def do_config(args):
    print(f"config {args!r}")
    ...


async def do_get(args):
    print(f"get {args!r}")
    ...


async def do_put(args):
    print(f"put {args!r}")
    ...


async def main():
    args = dykes.parse_args(SAUArgs)
    if args.config is not None:
        await do_config(args.config)
    elif args.get is not None:
        await do_get(args.get)
    elif args.put is not None:
        await do_put(args.put)
    else:
        # FIXME: Print usage
        sys.exit("No command specified")


def entrypoint():
    anyio.run(main, backend="trio")
