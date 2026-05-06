import argparse
from enum import Enum
import logging
import logging.config
from pathlib import Path
import sys
import typing as T

import anyio
import httpx
import rich.logging
import scr

from .backends import get_backend, UnknownURLError, NoCredentialsFound, Backend
from .deps import enter_container


LOG = logging.getLogger(__name__)


class ExcludeSpecial(Enum):
    Nothing = "NOTHING"
    Default = "DEFAULT"


# Is actually a protocol, but isn't for Reasons:tm:
class CliArgs:
    command: str

    # Copy commands
    src: httpx.URL | anyio.Path
    dest: httpx.URL | anyio.Path
    exclusions: list[str | anyio.Path | ExcludeSpecial]

    # login
    url: httpx.URL


def _path_or_url(arg: str) -> httpx.URL | anyio.Path:
    # In this context, all the URLs given should have schemes
    if ":" in arg:
        # FIXME: Windows absolute paths
        url = httpx.URL(arg)
        if url.scheme:
            return url
    return anyio.Path(arg)


def parse_args(args: list[str] | None = None) -> CliArgs:
    parser = argparse.ArgumentParser(
        description="""
Upload to a variety of web hosts
""",
        suggest_on_error=True,
    )

    subs = parser.add_subparsers(dest="command", required=True)

    p_login = subs.add_parser(
        "login",
        help="Log in to a provider",
        suggest_on_error=True,
        description="""
Log in to a provider.

Any of the following forms are allowed:
* Just a name (tea)
* A URL stub (tea:, tea://)
* A URL base (tea://mysite.example)

Note that support for multiple credentials to the same provider will vary.
""",
    )
    p_login.add_argument("url", type=httpx.URL, help="URL to log in to")

    p_get = subs.add_parser(
        "get",
        suggest_on_error=True,
        help="Download a file",
        description="""
Download a file.

Both the source and the destination must include the file name.
""",
    )
    p_get.add_argument("src", type=httpx.URL, help="URL to read from")
    p_get.add_argument("dest", type=anyio.Path, help="Path to write to")

    p_put = subs.add_parser(
        "put",
        suggest_on_error=True,
        help="Upload a file",
        description="""
Upload a file

Both the source and the destination must include the file name.
""",
    )
    p_put.add_argument("src", type=anyio.Path, help="Path to read from")
    p_put.add_argument("dest", type=httpx.URL, help="URL to write to")

    p_sync = subs.add_parser(
        "sync",
        suggest_on_error=True,
        help="Synchronize one directory to another",
        description="""
Synchronize one directory to another.

No implicit names are added to the end of the destination path.
""",
    )
    p_sync.add_argument("src", type=_path_or_url, help="Path or URL to read from")
    p_sync.add_argument("dest", type=_path_or_url, help="URL or Path to write to")
    p_sync.add_argument(
        "--exclude",
        action="append",
        dest="exclusions",
        metavar="PATH",
        default=[ExcludeSpecial.Default],
        help="Exclude the given file/directory",
    )
    # p_sync.add_argument("--ignore-file", action="append", dest="exclusions", metavar="PATH", type=anyio.Path, help="Read and use an ignore file")
    p_sync.add_argument(
        "--exclude-nothing",
        action="append_const",
        dest="exclusions",
        const=ExcludeSpecial.Nothing,
        help="Disable exclusions, including implied ones",
    )

    pargs = parser.parse_args(args)
    return T.cast(CliArgs, pargs)


scr.registry.register_factory(CliArgs, parse_args)


async def do_login(svc: scr.Container):
    args = await svc.aget(CliArgs)
    if not args.url.scheme:
        assert not args.url.host
        args.url = httpx.URL(scheme=args.url.path)

    async with get_backend(args, args.url) as backend:
        # Check if credentials exist, and warn if they do
        try:
            have_creds_already = await backend.check_credentials(args.url)
        except* NoCredentialsFound:
            pass
        else:
            if have_creds_already:
                LOG.warning("Already have credentials for %s; overwriting", args.url)

        await backend.prompt_for_credentials(args.url)


async def do_get(svc: scr.Container):
    args = await svc.aget(CliArgs)
    usrc = T.cast(httpx.URL, args.src)
    pdest = T.cast(anyio.Path, args.dest)
    async with get_backend(args, usrc) as backend:
        await backend.get_to_file(usrc, pdest)


async def do_put(svc: scr.Container):
    args = await svc.aget(CliArgs)
    src = T.cast(Path, args.src)
    dest = T.cast(httpx.URL, args.dest)
    async with get_backend(args, dest) as backend:
        await backend.put_from_file(src, dest)


async def do_sync(svc: scr.Container):
    args = await svc.aget(CliArgs)
    if isinstance(args.src, httpx.URL):
        surl: httpx.URL = args.src
        sbe = get_backend(args, surl)
    else:
        sbe = None

    if isinstance(args.dest, httpx.URL):
        durl: httpx.URL = args.dest
        dbe = get_backend(args, durl)
    else:
        dbe = None

    if sbe is not None and dbe is not None:
        sys.exit("One of source or destination must be a local path")
    elif sbe is None and dbe is None:
        sys.exit("One of source or destination must be a remote path")
    elif sbe is None:
        async with T.cast(Backend, dbe):
            await T.cast(Backend, dbe).rsync_up(
                T.cast(Path, args.src), durl, delete=True
            )
    elif dbe is None:
        async with T.cast(Backend, sbe):
            await T.cast(Backend, sbe).rsync_down(
                surl, T.cast(Path, args.dest), delete=True
            )
    else:
        assert False, "Shouldn't get here"


def flatten_excetions[E: Exception](grp: ExceptionGroup[E]) -> T.Iterable[E]:
    for exc in grp.exceptions:
        if isinstance(exc, ExceptionGroup):
            yield from flatten_excetions(exc)
        else:
            yield exc


async def main():
    async with scr.ainit():
        args = await scr.root.aget(CliArgs)

        retval = 0
        try:
            async with enter_container(args):
                if args.command == "login":
                    await do_login(scr.root)
                elif args.command == "get":
                    await do_get(scr.root)
                elif args.command == "put":
                    await do_put(scr.root)
                elif args.command == "sync":
                    await do_sync(scr.root)
                else:
                    # FIXME: Print usage
                    sys.exit("No command specified")
        except* UnknownURLError as egrp:
            for uue in flatten_excetions(egrp):
                LOG.error("%s", str(uue.args[0]))
            del uue
            retval = 1
        except* NoCredentialsFound as egrp:
            for ncf in flatten_excetions(egrp):
                LOG.error("%s\nDid you need to use the login command?", ncf.args[0])
            del ncf
            retval = 1
        except* httpx.HTTPError as egrp:
            for rt in flatten_excetions(egrp):
                try:
                    rt.add_note(f"URL: {rt.request.url}")
                except RuntimeError:
                    # Request property has not been set
                    pass
            del rt
            raise
        except* KeyboardInterrupt:
            retval = 1
        sys.exit(retval)


def entrypoint():
    logging.config.dictConfig(
        {
            "version": 1,
            "incremental": False,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"format": "%(message)s"},
            },
            "handlers": {
                "default": {
                    "level": "NOTSET",
                    "formatter": "standard",
                    "class": "rich.logging.RichHandler",
                    "rich_tracebacks": True,  # TODO: Only in development
                    "console": rich.console.Console(stderr=True),
                },
            },
            "root": {"handlers": ["default"], "level": "INFO", "propagate": True},
            "loggers": {
                __name__: {
                    "handlers": ["default"],
                    "level": "DEBUG",
                    "propagate": False,
                },
                "httpx": {
                    # INFO spews all requests
                    "level": "WARNING",
                },
            },
        }
    )
    anyio.run(main, backend="trio")
