import hashlib

import anyio


async def hash_stream(algo: str, stream: anyio.abc.ByteReceiveStream, **opts) -> bytes:
    """
    Reads a stream until EOF, hashing contents as it goes. The actual hash
    computation is done in another thread.

    Args:
        algo: Name of the :mod:`hashlib` algorithm to use
        stream: Data to hash
        opts: Additional flags to pass to hashlib (namely ``usedforsecurity``)

    Returns:
        The hash digest
    """
    hashobj = hashlib.new(algo, **opts)
    async with stream:
        async for chunk in stream:
            await anyio.to_thread.run_sync(hashobj.update, chunk)

    return await anyio.to_thread.run_sync(hashobj.digest)
