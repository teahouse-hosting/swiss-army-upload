"""
Generic tests on single files
"""

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
    assert (tmp_path / "test.txt").read_text() == data


@pytest.mark.parametrize(
    "upload_url,result_url",
    [
        ("tea://alice.teahouse/file.txt", "https://alice.teahouse/file.txt"),
        # ("pages://alice.gitpages/file.txt", "https://alice.gitpages/file.txt"),
    ],
)
async def test_publishes(
    keyring, sau_cli, tmp_path, http_client, upload_url, result_url
):
    await keyring.set_password(
        "counter.teahouse.cafe", "alice@valid.test", "sweet little angel"
    )
    data = (
        "According to all known laws of aviation, there is no way a bee should be able to fly. "
        "Its wings are too small to get its fat little body off the ground. "
        "The bee, of course, flies anyway because bees don't care what humans think is impossible."
    )
    (tmp_path / "test.txt").write_text(data)
    await sau_cli(["put", tmp_path / "test.txt", upload_url], check=True)

    resp = await http_client.get(result_url)
    resp.raise_for_status()
    assert resp.text == data
