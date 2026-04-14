async def test_oidc_put(tmp_path, sau_cli, use_good_oidc):
    remote_url = "tea://dani.teahouse/file.txt"
    data = "This place is a message... and part of a system of messages... pay attention to it!"
    (tmp_path / "test.txt").write_text(data)
    await sau_cli(["put", tmp_path / "test.txt", remote_url], check=True)
    await sau_cli(["get", remote_url, tmp_path / "download.txt"], check=True)
    assert (tmp_path / "download.txt").read_text() == data


async def test_bad_oidc(tmp_path, sau_cli, use_bad_oidc):
    remote_url = "tea://edna.teahouse/file.txt"
    data = "Sending this message was important to us. We considered ourselves to be a powerful culture."
    (tmp_path / "test.txt").write_text(data)
    proc = await sau_cli(["put", tmp_path / "test.txt", remote_url], check=False)

    assert proc.returncode


async def test_oidc_fallback(tmp_path, keyring, sau_cli, use_bad_oidc):
    await keyring.set_password(
        "counter.teahouse.cafe", "alice@valid.test", "sweet little angel"
    )
    remote_url = "tea://frankie.teahouse/file.txt"
    data = "This place is not a place of honor... no highly esteemed deed is commemorated here... nothing valued is here."
    (tmp_path / "test.txt").write_text(data)
    await sau_cli(["put", tmp_path / "test.txt", remote_url], check=True)
