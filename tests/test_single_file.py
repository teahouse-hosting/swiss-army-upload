"""
Generic tests on single files
"""

import pytest


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://alice.teahouse/file.txt",
        "pages://alice.gitpages/file.txt",
    ],
)
async def test_round_trip(sau_cli, remote_url, tmp_path):
    data = (
        "According to all known laws of aviation, there is no way a bee should be able to fly. "
        "Its wings are too small to get its fat little body off the ground. "
        "The bee, of course, flies anyway because bees don't care what humans think is impossible."
    )
    (tmp_path / "test.txt").write_text(data)
    await sau_cli(["put", tmp_path / "test.txt", remote_url])
    await sau_cli(["get", remote_url, tmp_path / "download.txt"])
    assert (tmp_path / "test.txt").read_text() == data
