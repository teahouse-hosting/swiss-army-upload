import subprocess
import sys

import anyio
import pytest

import swiss_army_upload


@pytest.fixture
def sau_cli():
    """
    Invoke swiss-army-upload
    """

    # FIXME: Implement more of the subprocess interface
    def invoke(argv: list[str]) -> subprocess.CompletedProcess:
        # Because https://github.com/pathunstrom/dykes/issues/31
        sys.argv[:] = ["swiss-army-upload"] + argv
        try:
            anyio.run(swiss_army_upload.main, backend="trio")
        except SystemExit as exc:
            return subprocess.CompletedProcess(argv, exc.code)
        else:
            return subprocess.CompletedProcess(argv, 0)

    return invoke
