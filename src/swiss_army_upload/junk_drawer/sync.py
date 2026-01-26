"""
Handles sync/async concerns.
"""

import functools

import anyio.to_thread


def async_to_sync(func):
    @functools.wraps(func)
    def _(*p, **kw):
        return anyio.to_thread.run(lambda: func(*p, **kw))

    return _


def sync_to_async(func):
    @functools.wraps(func)
    def _(*p, **kw):
        return anyio.to_thread.run_sync(lambda: func(*p, **kw))

    return _
