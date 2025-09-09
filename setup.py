import os
import re

from setuptools import find_packages, setup

# Read version from __init__.py without importing the package
with open(
    os.path.join(os.path.dirname(__file__), "src", "biblebot", "__init__.py"),
    encoding="utf-8",
) as f:
    content = f.read()
    match = re.search(r'__version__\s*=\s*["\']([^"\']*)["\']', content)
    if match:
        __version__ = match.group(1)
    else:
        raise RuntimeError(
            "Version string not found in src/biblebot/__init__.py"
        )  # noqa: TRY003

# Read README with fallback
try:
    with open("README.md", encoding="utf-8") as f:
        long_description = f.read()
except OSError:
    long_description = "A simple Matrix bot that fetches Bible verses."

setup(
    name="matrix-biblebot",
    version=__version__,
    author="Jeremiah K",
    author_email="jeremiahk@gmx.com",
    description="A simple Matrix bot that fetches Bible verses",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    license_files=["LICENSE", "LICENSE.txt"],
    url="https://github.com/jeremiah-k/matrix-biblebot",
    project_urls={
        "Bug Tracker": "https://github.com/jeremiah-k/matrix-biblebot/issues"
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Topic :: Communications",
    ],
    python_requires=">=3.9",
    install_requires=[
        "matrix-nio>=0.25.2,<0.26",
        "PyYAML~=6.0",
        "python-dotenv~=1.1.0",
        "aiohttp>=3.11.0",
        "rich~=13.7",
        "packaging~=24.0",
    ],
    extras_require={
        "test": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0",
            "pytest-aiohttp>=1.0",
            "coverage>=7.6",
        ],
        "e2e": [
            "matrix-nio[e2e]>=0.25.2,<0.26",
        ],
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={"biblebot.tools": ["*.yaml", "*.service"]},
    entry_points={"console_scripts": ["biblebot = biblebot.cli:main"]},
)
