"""Package definition for PyPI."""
from setuptools import setup, find_packages

PACKAGE_NAME = "mbed-tools-ci"
SOURCE_DIR = "mbed_tools_ci"
__version__ = None

setup(
    name="mbed-tools-ci",
    version="0.0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "assert-news=mbed_tools_ci.assert_news:main",
            "generate-news=mbed_tools_ci.generate_news:main",
            "generate-docs=mbed_tools_ci.generate_docs:main",
            "tag-and-release=mbed_tools_ci.tag_and_release:main",
            "get-config=mbed_tools_ci.get_config:main",
        ],
    },
    install_requires=[
        'gitpython',
        'towncrier',
        'pyautoversion',
        'pdoc3',
        'toml',
        'python-dotenv',
        'twine<1.12',
    ],
)
