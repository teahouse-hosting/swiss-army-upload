def test_usage(sau_cli):
    proc = sau_cli([])

    # FIXME: check output
    assert proc.returncode != 0


def test_help(sau_cli):
    proc = sau_cli(["--help"])

    # FIXME: check output
    assert proc.returncode == 0
