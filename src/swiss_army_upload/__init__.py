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

from .backends import get_backend, UnknownURLError, NoCredentialsFound
from .deps import enter_container


LOG = logging.getLogger(__name__)


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
        if await backend.is_file(args.src):
            await backend.get_to_file(args.src, args.dest)
        else:
            LOG.error("Not a file: %s", args.src)


async def do_put(args: PutCmd):
    async with get_backend(args, args.dest) as backend:
        await backend.put_from_file(args.src, args.dest)


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
