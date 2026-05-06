from pathlib import Path
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

    dst_path = tmp_path / "inner"

    for src_file in (PROJECT / "test-site" / "inner").iterdir():
        if not src_file.is_file():
            continue
        dest_file = dst_path / src_file.relative_to(PROJECT / "test-site")
        assert src_file.read_text() == dest_file.read_text()
