import contextlib
from http import HTTPStatus
import pathlib

import anyio
from aws_request_signer import AwsRequestSigner
import httpx
import handtruck
import scr

from . import Backend, InvalidCredentials, UnknownSite, NoCredentialsFound

# from ..junk_drawer.github import github_oidc
from ..junk_drawer.keyring import AsyncKeyring


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

    async def async_auth_flow(self, request):
        # If we've stashed a token, reuse that
        if self.token is not None:
            request.headers["Authorization"] = f"Bearer {self.token}"

        # Attempt the main request
        resp = yield request

        # Teahouse needs us to auth
        if resp.status_code == 403:
            # Check if we're in github and there's an OIDC token
            # FIXME: Reimplement github_oidc() in an async-friendly way
            oidc = None  # yield from github_oidc()
            if oidc is not None:
                # There is an OIDC token, use that and stash it for later.
                # We don't need to cache this because the actions environment is
                # ephemeral and github wants us to do it more.
                self.token = oidc
                request.headers["Authorization"] = f"Bearer {self.token}"
                yield request
            else:
                # No token, do user/pass auth with cookies
                # (Cookies are implicitly saved by the global client)
                # FIXME: Allow site-specific credentials
                keyring = await self.scr.aget(AsyncKeyring)
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
                                "Invalid credentials for ... at Teahouse"
                            ) from exc
                        else:
                            raise exc
                    yield request
                else:
                    raise NoCredentialsFound(
                        "Could not find credentials for counter.teahouse.cafe"
                    )


class TeahouseCredentials(
    handtruck.credentials.AbstractCredentials, anyio.AsyncContextManagerMixin
):
    taskgroup: anyio.abc.TaskGroup
    bucket: str
    endpoint: str | httpx.URL

    def __init__(self, scr: scr.Container, domain: str):
        self._scr = scr
        self.domain = domain
        self.refresh_lock: anyio.Lock = anyio.Lock()
        self._signer: AwsRequestSigner | None = None

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self):
        self._client = await self._scr.aget(httpx.AsyncClient)
        async with anyio.create_task_group() as self.taskgroup:
            await self.taskgroup.start(
                self._refresher, name="TeahouseCredentials-refresher"
            )
            yield self

    def __bool__(self) -> bool:
        return self._signer is not None

    async def _refresher(
        self, *, task_status: anyio.abc.TaskStatus[None] = anyio.TASK_STATUS_IGNORED
    ) -> None:
        auth = TeahouseAuth(self._scr)
        while True:
            async with self.refresh_lock:
                resp = await self._client.post(
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


class TeahouseBackend(anyio.AsyncContextManagerMixin, Backend):
    _client: handtruck.S3Client

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self):
        self.exitstack = contextlib.AsyncExitStack()
        async with self.exitstack:
            yield self

    async def _munge_url(self, url: httpx.URL) -> tuple[handtruck.S3Client, str]:
        http = await self.scr.aget(httpx.AsyncClient)
        creds = await self.exitstack.enter_async_context(
            TeahouseCredentials(self.scr, url.host)
        )
        client = handtruck.S3Client(url=creds.endpoint, client=http, credentials=creds)
        return client, str(httpx.URL(url, host=creds.bucket, scheme="s3"))

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

    async def get_to_file(self, url: httpx.URL, file: pathlib.Path | str):
        raise NotImplementedError
