import contextlib
from http import HTTPStatus

import anyio
from aws_request_signer import AwsRequestSigner
import httpx
import handtruck

from . import Backend


SIGNER_ENV_MAP = {
    "AWS_ACCESS_KEY_ID": "access_key_id",
    # "AWS_ENDPOINT_URL_S3": ...,
    "AWS_REGION": "region",
    "AWS_SECRET_ACCESS_KEY": "secret_access_key",
    "AWS_SESSION_TOKEN": "session_token",
    # "BUCKET_NAME": ...,
}


class TeahouseCredentials(
    handtruck.credentials.AbstractCredentials, anyio.AsyncContextManagerMixin
):
    taskgroup: anyio.TaskGroup
    bucket: str
    endpoint: str | httpx.URL

    def __init__(self, domain: str):
        self.domain = domain
        self._client = (
            httpx.AsyncClient()
        )  # FIXME: Use global client that does API credentials
        self.refresh_lock: anyio.Lock = anyio.Lock()
        self._signer: AwsRequestSigner | None = None

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self):
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
        while True:
            async with self.refresh_lock:
                resp = await self._client.post(
                    "https://counter.teahouse.cafe/upload/get-s3-config",
                    json={"domain": self.domain},
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
    _http: httpx.AsyncClient
    _client: handtruck.S3Client

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self):
        async with httpx.AsyncClient() as self._http:
            yield self

    async def _munge_url(self, url: httpx.URL) -> tuple[handtruck.S3Client, httpx.URL]:
        creds = TeahouseCredentials(url.host)
        client = handtruck.S3Client(
            url=creds.endpoint, client=self._http, credentials=creds
        )
        return client, httpx.URL(url, host=creds.bucket, scheme="s3")

    async def is_file(self, url: httpx.URL):
        assert url.scheme == "tea"
        client, s3url = await self._munge_url(url)
        resp = await client.head(s3url)
        if resp.status_code == HTTPStatus.OK:
            return True
        elif resp.status_code == HTTPStatus.NOT_FOUND:
            return False
        else:
            resp.raise_for_status()
