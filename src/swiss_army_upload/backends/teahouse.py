import contextlib
from http import HTTPStatus
import http.cookiejar
import logging
import os

import anyio
from aws_request_signer import AwsRequestSigner
import httpx
import handtruck
import rich.console
from rich.prompt import Prompt
import scr

from . import Backend, InvalidCredentials, UnknownSite, NoCredentialsFound

# from ..junk_drawer.github import github_oidc
from ..junk_drawer.keyring import AsyncKeyring


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
            # Check if we're in github and there's an OIDC token
            # FIXME: Reimplement github_oidc() in an async-friendly way
            oidc = None  # yield from github_oidc()
            if oidc is not None:
                LOG.debug("Got OIDC")
                # There is an OIDC token, use that and stash it for later.
                # We don't need to cache this because the actions environment is
                # ephemeral and github wants us to do it more.
                self.token = oidc
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
                                "Invalid credentials for ... at Teahouse"
                            ) from exc
                        elif 300 <= exc.response.status_code < 400:
                            # Successful, actually
                            pass
                        else:
                            raise exc
                    httpx.Cookies(cookiejar).set_cookie_header(request=request)
                    yield request
                else:
                    raise NoCredentialsFound(
                        "Could not find credentials for counter.teahouse.cafe"
                    )


def _get_auth(svcs_container):
    return TeahouseAuth(svcs_container)


scr.registry.register_factory(TeahouseAuth, _get_auth, enter=False)


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
        async with anyio.create_task_group() as self.taskgroup:
            await self.taskgroup.start(
                self._refresher, name="TeahouseCredentials-refresher"
            )
            yield self
            self.taskgroup.cancel_scope.cancel()

    def __bool__(self) -> bool:
        return self._signer is not None

    async def _refresher(
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


class TeahouseBackend(anyio.AsyncContextManagerMixin, Backend):
    _client: handtruck.S3Client

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self):
        self.exitstack = contextlib.AsyncExitStack()
        async with self.exitstack:
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
        creds = await self.exitstack.enter_async_context(
            TeahouseCredentials(self.scr, url.host)
        )
        client = handtruck.S3Client(url=creds.endpoint, client=http, credentials=creds)
        return client, str(httpx.URL(url, host=creds.bucket, scheme="https"))

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
        raise NotImplementedError
