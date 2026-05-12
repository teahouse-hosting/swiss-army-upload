from anyio import Path
from httpx import URL
import pytest

from swiss_army_upload import ExcludeSpecial
from swiss_army_upload.junk_drawer.ignores import IgnoreEngine


async def test_defaults():
    ie = await IgnoreEngine.from_args([ExcludeSpecial.Default])
    assert ie(Path("index.html"))
    assert ie(Path("foo/bar.txt"))
    assert not ie(Path(".git"))
    assert ie(URL("http://site/index.html"))
    assert not ie(URL("http://site/spam/eggs/.gitignore"))


async def test_globs():
    ie = await IgnoreEngine.from_args([ExcludeSpecial.Default, "*.no"])
    assert ie(Path("foo.html"))
    assert not ie(Path("bar.no"))
    assert ie(Path("dir/foo.html"))
    assert not ie(Path("dir/bar.no"))
    assert ie(URL("http://site/foo.html"))
    assert not ie(URL("http://site/bar.no"))
    assert ie(URL("http://site/dir/foo.html"))
    assert not ie(URL("http://site/dir/bar.no"))


async def test_nothing():
    ie = await IgnoreEngine.from_args(
        [ExcludeSpecial.Default, "*.no", ExcludeSpecial.Nothing]
    )

    assert not ie.rules

    assert ie(Path("foo/bar.txt"))
    assert ie(Path(".git"))
    assert ie(URL("http://site/index.html"))
    assert ie(URL("http://site/spam/eggs/.gitignore"))
    assert ie(Path("foo.html"))
    assert ie(Path("bar.no"))
    assert ie(Path("dir/foo.html"))
    assert ie(Path("dir/bar.no"))
    assert ie(URL("http://site/foo.html"))
    assert ie(URL("http://site/bar.no"))
    assert ie(URL("http://site/dir/foo.html"))
    assert ie(URL("http://site/dir/bar.no"))


@pytest.mark.parametrize(
    "remote_url",
    [
        "tea://jenny.teahouse/",
        # "pages://jenny.gitpages/",
    ],
)
async def test_resync_subdir(
    sau_cli, tmp_path_factory, remote_url, use_good_oidc, http_client
):
    src = tmp_path_factory.mktemp("src")
    dest = tmp_path_factory.mktemp("dest")
    # FIXME: Don't copy the entire project to test this

    (src / ".gitignore").touch()
    (src / ".git").mkdir()
    (src / ".git" / "stuff").write_text("yup i exist")

    await sau_cli(
        ["sync", str(src), f"{remote_url}"],
        check=True,
    )
    await sau_cli(["sync", remote_url, dest], check=True)

    assert not (dest / ".git").exists()
    assert not (dest / ".gitignore").exists()

    result_url = URL(remote_url).copy_with(scheme="https").join(".gitignore")

    resp = await http_client.get(result_url)
    assert resp.status_code == 404
