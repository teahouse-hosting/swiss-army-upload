"""
Fingerprinting files to discover their type
"""

import mimetypes
import os

import anyio.to_thread


async def fingerprint_file(path: os.PathLike | str) -> str:
    if not mimetypes.inited:
        await anyio.to_thread.run_sync(mimetypes.init)
    type, enc = mimetypes.guess_file_type(path, strict=False)
    # TODO: Do file contents fingerprinting
    if type is None:
        return "application/octet-stream"
    elif enc is None:
        return type
    else:
        return f"{type}; charset={enc}"
