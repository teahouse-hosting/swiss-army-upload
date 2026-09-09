from pathlib import Path

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


# TODO: Test that no changes cause no operations
