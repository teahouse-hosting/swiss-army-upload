from pathlib import Path
import shutil
import typing as T

import httpx
import pytest


PROJECT = Path(__file__).absolute().parent.parent


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://grace.teahouse/",
        # "pages://alice.gitpages/file.txt",
    ],
)
async def test_round_trip(sau_cli, tmp_path, remote_url, use_good_oidc):
    await sau_cli(["sync", str(PROJECT / "test-site"), remote_url], check=True)
    await sau_cli(["sync", remote_url, tmp_path], check=True)

    for src_file in (PROJECT / "test-site").iterdir():
        if not src_file.is_file():
            continue
        dest_file = tmp_path / src_file.relative_to(PROJECT / "test-site")
        assert src_file.read_text() == dest_file.read_text()


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://harriet.teahouse/",
        # "pages://alice.gitpages/file.txt",
    ],
)
async def test_empty_subdir(sau_cli, tmp_path, remote_url, use_good_oidc):
    await sau_cli(
        ["sync", str(PROJECT / "test-site" / "inner"), f"{remote_url}/inner"],
        check=True,
    )
    await sau_cli(["sync", remote_url, tmp_path], check=True)

    for src_file in (PROJECT / "test-site" / "inner").iterdir():
        if not src_file.is_file():
            continue
        dest_file = tmp_path / src_file.relative_to(PROJECT / "test-site")
        assert src_file.read_text() == dest_file.read_text()


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://irene.teahouse/",
        # "pages://alice.gitpages/file.txt",
    ],
)
async def test_resync_subdir(sau_cli, tmp_path, remote_url, use_good_oidc):
    await sau_cli(
        ["sync", str(PROJECT / "test-site" / "inner"), f"{remote_url}/inner"],
        check=True,
    )
    (PROJECT / "test-site" / "inner" / "generated.txt").write_text("A generated file")
    await sau_cli(
        ["sync", str(PROJECT / "test-site" / "inner"), f"{remote_url}/inner"],
        check=True,
    )
    # FIXME: Check that the first invocation uploaded test.html and the second uploaded generated.txt
    await sau_cli(["sync", remote_url, tmp_path], check=True)

    for src_file in (PROJECT / "test-site" / "inner").iterdir():
        if not src_file.is_file():
            continue
        dest_file = tmp_path / src_file.relative_to(PROJECT / "test-site")
        assert src_file.read_text() == dest_file.read_text()


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://lena.teahouse/",
        # "pages://lena.gitpages/",
    ],
)
async def test_modified_file(
    sau_cli, tmp_path_factory, remote_url, use_good_oidc, http_client
):
    src = tmp_path_factory.mktemp("src")
    dest = tmp_path_factory.mktemp("dest")

    result_url = httpx.URL(remote_url).copy_with(scheme="https").join("test.txt")

    (src / "test.txt").write_text("John Gaius")
    await sau_cli(
        ["sync", str(src), f"{remote_url}"],
        check=True,
    )

    resp = await http_client.get(result_url)
    resp.raise_for_status()
    assert resp.text == "John Gaius"

    (src / "test.txt").write_text("Judith Deuteros")
    await sau_cli(
        ["sync", str(src), f"{remote_url}"],
        check=True,
    )

    resp = await http_client.get(result_url)
    resp.raise_for_status()
    assert resp.text == "Judith Deuteros"

    await sau_cli(["sync", remote_url, dest], check=True)

    assert (dest / "test.txt").read_text() == "Judith Deuteros"


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://mel.teahouse/",
        # "pages://mel.gitpages/",
    ],
)
async def test_modified_headers(
    sau_cli, tmp_path_factory, remote_url, use_good_oidc, http_client
):
    src = tmp_path_factory.mktemp("src")
    result_url = httpx.URL(remote_url).copy_with(scheme="https").join("test.txt")

    (src / "test.txt").write_text("the horrors persist and so do i")
    (src / "_headers").write_text("""
/test.txt
    X-Foo: Bar
""")

    await sau_cli(
        ["sync", str(src), f"{remote_url}"],
        check=True,
    )

    resp = await http_client.get(result_url)
    resp.raise_for_status()
    assert resp.headers["X-Foo"] == "Bar"

    (src / "_headers").write_text("""
/test.txt
    X-Spam: Eggs
""")

    await sau_cli(
        ["sync", str(src), f"{remote_url}"],
        check=True,
    )

    resp = await http_client.get(result_url)
    resp.raise_for_status()
    assert resp.headers["X-Spam"] == "Eggs"


async def test_noop_teahouse(sau_cli, tmp_path, use_good_oidc):
    """
    Test that syncing the same data twice causes no work to be done.
    """
    remote_url = httpx.URL("tea://nat.teahouse/")
    src_dir = tmp_path / "test-site"

    # Set up a complex site

    shutil.copytree(PROJECT / "test-site", src_dir)
    (src_dir / "_headers").write_text("""
/index.html
   Content-Language: en
""")

    # Do the first sync
    await sau_cli(["sync", src_dir, str(remote_url)], check=True)

    # Copy/paste the teahouse sync implementation, so we can list what
    # operations it would run the second time.
    # FIXME: Do this better
    import anyio
    import scr
    from swiss_army_upload.backends import get_backend
    from swiss_army_upload.backends.teahouse import TeahouseSync, TeahouseBackend
    from swiss_army_upload.junk_drawer.ignores import IgnoreEngine
    from swiss_army_upload.junk_drawer import rsync

    async with scr.ainit(), get_backend(scr.root, remote_url) as thbe:
        ie = await thbe.scr.aget(IgnoreEngine)
        sync = TeahouseSync(T.cast(TeahouseBackend, thbe), ie)
        async with anyio.create_task_group() as tg:
            send, recv = anyio.create_memory_object_stream[rsync.Operation]()
            tg.start_soon(sync, anyio.Path(src_dir), remote_url, send)
            async with recv:
                ops = [op async for op in recv]

    # Actually check what operations would happen
    assert len(ops) == 0
