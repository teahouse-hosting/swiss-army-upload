import http.cookiejar
import os
import subprocess
import sys
import typing as T

import httpx
import pytest
from pytest_ephemeral_container import spawn_container, discover_ports, wait_for_http
import scr

import mock_servers.teahouse
import swiss_army_upload
from swiss_army_upload.junk_drawer.keyring import AsyncKeyring
from mockring import MockKeyring


@pytest.fixture(scope="session")  # Gotta redefine this at the session level
def anyio_backend():
    # We only care about the trio backend for now
    return "trio"


@pytest.fixture(scope="session")
def _teahouse_s3():
    if "S3_ADDR" in os.environ:
        ip, _, sport = os.environ["S3_ADDR"].rpartition(":")
        port = int(sport)
        yield ip, port
    else:
        with spawn_container(
            # Pin to the non-licensed version of localstack
            # https://blog.localstack.cloud/the-road-ahead-for-localstack/
            image="docker.io/localstack/localstack@sha256:2c32486ed9ce66afbc6f8792dc6719a35890b454ecae7dc09eb9acecd057eda8",
            ports={
                "4566/tcp": None,
            },
            environment={
                # "LS_LOG": "trace-internal",
            },
        ) as container:
            ip, port = next(discover_ports(container, "4566/tcp"))  # type: ignore
            wait_for_http(ip, port)
            yield ip, port


@pytest.fixture(scope="session")
def _teahouse_objects_transport(_teahouse_s3):
    import httpcore._backends.auto

    class MockBackend(httpcore._backends.auto.AutoBackend):
        async def connect_tcp(
            self,
            host: str,
            port: int,
            timeout: float | None = None,
            local_address: str | None = None,
            socket_options: T.Iterable | None = None,
        ):
            host, port = _teahouse_s3
            return await super().connect_tcp(
                host, port, timeout, local_address, socket_options
            )

    class Transport(httpx.AsyncHTTPTransport):
        def __init__(self, *pargs, **kwargs):
            super().__init__(*pargs, **kwargs)
            self._pool._network_backend = MockBackend()
            self._pool._ssl_context = NotImplementedError("Tried to use ssl")  # type: ignore

    return Transport()


@pytest.fixture(scope="session", autouse=True)
async def http_client(
    tmp_path_factory, anyio_backend, _teahouse_objects_transport, _teahouse_s3
):
    jar = swiss_army_upload.junk_drawer.cookiejar.SecureSavedJar(
        tmp_path_factory.mktemp("cookies") / "cookies.blob"
    )
    mock_servers.teahouse.LOCALSTACK_ENDPOINT = _teahouse_s3
    client = httpx.AsyncClient(
        http2=True,
        cookies=jar,
        headers={"User-Agent": "swiss-army-upload/0.0.0"},
        follow_redirects=False,  # This causes complications in implementing auth code
        mounts={
            # "all://*.gitpages": ...,
            "all://*.teahouse": httpx.ASGITransport(app=mock_servers.teahouse.serv),
            "all://counter.teahouse.cafe": httpx.ASGITransport(
                app=mock_servers.teahouse.admin
            ),
            "all://objects.test": _teahouse_objects_transport,
        },
    )
    mock_servers.teahouse.http_client = client
    async with jar, client:
        scr.registry.register_value(http.cookiejar.CookieJar, jar)
        scr.registry.register_value(httpx.AsyncClient, client)
        yield client


@pytest.fixture(autouse=True)
async def keyring():
    ring = MockKeyring()
    scr.registry.register_value(AsyncKeyring, ring, enter=False)
    return ring


@pytest.fixture
async def sau_cli():
    """
    Invoke swiss-army-upload
    """

    # FIXME: Implement more of the subprocess interface
    async def invoke(
        argv: list[str], *, check: bool = False
    ) -> subprocess.CompletedProcess:
        import scr

        # Caught a bug in saucer, which was annoying to diagnose from here, so
        # Jamie's leaving this.
        assert scr.registry._services

        # Because https://github.com/pathunstrom/dykes/issues/31
        sys.argv[:] = ["swiss-army-upload", *map(str, argv)]
        cp: subprocess.CompletedProcess
        try:
            await swiss_army_upload.main()
        except SystemExit as exc:
            cp = subprocess.CompletedProcess(
                argv, exc.code if isinstance(exc.code, int) else int(bool(exc.code))
            )
        else:
            cp = subprocess.CompletedProcess(argv, 0)

        if check and cp.returncode:
            raise subprocess.CalledProcessError(
                cp.returncode, cp.args, output=None, stderr=None
            )

        return cp

    return invoke
