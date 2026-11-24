import typing as T
import os

import pytest


def text_pipe() -> tuple[T.IO[str], T.IO[str]]:
    """
    Opens a pipe, wraps it in text stuff, and returns the writable and readable
    ends.
    """
    rfd, wfd = os.pipe()
    return os.fdopen(wfd, "wt"), os.fdopen(rfd, "rt")


@pytest.mark.timeout(5, func_only=True)
async def test_teahouse_good(sau_cli, monkeypatch):
    # FIXME: Replace all this with a rich.console.Console mock
    pipe_in, pipe_out = text_pipe()
    monkeypatch.setattr("sys.stdin", pipe_out)
    # Hoping the internal pipe buffer is bigger than this
    pipe_in.write("pearl@valid.test\n")
    pipe_in.close()

    def getpass(*p, **kw):
        return "do it for her"

    monkeypatch.setattr("getpass.getpass", getpass)
    monkeypatch.setattr("rich.console.getpass", getpass)

    proc = await sau_cli(["login", "tea://"])
    assert proc.returncode == 0
