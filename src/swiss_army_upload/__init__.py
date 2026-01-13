from dataclasses import dataclass
from pathlib import Path
import sys
import typing as T

import anyio
import dykes
import httpx
import scr

from .backends import get_backend, UnknownURLError, NoCredentialsFound
from .deps import enter_container


@dataclass
class LoginCmd:
    """
    Log in to a backend
    """

    url: T.Annotated[httpx.URL, "URL to log in to"]


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

    login: dykes.Subparser[LoginCmd] = None
    get: dykes.Subparser[GetCmd] = None
    put: dykes.Subparser[PutCmd] = None


async def do_login(args: LoginCmd):
    if not args.url.scheme:
        assert not args.url.host
        args.url = httpx.URL(scheme=args.url.path)
    print(f"login {args!r}")


async def do_get(args: GetCmd):
    print(f"get {args!r}")
    backend = get_backend(args, args.src)
    print(f"\t{backend=}")
    async with backend:
        if await backend.is_file(args.src):
            await backend.get_to_file(args.src, args.dest)
        else:
            raise NotImplementedError


async def do_put(args: PutCmd):
    print(f"put {args!r}")
    backend = get_backend(args, args.dest)
    print(f"\t{backend=}")
    ...


async def main():
    async with scr.ainit():
        args = dykes.parse_args(SAUArgs)

        retval = 0
        try:
            if args.login is not None:
                async with enter_container(args, args.login):
                    await do_login(args.login)
            elif args.get is not None:
                async with enter_container(args, args.get):
                    await do_get(args.get)
            elif args.put is not None:
                async with enter_container(args, args.put):
                    await do_put(args.put)
            else:
                # FIXME: Print usage
                sys.exit("No command specified")
        except* UnknownURLError as egrp:
            for uue in egrp.exceptions:
                print(str(uue.args[0]), file=sys.stderr)
            del uue
            retval = 1
        except* NoCredentialsFound as egrp:
            for ncf in egrp.exceptions:
                print(str(ncf.args[0]), file=sys.stderr)
            del ncf
            print("Did you need to use the login command?")
            retval = 1
        sys.exit(retval)


def entrypoint():
    anyio.run(main, backend="trio")
