# import httpx
# import handtruck

from . import Backend


class TeahouseBackend(Backend):
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass
