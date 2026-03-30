import http.cookiejar
import subprocess
import sys

import httpx
import pytest
import scr

import mock_servers.teahouse
import swiss_army_upload
from swiss_army_upload.junk_drawer.keyring import AsyncKeyring
from mockring import MockKeyring


@pytest.fixture(scope="session")  # Gotta redefine this at the session level
def anyio_backend():
    # We only care about the trio backend for now
    return "trio"


@pytest.fixture(scope="session", autouse=True)
async def http_client(tmp_path_factory, anyio_backend):
    jar = swiss_army_upload.junk_drawer.cookiejar.SecureSavedJar(
        tmp_path_factory.mktemp("cookies") / "cookies.blob"
    )
    client = httpx.AsyncClient(
        http2=True,
        cookies=jar,
        headers={"User-Agent": "swiss-army-upload/0.0.0"},
        follow_redirects=False,  # This causes complications in implementing auth code
        mounts={
            # "all://*.gitpages": ...,
            # "all://*.teahouse": ...,
            "all://counter.teahouse.cafe": httpx.ASGITransport(
                app=mock_servers.teahouse.app
            )
        },
    )
    async with jar, client:
        scr.registry.register_value(http.cookiejar.CookieJar, jar)
        scr.registry.register_value(httpx.AsyncClient, client)
        yield client


@pytest.fixture(autouse=True)
async def keyring():
    ring = MockKeyring()
    scr.registry.register_value(AsyncKeyring, ring, enter=False)
    return keyring


@pytest.fixture
async def sau_cli():
    """
    Invoke swiss-army-upload
    """

    # FIXME: Implement more of the subprocess interface
    async def invoke(argv: list[str]) -> subprocess.CompletedProcess:
        import scr

        # Caught a bug in saucer, which was annoying to diagnose from here, so
        # Jamie's leaving this.
        assert scr.registry._services

        # Because https://github.com/pathunstrom/dykes/issues/31
        sys.argv[:] = ["swiss-army-upload", *map(str, argv)]
        try:
            await swiss_army_upload.main()
        except SystemExit as exc:
            return subprocess.CompletedProcess(
                argv, exc.code if isinstance(exc.code, int) else int(bool(exc.code))
            )
        else:
            return subprocess.CompletedProcess(argv, 0)

    return invoke
