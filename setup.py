#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Package definition for PyPI."""
import os

from setuptools import setup

PROJECT_SLUG = "mbed-tools-ci-scripts"
SOURCE_DIR = "mbed_tools_ci_scripts"
__version__ = None

repository_dir = os.path.dirname(__file__)

# Read package version, this will set the variable `__version__` to the current version.
with open(os.path.join(repository_dir, SOURCE_DIR, "_version.py"), encoding="utf8") as fh:
    exec(fh.read())

# Use readme needed as long description in PyPI
with open(os.path.join(repository_dir, "README.md"), encoding="utf8") as fh:
    long_description = fh.read()

setup(
    author="Mbed team",
    author_email="support@mbed.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Embedded Systems",
    ],
    description="Continuous Integration scripts used by Mbed tools Python packages",
    entry_points={
        "console_scripts": [
            f"assert-news={SOURCE_DIR}.assert_news:main",
            f"generate-news={SOURCE_DIR}.generate_news:main",
            f"create-news-file={SOURCE_DIR}.create_news_file:main",
            f"generate-docs={SOURCE_DIR}.generate_docs:main",
            f"tag-and-release={SOURCE_DIR}.tag_and_release:main",
            f"get-config={SOURCE_DIR}.get_config:main",
            f"license-files={SOURCE_DIR}.license_files:main",
            f"generate-spdx={SOURCE_DIR}.report_third_party_ip:main",
        ],
    },
    keywords="Arm Mbed OS MbedOS Tools CI Scripts",
    include_package_data=True,
    install_requires=[
        "gitpython",
        "towncrier==19.2.0",
        "pyautoversion~=1.2.0",
        "pdoc3",
        "toml",
        "python-dotenv",
        "twine",
        "boto3",
        "packaging",
        "licenseheaders",
        "spdx-tools",
        "license-expression",
        "wcmatch",
        "dataclasses; python_version<'3.7'",
    ],
    license="Apache 2.0",
    long_description_content_type="text/markdown",
    long_description=long_description,
    name=PROJECT_SLUG,
    packages=[SOURCE_DIR],
    python_requires=">=3.6,<4",
    url=f"https://github.com/ARMmbed/{PROJECT_SLUG}",
    version=__version__,
)
