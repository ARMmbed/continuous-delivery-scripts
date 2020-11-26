#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Package definition for PyPI."""
import os

from setuptools import setup

PROJECT_SLUG = "continuous-delivery-scripts"
SOURCE_DIR = "continuous_delivery_scripts"
__version__ = None

repository_dir = os.path.dirname(__file__)

# Read package version, this will set the variable `__version__` to the current version.
with open(os.path.join(repository_dir, SOURCE_DIR, "_version.py"), encoding="utf8") as fh:
    exec(fh.read())

# Use readme needed as long description in PyPI
with open(os.path.join(repository_dir, "README.md"), encoding="utf8") as fh:
    long_description = fh.read()

setup(
    author="CMSIS team",
    author_email="adrien.cabarbaye@arm.com",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Build Tools",
    ],
    description="Continuous Delivery scripts to increase automation",
    entry_points={
        "console_scripts": [
            f"cd-assert-news={SOURCE_DIR}.assert_news:main",
            f"cd-generate-news={SOURCE_DIR}.generate_news:main",
            f"cd-create-news-file={SOURCE_DIR}.create_news_file:main",
            f"cd-generate-docs={SOURCE_DIR}.generate_docs:main",
            f"cd-tag-and-release={SOURCE_DIR}.tag_and_release:main",
            f"cd-get-config={SOURCE_DIR}.get_config:main",
            f"cd-license-files={SOURCE_DIR}.license_files:main",
            f"cd-generate-spdx={SOURCE_DIR}.report_third_party_ip:main",
        ]
    },
    keywords="Arm Tools CI CD Continuous Delivery Scripts Automation",
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
        "jellyfish",
        "jinja2",
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
