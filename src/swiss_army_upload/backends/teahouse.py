from __future__ import annotations

import contextlib
from http import HTTPStatus
import http.cookiejar
import logging
import os
import time
import typing as T

import anyio
from aws_request_signer import AwsRequestSigner
from httpdate import httpdate_to_unixtime
import httpx
import handtruck
import rich.console
from rich.prompt import Prompt
import scr

from . import Backend, InvalidCredentials, UnknownSite, NoCredentialsFound

# from ..junk_drawer.github import github_oidc
from ..junk_drawer.keyring import AsyncKeyring
from ..junk_drawer import rsync
from ..junk_drawer.sync import sync_to_async
from ..junk_drawer.oidc import oidc_tool
from ..junk_drawer.typefinger import fingerprint_file


LOG = logging.getLogger(__name__)


SIGNER_ENV_MAP = {
    "AWS_ACCESS_KEY_ID": "access_key_id",
    # "AWS_ENDPOINT_URL_S3": ...,
    "AWS_REGION": "region",
    "AWS_SECRET_ACCESS_KEY": "secret_access_key",
    "AWS_SESSION_TOKEN": "session_token",
    # "BUCKET_NAME": ...,
}


class TeahouseAuth(httpx.Auth):
    token: str | None = None

    requires_response_body = True

    def __init__(self, saucer: scr.Container):
        self.scr = saucer

    def asking_for_auth(self, resp: httpx.Response) -> bool:
        """
        Check if a response is a prompt for authentication
        """
        # This should be what we get as an API client
        if resp.status_code == 403:
            return True
        # Buuut this hasn't been implemented in the general case yet
        elif resp.url.path == "/auth/login/":  # If redirects were followed
            return True
        elif 300 <= resp.status_code < 400:  # If not
            loc = resp.url.join(resp.headers["Location"])
            return loc.path == "/auth/login/"
        else:
            return False

    async def async_auth_flow(self, request: httpx.Request):
        # Requests only receive cookies at initial creation. If cookies are
        # updated, headers need to be reset.
        cookiejar = await self.scr.aget(http.cookiejar.CookieJar)

        httpx.Cookies(cookiejar).set_cookie_header(request=request)
        # If we've stashed a token, reuse that
        if self.token is not None:
            request.headers["Authorization"] = f"Bearer {self.token}"

        # Attempt the main request
        resp = yield request

        if self.asking_for_auth(resp):
            # Check if we're in CI and there's an OIDC token
            if (oidc := oidc_tool()) is not None:
                async for req in oidc:
                    resp = yield req
                    await oidc.asend(resp)

            if oidc:
                LOG.debug("Got OIDC")
                # There is an OIDC token, use that and stash it for later.
                # We don't need to cache this because the actions environment is
                # ephemeral and github wants us to do it more.
                self.token = oidc.token
                request.headers["Authorization"] = f"Bearer {self.token}"
                yield request
            else:
                # No token, do user/pass auth with cookies
                # (Cookies are implicitly saved by the global client)
                # TODO: Allow site-specific credentials
                keyring: AsyncKeyring = await self.scr.aget(AsyncKeyring)  # type: ignore
                cred = await keyring.get_credential("counter.teahouse.cafe", None)
                if cred is not None:
                    resp = yield httpx.Request(
                        "POST",
                        "https://counter.teahouse.cafe/auth/login/",
                        json={"email": cred.username, "password": cred.password},
                        headers={"Accept": "application/json"},
                    )
                    try:
                        resp.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 400:
                            raise InvalidCredentials(
                                f"Invalid credentials for {request.url.host} at Teahouse"
                            ) from exc
                        elif 300 <= exc.response.status_code < 400:
                            # Successful, actually
                            pass
                        else:
                            raise exc
                    # Requests only receive cookies at initial creation
                    httpx.Cookies(cookiejar).set_cookie_header(request=request)
                    yield request
                else:
                    raise NoCredentialsFound(
                        "Could not find credentials for counter.teahouse.cafe"
                    )


def _get_auth(svcs_container):
    return TeahouseAuth(svcs_container)


scr.registry.register_factory(TeahouseAuth, _get_auth, enter=False)


class TeahouseCredentials(handtruck.credentials.AbstractCredentials):
    taskgroup: anyio.abc.TaskGroup
    bucket: str
    endpoint: str | httpx.URL

    def __init__(self, scr: scr.Container, domain: str):
        self._scr = scr
        self.domain = domain
        self.refresh_lock: anyio.Lock = anyio.Lock()
        self._signer: AwsRequestSigner | None = None

    def __bool__(self) -> bool:
        return self._signer is not None

    async def refresh_task(
        self, *, task_status: anyio.abc.TaskStatus[None] = anyio.TASK_STATUS_IGNORED
    ) -> None:
        http, auth = await self._scr.aget(httpx.AsyncClient, TeahouseAuth)
        while True:
            async with self.refresh_lock:
                resp = await http.post(
                    "https://counter.teahouse.cafe/upload/get-s3-config",
                    json={"domain": self.domain},
                    auth=auth,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    envvars = resp.json()
                    self._signer = AwsRequestSigner(
                        service="s3",
                        **{
                            SIGNER_ENV_MAP[key]: value
                            for key, value in envvars.items()
                            if key in SIGNER_ENV_MAP
                        },
                    )
                    self.endpoint = envvars.get("AWS_ENDPOINT_URL_S3", None)
                    self.bucket = envvars.get("BUCKET_NAME", None)
                else:
                    try:
                        resp.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 400:
                            raise UnknownSite(
                                f"Domain {self.domain} not recognized"
                            ) from exc
                        else:
                            raise exc
                    else:
                        raise RuntimeError("Unhandled status")
                task_status.started()
                sleep_time = 3600
            await anyio.sleep(sleep_time)

    @property
    def signer(self) -> AwsRequestSigner:
        if not self._signer:
            raise RuntimeError(
                f"{self.__class__.__name__} must be started before using",
            )
        return self._signer


class CredCache(anyio.AsyncContextManagerMixin):
    """
    Owns the credential instances and manages their tasks.

    This exists because juggling structural tasks is as subtle as a wizard
    dragon.
    """

    # Do not meddle in the affairs of wizards, for they are subtle and quick to anger.
    # Do not meddle in the affairs of dragons for you are crunchy and taste good with ketchup.
    # Jamie had a lot of trouble getting trio happy with refresh tasks, even
    # before weakrefs, so now this exists.

    creds: dict[str, TeahouseCredentials]

    def __init__(self, scr: scr.Container):
        self._scr = scr
        self.creds = {}

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self):
        # This task group owns all the refresh tasks
        async with anyio.create_task_group() as self.taskgroup:
            yield self
            self.taskgroup.cancel_scope.cancel()

    async def get(self, domain: str) -> TeahouseCredentials:
        """
        Get a credentials for the given domain.

        Might be a new or existing instance.
        """
        # This can be called from any task
        if domain not in self.creds:
            self.creds[domain] = cred = TeahouseCredentials(self._scr, domain)
            await self.taskgroup.start(
                cred.refresh_task, name=f"TeahouseCredentials-refresher-{domain}"
            )
        # Jamie thinks there's a race condition, where if two tasks ask for the
        # same credentials at the same time, one of them will get the instance
        # while it's semi-initialized.
        return self.creds[domain]


class TeahouseSync(rsync.SyncEngine):
    # There aren't additional attributes we can get without just downloading the file
    attrs_to_get = []

    def __init__(self, backend: TeahouseBackend):
        self.backend = backend

    async def _munge_url(self, url: httpx.URL) -> tuple[handtruck.S3Client, str]:
        return await self.backend._munge_url(url)

    async def iter_remote(
        self,
        url: httpx.URL,
        stream: anyio.abc.UnreliableObjectSendStream[rsync.RFileMeta],
    ):
        """
        Produce the list of files on the remote.

        Only populate metadata fields that are free.
        """
        async with stream:
            client, path = await self._munge_url(url)
            async for page in client.list_objects_v2(path):
                for meta in page:
                    await stream.send(
                        rsync.RFileMeta(
                            name=meta.key,
                            size=meta.size,
                            mtime=meta.last_modified,
                        )
                    )

    async def fill_remote_meta(
        self, url: httpx.URL, meta: rsync.RFileMeta, field_hints: list[str]
    ):
        # There's no fields we could query extra for
        return


class TeahouseBackend(anyio.AsyncContextManagerMixin, Backend):
    _creds: CredCache

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self):
        async with CredCache(self.scr) as self._creds:
            yield self

    async def check_credentials(self, url: httpx.URL) -> bool:
        http, auth = await self.scr.aget(httpx.AsyncClient, TeahouseAuth)
        # whoami will never ask for auth, so we gotta hit something else to force it
        resp = await http.get(
            "https://counter.teahouse.cafe/user/",
            auth=auth,
            headers={"Accept": "application/json"},
        )
        # Find out who we auth'd as
        resp = await http.get(
            "https://counter.teahouse.cafe/auth/whoami/",
            auth=auth,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        body = resp.json()
        LOG.debug("whoami: %r", body)
        return body["is_authenticated"]

    async def prompt_for_credentials(self, url: httpx.URL):
        console = await self.scr.aget(rich.console.Console)
        keyring: AsyncKeyring = await self.scr.aget(AsyncKeyring)  # type: ignore

        if url.host:
            # Should this by run through logging, or displayed as UI?
            console.print(
                "swiss-army-upload currently does not support multiple Teahouse logins"
            )

        credentials_ok = False
        while not credentials_ok:
            # These do block the event loop, but maybe that's ok?
            email = Prompt.ask("Teahouse email", console=console)
            password = Prompt.ask("Teahouse password", password=True, console=console)

            # FIXME: Try credentials before saving them
            await keyring.set_password("counter.teahouse.cafe", email, password)

            credentials_ok = await self.check_credentials(url)
            if not credentials_ok:
                console.print("Unable to confirm credentials; try again")

    async def _munge_url(self, url: httpx.URL) -> tuple[handtruck.S3Client, str]:
        http = await self.scr.aget(httpx.AsyncClient)
        creds = await self._creds.get(url.host)
        client = handtruck.S3Client(url=creds.endpoint, client=http, credentials=creds)
        if url.path == "/":
            return client, creds.bucket
        else:
            return client, f"{creds.bucket}/{url.path.lstrip('/')}"

    async def is_file(self, url: httpx.URL) -> bool:
        assert url.scheme == "tea"
        client, s3url = await self._munge_url(url)
        resp = await client.head(s3url)
        if resp.status_code == HTTPStatus.OK:
            return True
        elif resp.status_code == HTTPStatus.NOT_FOUND:
            return False
        else:
            resp.raise_for_status()
            raise RuntimeError("Unhandled status")

    async def get_to_file(self, url: httpx.URL, file: os.PathLike | str):
        client, s3url = await self._munge_url(url)
        await client.get_file_parallel(s3url, os.fspath(file))
        # FIXME: Grab a modified time from one of the download requests
        resp = await client.head(s3url)
        mtime = httpdate_to_unixtime(resp.headers["Last-Modified"])
        await sync_to_async(os.utime)(file, (time.time(), mtime))

    async def put_from_file(self, file: os.PathLike | str, url: httpx.URL):
        client, s3url = await self._munge_url(url)
        headers = {"Content-Type": await fingerprint_file(file)}
        await client.put_file_multipart(s3url, os.fspath(file), headers=headers)

    async def _delete_object(self, url: httpx.URL):
        client, s3url = await self._munge_url(url)
        await client.delete(s3url)

    async def rsync_up(self, src: os.PathLike | str, dest: httpx.URL, *, delete: bool):
        sync = TeahouseSync(self)
        async with anyio.create_task_group() as tg:
            send, recv = anyio.create_memory_object_stream[rsync.Operation]()
            tg.start_soon(sync, anyio.Path(src), dest, send)
            async with recv:
                async for op in recv:
                    match op:
                        case rsync.Operation(op=rsync.Op.CREATE, src=osrc, dest=odest):
                            posrc = T.cast(anyio.Path, osrc)
                            uodest = T.cast(httpx.URL, odest)
                            tg.start_soon(self.put_from_file, posrc, uodest)
                        case rsync.Operation(op=rsync.Op.UPDATE, src=osrc, dest=odest):
                            posrc = T.cast(anyio.Path, osrc)
                            uodest = T.cast(httpx.URL, odest)
                            tg.start_soon(self.put_from_file, posrc, uodest)
                        case rsync.Operation(op=rsync.Op.DELETE, dest=odest):
                            uodest = T.cast(httpx.URL, odest)
                            tg.start_soon(self._delete_object, uodest)
                        case _:
                            raise NotImplementedError(op)

    async def rsync_down(
        self, src: httpx.URL, dest: os.PathLike | str, *, delete: bool
    ):
        pdest = anyio.Path(dest)
        await pdest.mkdir(exist_ok=True, parents=True)
        sync = TeahouseSync(self)
        async with anyio.create_task_group() as tg:
            send, recv = anyio.create_memory_object_stream[rsync.Operation]()
            tg.start_soon(sync, src, pdest, send)
            async with recv:
                async for op in recv:
                    match op:
                        case rsync.Operation(op=rsync.Op.CREATE, src=osrc, dest=odest):
                            uosrc = T.cast(httpx.URL, osrc)
                            podest = T.cast(anyio.Path, odest)
                            await podest.parent.mkdir(exist_ok=True, parents=True)
                            tg.start_soon(self.get_to_file, uosrc, podest)
                        case rsync.Operation(op=rsync.Op.UPDATE, src=osrc, dest=odest):
                            uosrc = T.cast(httpx.URL, osrc)
                            podest = T.cast(anyio.Path, odest)
                            tg.start_soon(self.get_to_file, uosrc, podest)
                        case rsync.Operation(op=rsync.Op.DELETE, dest=odest):
                            podest = T.cast(anyio.Path, odest)
                            tg.start_soon(podest.unlink)
                        case _:
                            raise NotImplementedError(op)
