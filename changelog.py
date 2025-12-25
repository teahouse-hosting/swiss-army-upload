"""
Generate changelog from forge releases

Based on https://keepachangelog.com/en/1.1.0/
"""

import httpx


PREAMBLE = """# Changelog

"""

with httpx.Client(http2=True) as http, open("CHANGELOG.md", "wt") as changefile:
    changefile.write(PREAMBLE)

    resp = http.get(
        "https://codeberg.org/api/v1/repos/teahouse/swiss-army-upload/releases"
    )
    resp.raise_for_status()
    releases = resp.json()

    # TODO: Sort releases

    for release in releases:
        # TODO: Handle drafts, prereleases
        # FIXME: Only use date from published_at
        print(
            f"## [{release['tag_name']}] - {release["published_at"]}", file=changefile
        )
        print("", file=changefile)
        changefile.write(release["body"])
        print("", file=changefile)
        print("", file=changefile)
