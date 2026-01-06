"""
saucer/svcs definitions
"""

import httpx
import scr


async def build_client(svcs_container):
    return httpx.AsyncClient()


scr.registry.register_factory(httpx.AsyncClient, build_client, enter=True)
