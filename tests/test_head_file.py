"""
Test _headers parsing.
"""

import re

import anyio
from anyio import create_memory_object_stream, create_task_group
from anyio.streams.text import TextReceiveStream
from httpx import Headers
import pytest

from swiss_army_upload.junk_drawer.headerfile import NetlifyHeaderFile, HeaderManager


async def test_symmetric_parsing(tmp_path):
    """
    Checks that loading from a stream and file are equivalent
    """
    data = b"""
# a path:
/templates/index.html
  # headers for that path:
  X-Frame-Options: DENY
# another path:
/templates/index2.html
  # headers for that path:
  X-Frame-Options: SAMEORIGIN
"""

    nhf1 = None
    bytes_send, bytes_receive = create_memory_object_stream[bytes](1)

    async def _send():
        async with bytes_send:
            await bytes_send.send(data)

    async def _recv():
        nonlocal nhf1
        async with TextReceiveStream(bytes_receive) as trs:
            nhf1 = await NetlifyHeaderFile.load(trs)

    async with create_task_group() as tg:
        tg.start_soon(_send)
        tg.start_soon(_recv)

    tmp_file = tmp_path / "_headers"
    tmp_file.write_bytes(data)
    nhf2 = await NetlifyHeaderFile.loadf(await anyio.open_file(tmp_file))

    nhf3 = NetlifyHeaderFile.loads(data.decode("utf-8"))

    assert nhf1._data == nhf2._data == nhf3._data


@pytest.mark.parametrize(
    "txt,result",
    [
        (
            """# a path:
/templates/index.html
  # headers for that path:
  X-Frame-Options: DENY
# another path:
/templates/index2.html
  # headers for that path:
  X-Frame-Options: SAMEORIGIN""",
            {
                "/templates/index.html": Headers({"X-Frame-Options": "DENY"}),
                "/templates/index2.html": Headers({"X-Frame-Options": "SAMEORIGIN"}),
            },
        ),
        (
            """/*
  cache-control: max-age=0
  cache-control: no-cache
  cache-control: no-store
  cache-control: must-revalidate""",
            {
                re.compile("/.*"): Headers(
                    [
                        ("cache-control", "max-age=0"),
                        ("cache-control", "no-cache"),
                        ("cache-control", "no-store"),
                        ("cache-control", "must-revalidate"),
                    ]
                )
            },
        ),
    ],
)
async def test_examples(txt, result):
    nhf = NetlifyHeaderFile.loads(txt)
    assert nhf._data == result


async def test_resolve():
    nhf = NetlifyHeaderFile.loads("""
/*
  cache-control: max-age=0
  cache-control: no-cache
  cache-control: no-store
  cache-control: must-revalidate
# a path:
/templates/index.html
  # headers for that path:
  X-Frame-Options: DENY
# another path:
/templates/index2.html
  # headers for that path:
  X-Frame-Options: SAMEORIGIN
""")

    assert nhf.resolve(anyio.Path("templates/index.html")) == Headers(
        [
            ("cache-control", "max-age=0"),
            ("cache-control", "no-cache"),
            ("cache-control", "no-store"),
            ("cache-control", "must-revalidate"),
            ("X-Frame-Options", "DENY"),
        ]
    )

    assert nhf.resolve(anyio.Path("templates/index2.html")) == Headers(
        [
            ("cache-control", "max-age=0"),
            ("cache-control", "no-cache"),
            ("cache-control", "no-store"),
            ("cache-control", "must-revalidate"),
            ("X-Frame-Options", "SAMEORIGIN"),
        ]
    )


async def test_multi_resolve(tmp_path):
    (tmp_path / "_headers").write_text("""
/templates/index.html
  # headers for that path:
  X-Frame-Options: DENY
/test.html
    Content-Type: text/html-plus
""")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "_headers").write_text("""
/index2.html
  # headers for that path:
  X-Frame-Options: SAMEORIGIN
/*
  cache-control: max-age=0
""")

    hm = HeaderManager()
    aio_path = anyio.Path(tmp_path)

    assert (await hm.resolve(aio_path / "test.html")) == Headers(
        {"Content-Type": "text/html-plus"}
    )
    assert (await hm.resolve(aio_path / "templates/index.html")) == Headers(
        {"X-Frame-Options": "DENY", "Cache-Control": "max-age=0"}
    )
    assert (await hm.resolve(aio_path / "templates/index2.html")) == Headers(
        {"X-Frame-Options": "SAMEORIGIN", "Cache-Control": "max-age=0"}
    )
