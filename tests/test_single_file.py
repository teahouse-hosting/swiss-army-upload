"""
Generic tests on single files
"""

import random

import pytest


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://alice.teahouse/file.txt",
        # "pages://alice.gitpages/file.txt",
    ],
)
async def test_round_trip(keyring, sau_cli, remote_url, tmp_path):
    await keyring.set_password(
        "counter.teahouse.cafe", "alice@valid.test", "sweet little angel"
    )
    data = (
        "According to all known laws of aviation, there is no way a bee should be able to fly. "
        "Its wings are too small to get its fat little body off the ground. "
        "The bee, of course, flies anyway because bees don't care what humans think is impossible."
    )
    (tmp_path / "test.txt").write_text(data)
    await sau_cli(["put", tmp_path / "test.txt", remote_url], check=True)
    await sau_cli(["get", remote_url, tmp_path / "download.txt"], check=True)
    assert (tmp_path / "download.txt").read_text() == data


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://clarice.teahouse/file.txt",
        # "pages://clarice.gitpages/file.txt",
    ],
)
async def test_round_trip_large(keyring, sau_cli, remote_url, tmp_path):
    await keyring.set_password(
        "counter.teahouse.cafe", "alice@valid.test", "sweet little angel"
    )
    with (tmp_path / "large.bin").open("wb") as fobj:
        # Write out 10MB
        for _ in range(1_000):
            fobj.write(random.randbytes(10_000))

    await sau_cli(["put", tmp_path / "large.bin", remote_url], check=True)
    await sau_cli(["get", remote_url, tmp_path / "download.bin"], check=True)
    assert (tmp_path / "large.bin").read_bytes() == (
        tmp_path / "download.bin"
    ).read_bytes()


@pytest.mark.parametrize(
    "upload_url,result_url",
    [
        ("tea://beth.teahouse/file.txt", "https://beth.teahouse/file.txt"),
        # ("pages://beth.gitpages/file.txt", "https://beth.gitpages/file.txt"),
    ],
)
async def test_publishes(
    keyring, sau_cli, tmp_path, http_client, upload_url, result_url
):
    await keyring.set_password(
        "counter.teahouse.cafe", "alice@valid.test", "sweet little angel"
    )
    data = "Hope is a discipline. It requires that you not give in to despair. So I'm here to tell you: don't despair."
    (tmp_path / "published.txt").write_text(data)
    await sau_cli(["put", tmp_path / "published.txt", upload_url], check=True)

    resp = await http_client.get(result_url)
    resp.raise_for_status()
    assert resp.text == data
