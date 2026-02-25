from dataclasses import dataclass
import logging
import logging.config
from pathlib import Path
import sys
import typing as T

import anyio
import dykes
import httpx
import rich.logging
import scr

from .backends import get_backend, UnknownURLError, NoCredentialsFound, Backend
from .deps import enter_container


LOG = logging.getLogger(__name__)


@dataclass
class LoginCmd:
    """
    Log in to a provider.

    Any of the following forms are allowed:
    * Just a name (tea)
    * A URL stub (tea:, tea://)
    * A URL base (tea://mysite.example)

    Note that support for multiple credentials to the same provider will vary.
    """

    url: T.Annotated[httpx.URL, "URL to log in to"]


@dataclass
class GetCmd:
    """
    Download a file.

    Both the source and the destination must include the file name.
    """

    src: T.Annotated[httpx.URL, "URL to read from"]
    dest: T.Annotated[Path, "Path to write to"]


@dataclass
class PutCmd:
    """
    Upload a file

    Both the source and the destination must include the file name.
    """

    src: T.Annotated[Path, "Path to read from"]
    dest: T.Annotated[httpx.URL, "URL to write to"]


@dataclass
class SyncCmd:
    """
    Synchronize one directory to another.

    No implicit names are added to the end of the destination path.
    """

    src: T.Annotated[str, "Path or URL to read from"]
    dest: T.Annotated[str, "URL or path to write to"]


@dataclass
class SAUArgs:
    """
    Upload to a variety of web hosts
    """

    login: dykes.Subparser[LoginCmd] = None
    get: dykes.Subparser[GetCmd] = None
    put: dykes.Subparser[PutCmd] = None
    sync: dykes.Subparser[SyncCmd] = None


async def do_login(args: LoginCmd):
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


async def do_get(args: GetCmd):
    async with get_backend(args, args.src) as backend:
        await backend.get_to_file(args.src, args.dest)


async def do_put(args: PutCmd):
    async with get_backend(args, args.dest) as backend:
        await backend.put_from_file(args.src, args.dest)


async def do_sync(args: SyncCmd):
    surl = httpx.URL(args.src)
    durl = httpx.URL(args.dest)
    try:
        sbe = get_backend(args, surl)
    except UnknownURLError:
        sbe = None

    try:
        dbe = get_backend(args, durl)
    except UnknownURLError:
        dbe = None

    if sbe is not None and dbe is not None:
        sys.exit("One of source or destination must be a local path")
    elif sbe is None and dbe is None:
        sys.exit("One of source or destination must be a remote path")
    elif sbe is None:
        async with T.cast(Backend, dbe):
            await T.cast(Backend, dbe).rsync_up(Path(args.src), durl, delete=True)
    elif dbe is None:
        async with T.cast(Backend, sbe):
            await T.cast(Backend, sbe).rsync_down(surl, Path(args.dest), delete=True)
    else:
        assert False, "Shouldn't get here"


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
            elif args.sync is not None:
                async with enter_container(args, args.sync):
                    await do_sync(args.sync)
            else:
                # FIXME: Print usage
                sys.exit("No command specified")
        except* UnknownURLError as egrp:
            for uue in egrp.exceptions:
                LOG.error("%s", str(uue.args[0]))
            del uue
            retval = 1
        except* NoCredentialsFound as egrp:
            for ncf in egrp.exceptions:
                LOG.error("%s\nDid you need to use the login command?", ncf.args[0])
            del ncf
            retval = 1
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
