async def test_usage(sau_cli):
    proc = await sau_cli([])

    # FIXME: check output
    assert proc.returncode != 0


async def test_help(sau_cli):
    proc = await sau_cli(["--help"])

    # FIXME: check output
    assert proc.returncode == 0
