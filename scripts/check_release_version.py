"""Reject release tags that disagree with the package version before publication."""

import os
import runpy
from pathlib import Path


def main() -> None:
    if os.environ.get("GITHUB_EVENT_NAME") != "release":
        return
    root = Path(__file__).resolve().parents[1]
    version = runpy.run_path(str(root / "src/biblebot/__init__.py"))["__version__"]
    tag = os.environ.get("RELEASE_TAG", "")
    if tag.removeprefix("v") != version:
        raise SystemExit(
            f"Release tag {tag!r} does not match package version {version}"
        )


if __name__ == "__main__":
    main()
