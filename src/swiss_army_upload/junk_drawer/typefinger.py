"""
Fingerprinting files to discover their type
"""

import mimetypes
import os
import sys

import anyio.to_thread

if sys.version_info >= (3, 13):
    guess_file_type = mimetypes.guess_file_type
else:
    guess_file_type = mimetypes.guess_type


async def fingerprint_file(path: os.PathLike | str) -> str:
    if not mimetypes.inited:
        await anyio.to_thread.run_sync(mimetypes.init)
    type, enc = guess_file_type(path, strict=False)
    # TODO: Do file contents fingerprinting
    if type is None:
        return "application/octet-stream"
    elif enc is None:
        return type
    else:
        return f"{type}; charset={enc}"
